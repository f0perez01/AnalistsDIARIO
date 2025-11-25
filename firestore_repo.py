"""
Firestore Repository for Workflow State Management
Handles persistence and retrieval of workflow execution state
"""

from typing import Dict, Any, Optional
from google.cloud import firestore
from datetime import datetime
import structlog

logger = structlog.get_logger()


class FirestoreRepo:
    """Repository for managing workflow state in Firestore"""

    def __init__(self, workflow_name: str, project_id: Optional[str] = None):
        """
        Initialize Firestore repository
        
        Args:
            workflow_name: Unique identifier for the workflow
            project_id: GCP project ID (optional, uses default if not provided)
        """
        self.workflow_name = workflow_name
        self.db = firestore.Client(project=project_id)
        self.collection = self.db.collection("workflow_runs")
        self.doc_ref = self.collection.document(workflow_name)
        
        logger.info(
            "firestore_repo_initialized",
            workflow_name=workflow_name,
            project_id=project_id
        )

    def get_state(self) -> Dict[str, Any]:
        """
        Retrieve the current state of the workflow
        
        Returns:
            Dictionary containing workflow state, or default state if not found
        """
        try:
            doc = self.doc_ref.get()
            
            if doc.exists:
                state = doc.to_dict()
                logger.info(
                    "state_retrieved",
                    workflow_name=self.workflow_name,
                    status=state.get("status"),
                    last_success_step=state.get("last_success_step")
                )
                return state
            else:
                logger.info(
                    "state_not_found_using_default",
                    workflow_name=self.workflow_name
                )
                return self._get_default_state()
                
        except Exception as e:
            logger.error(
                "error_retrieving_state",
                workflow_name=self.workflow_name,
                error=str(e)
            )
            return self._get_default_state()

    def update_state(self, data: Dict[str, Any]) -> None:
        """
        Update the workflow state in Firestore
        
        Args:
            data: Dictionary containing state updates
        """
        try:
            # Add timestamp to all updates
            data["updated_at"] = firestore.SERVER_TIMESTAMP
            
            # Merge with existing data
            self.doc_ref.set(data, merge=True)
            
            logger.info(
                "state_updated",
                workflow_name=self.workflow_name,
                updates=list(data.keys())
            )
            
        except Exception as e:
            logger.error(
                "error_updating_state",
                workflow_name=self.workflow_name,
                error=str(e)
            )
            raise

    def reset_state(self) -> None:
        """Reset the workflow state to initial state"""
        try:
            self.doc_ref.set(self._get_default_state())
            logger.info(
                "state_reset",
                workflow_name=self.workflow_name
            )
        except Exception as e:
            logger.error(
                "error_resetting_state",
                workflow_name=self.workflow_name,
                error=str(e)
            )
            raise

    def get_execution_history(self, limit: int = 10) -> list:
        """
        Get execution history for this workflow
        
        Args:
            limit: Maximum number of historical records to retrieve
            
        Returns:
            List of historical execution states
        """
        try:
            # Query subcollection for history
            history_ref = self.doc_ref.collection("history")
            docs = history_ref.order_by(
                "created_at", 
                direction=firestore.Query.DESCENDING
            ).limit(limit).stream()
            
            history = [doc.to_dict() for doc in docs]
            
            logger.info(
                "history_retrieved",
                workflow_name=self.workflow_name,
                count=len(history)
            )
            
            return history
            
        except Exception as e:
            logger.error(
                "error_retrieving_history",
                workflow_name=self.workflow_name,
                error=str(e)
            )
            return []

    def save_execution_to_history(self, execution_data: Dict[str, Any]) -> None:
        """
        Save completed execution to history
        
        Args:
            execution_data: Data from completed execution
        """
        try:
            execution_data["created_at"] = firestore.SERVER_TIMESTAMP
            
            history_ref = self.doc_ref.collection("history")
            history_ref.add(execution_data)
            
            logger.info(
                "execution_saved_to_history",
                workflow_name=self.workflow_name,
                status=execution_data.get("status")
            )
            
        except Exception as e:
            logger.error(
                "error_saving_to_history",
                workflow_name=self.workflow_name,
                error=str(e)
            )

    @staticmethod
    def _get_default_state() -> Dict[str, Any]:
        """
        Get default initial state for a workflow
        
        Returns:
            Default state dictionary
        """
        return {
            "status": "NOT_STARTED",
            "last_success_step": -1,
            "current_step": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "retry_count": 0
        }
