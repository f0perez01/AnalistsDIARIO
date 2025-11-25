"""
Saga Orchestrator for Workflow Management
Implements the Saga pattern with compensating transactions
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog
from firestore_repo import FirestoreRepo

logger = structlog.get_logger()


class WorkflowStep:
    """Base class for workflow steps"""
    
    name: str = "base_step"
    
    async def run(self) -> Any:
        """
        Execute the step logic
        Should be implemented by subclasses
        """
        raise NotImplementedError("Step must implement run() method")
    
    async def compensate(self) -> None:
        """
        Compensate/undo the step if needed
        Optional - implement if the step needs compensation
        """
        logger.info(
            "no_compensation_defined",
            step=self.name
        )


class SagaOrchestrator:
    """
    Orchestrates workflow execution using the Saga pattern
    Manages state, retries, and compensating transactions
    """

    def __init__(
        self,
        workflow_name: str,
        steps: List[WorkflowStep],
        project_id: Optional[str] = None,
        max_retries: int = 3
    ):
        """
        Initialize the Saga orchestrator
        
        Args:
            workflow_name: Unique identifier for this workflow
            steps: List of workflow steps to execute in order
            project_id: GCP project ID (optional)
            max_retries: Maximum number of retries for failed steps
        """
        self.workflow_name = workflow_name
        self.steps = steps
        self.repo = FirestoreRepo(workflow_name, project_id)
        self.max_retries = max_retries
        
        logger.info(
            "saga_orchestrator_initialized",
            workflow_name=workflow_name,
            total_steps=len(steps),
            max_retries=max_retries
        )

    async def execute(self, retry: bool = False) -> Dict[str, Any]:
        """
        Execute the workflow using the Saga pattern
        
        Args:
            retry: Whether this is a retry of a failed execution
            
        Returns:
            Dictionary with execution results
        """
        logger.info(
            "workflow_execution_started",
            workflow_name=self.workflow_name,
            is_retry=retry
        )
        
        # Get current state
        state = self.repo.get_state()
        
        # Check if already in progress
        if state.get("status") == "IN_PROGRESS" and not retry:
            logger.warning(
                "workflow_already_in_progress",
                workflow_name=self.workflow_name
            )
            return {
                "status": "ALREADY_IN_PROGRESS",
                "message": "Workflow is already running"
            }
        
        # Initialize execution
        last_success_step = state.get("last_success_step", -1)
        retry_count = state.get("retry_count", 0) if retry else 0
        
        self.repo.update_state({
            "status": "IN_PROGRESS",
            "started_at": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
            "error": None
        })
        
        execution_result = {
            "status": "SUCCESS",
            "steps_executed": [],
            "errors": []
        }
        
        # Execute steps
        for index, step in enumerate(self.steps):
            
            # Skip already completed steps on retry
            if index <= last_success_step:
                logger.info(
                    "skipping_completed_step",
                    step=step.name,
                    index=index
                )
                execution_result["steps_executed"].append({
                    "step": step.name,
                    "status": "SKIPPED",
                    "index": index
                })
                continue
            
            # Execute step with retry logic
            step_result = await self._execute_step_with_retry(
                step, 
                index
            )
            
            execution_result["steps_executed"].append(step_result)
            
            if step_result["status"] == "FAILED":
                # Step failed after retries - run compensations
                logger.error(
                    "step_failed_initiating_compensation",
                    step=step.name,
                    index=index,
                    error=step_result.get("error")
                )
                
                await self._run_compensations(index)
                
                execution_result["status"] = "FAILED"
                execution_result["failed_step"] = step.name
                execution_result["failed_step_index"] = index
                
                self.repo.update_state({
                    "status": "FAILED",
                    "error": step_result.get("error"),
                    "failed_step": step.name,
                    "completed_at": datetime.utcnow().isoformat()
                })
                
                # Save to history
                self.repo.save_execution_to_history(execution_result)
                
                return execution_result
        
        # All steps completed successfully
        logger.info(
            "workflow_completed_successfully",
            workflow_name=self.workflow_name,
            total_steps=len(self.steps)
        )
        
        self.repo.update_state({
            "status": "SUCCESS",
            "completed_at": datetime.utcnow().isoformat(),
            "last_success_step": len(self.steps) - 1
        })
        
        # Save to history
        self.repo.save_execution_to_history(execution_result)
        
        return execution_result

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        index: int
    ) -> Dict[str, Any]:
        """
        Execute a single step with retry logic
        
        Args:
            step: The workflow step to execute
            index: Index of the step in the workflow
            
        Returns:
            Dictionary with step execution result
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "executing_step",
                    step=step.name,
                    index=index,
                    attempt=attempt + 1
                )
                
                self.repo.update_state({
                    "current_step": step.name,
                    "current_step_index": index,
                    "current_step_attempt": attempt + 1
                })
                
                # Execute the step
                result = await step.run()
                
                # Step succeeded
                logger.info(
                    "step_completed_successfully",
                    step=step.name,
                    index=index
                )
                
                self.repo.update_state({
                    "last_success_step": index
                })
                
                return {
                    "step": step.name,
                    "status": "SUCCESS",
                    "index": index,
                    "attempts": attempt + 1,
                    "result": result
                }
                
            except Exception as e:
                logger.error(
                    "step_execution_failed",
                    step=step.name,
                    index=index,
                    attempt=attempt + 1,
                    error=str(e)
                )
                
                # If this was the last retry, return failure
                if attempt == self.max_retries - 1:
                    return {
                        "step": step.name,
                        "status": "FAILED",
                        "index": index,
                        "attempts": attempt + 1,
                        "error": str(e)
                    }
                
                # Otherwise, continue to next retry
                continue
        
        # Should never reach here, but just in case
        return {
            "step": step.name,
            "status": "FAILED",
            "index": index,
            "error": "Max retries exceeded"
        }

    async def _run_compensations(self, failed_step_index: int) -> None:
        """
        Run compensation logic for all completed steps in reverse order
        
        Args:
            failed_step_index: Index of the step that failed
        """
        logger.info(
            "starting_compensations",
            failed_step_index=failed_step_index
        )
        
        # Run compensations in reverse order
        for index in reversed(range(failed_step_index)):
            step = self.steps[index]
            
            if hasattr(step, "compensate"):
                try:
                    logger.info(
                        "compensating_step",
                        step=step.name,
                        index=index
                    )
                    
                    await step.compensate()
                    
                    logger.info(
                        "compensation_completed",
                        step=step.name,
                        index=index
                    )
                    
                except Exception as e:
                    logger.error(
                        "compensation_failed",
                        step=step.name,
                        index=index,
                        error=str(e)
                    )
                    # Continue with other compensations even if one fails
                    continue

    def get_status(self) -> Dict[str, Any]:
        """
        Get current workflow status
        
        Returns:
            Current state from Firestore
        """
        return self.repo.get_state()

    def reset(self) -> None:
        """Reset workflow to initial state"""
        logger.info(
            "resetting_workflow",
            workflow_name=self.workflow_name
        )
        self.repo.reset_state()
