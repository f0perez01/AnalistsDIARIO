"""
Main Application - FastAPI Entry Point
Handles HTTP requests from Cloud Scheduler and orchestrates workflow execution
"""

import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from saga_orchestrator import SagaOrchestrator
from steps.extract import ExtractStep
from steps.transform import TransformStep
from steps.analyze import AnalyzeStep
from steps.store import StoreStep
from secrets_manager import get_secrets_manager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Configuration from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "daily_data_analysis")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events
    """
    # Startup
    logger.info(
        "application_starting",
        environment=ENVIRONMENT,
        project_id=PROJECT_ID,
        workflow_name=WORKFLOW_NAME
    )
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")


# Initialize FastAPI app
app = FastAPI(
    title="Data Analysis Microservice",
    description="Daily data analysis workflow with Saga pattern orchestration",
    version="1.0.0",
    lifespan=lifespan
)


# Request/Response Models
class WorkflowExecutionRequest(BaseModel):
    """Request model for workflow execution"""
    retry: bool = False
    config: Optional[dict] = None


class WorkflowStatusResponse(BaseModel):
    """Response model for workflow status"""
    workflow_name: str
    status: str
    last_success_step: int
    current_step: Optional[str]
    error: Optional[str]


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run
    """
    return {
        "status": "healthy",
        "service": "data-analysis-service",
        "environment": ENVIRONMENT
    }


# Readiness check endpoint
@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint
    """
    try:
        # Could add checks for Firestore connectivity, etc.
        return {
            "status": "ready",
            "service": "data-analysis-service"
        }
    except Exception as e:
        logger.error("readiness_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")


# Main workflow execution endpoint
@app.post("/run-analysis")
async def run_analysis(
    background_tasks: BackgroundTasks,
    retry: bool = Query(False, description="Retry failed execution"),
    async_execution: bool = Query(False, description="Run in background")
):
    """
    Execute the daily data analysis workflow
    
    Args:
        retry: Whether to retry a failed execution
        async_execution: Whether to run in background (returns immediately)
    
    Returns:
        Workflow execution result
    """
    logger.info(
        "workflow_execution_requested",
        workflow_name=WORKFLOW_NAME,
        retry=retry,
        async_execution=async_execution
    )
    
    try:
        if async_execution:
            # Run in background
            background_tasks.add_task(execute_workflow, retry)
            
            return JSONResponse(
                status_code=202,
                content={
                    "status": "accepted",
                    "message": "Workflow execution started in background",
                    "workflow_name": WORKFLOW_NAME
                }
            )
        else:
            # Run synchronously
            result = await execute_workflow(retry)
            return result
            
    except Exception as e:
        logger.error(
            "workflow_execution_error",
            workflow_name=WORKFLOW_NAME,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {str(e)}"
        )


async def execute_workflow(retry: bool = False) -> dict:
    """
    Execute the complete workflow
    
    Args:
        retry: Whether this is a retry
        
    Returns:
        Execution result dictionary
    """
    logger.info(
        "executing_workflow",
        workflow_name=WORKFLOW_NAME,
        retry=retry
    )
    
    try:
        # Load configuration (could be from Secret Manager, env vars, etc.)
        config = load_workflow_config()
        
        # Initialize workflow steps
        extract_step = ExtractStep(config=config.get("extract", {}))
        transform_step = TransformStep(config=config.get("transform", {}))
        analyze_step = AnalyzeStep(config=config.get("analyze", {}))
        store_step = StoreStep(config=config.get("store", {}))
        
        # Create orchestrator
        orchestrator = SagaOrchestrator(
            workflow_name=WORKFLOW_NAME,
            steps=[extract_step, transform_step, analyze_step, store_step],
            project_id=PROJECT_ID,
            max_retries=3
        )
        
        # Execute workflow
        result = await orchestrator.execute(retry=retry)
        
        logger.info(
            "workflow_execution_completed",
            workflow_name=WORKFLOW_NAME,
            status=result.get("status")
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "workflow_execution_failed",
            workflow_name=WORKFLOW_NAME,
            error=str(e)
        )
        raise


# Workflow status endpoint
@app.get("/status", response_model=WorkflowStatusResponse)
async def get_workflow_status():
    """
    Get current workflow status
    
    Returns:
        Current workflow state
    """
    try:
        from firestore_repo import FirestoreRepo
        
        repo = FirestoreRepo(WORKFLOW_NAME, PROJECT_ID)
        state = repo.get_state()
        
        return WorkflowStatusResponse(
            workflow_name=WORKFLOW_NAME,
            status=state.get("status", "UNKNOWN"),
            last_success_step=state.get("last_success_step", -1),
            current_step=state.get("current_step"),
            error=state.get("error")
        )
        
    except Exception as e:
        logger.error("status_check_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve status: {str(e)}"
        )


# Reset workflow endpoint
@app.post("/reset")
async def reset_workflow():
    """
    Reset workflow to initial state
    
    Returns:
        Reset confirmation
    """
    try:
        from firestore_repo import FirestoreRepo
        
        repo = FirestoreRepo(WORKFLOW_NAME, PROJECT_ID)
        repo.reset_state()
        
        logger.info(
            "workflow_reset",
            workflow_name=WORKFLOW_NAME
        )
        
        return {
            "status": "success",
            "message": "Workflow reset to initial state",
            "workflow_name": WORKFLOW_NAME
        }
        
    except Exception as e:
        logger.error("workflow_reset_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset workflow: {str(e)}"
        )


# Execution history endpoint
@app.get("/history")
async def get_execution_history(limit: int = Query(10, ge=1, le=100)):
    """
    Get workflow execution history
    
    Args:
        limit: Maximum number of historical records to retrieve
        
    Returns:
        List of historical executions
    """
    try:
        from firestore_repo import FirestoreRepo
        
        repo = FirestoreRepo(WORKFLOW_NAME, PROJECT_ID)
        history = repo.get_execution_history(limit=limit)
        
        return {
            "workflow_name": WORKFLOW_NAME,
            "history": history,
            "count": len(history)
        }
        
    except Exception as e:
        logger.error("history_retrieval_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve history: {str(e)}"
        )


def load_workflow_config() -> dict:
    """
    Load workflow configuration from various sources
    
    Returns:
        Configuration dictionary
    """
    config = {
        "extract": {
            # Extract step configuration
        },
        "transform": {
            "required_columns": ["id", "timestamp", "value"],
            "timestamp_columns": ["timestamp"],
            "numeric_columns": ["value"],
        },
        "analyze": {
            "custom_metrics": {
                "total_records": {
                    "type": "count"
                }
            }
        },
        "store": {
            "project_id": PROJECT_ID,
            "firestore_enabled": True,
            "firestore_collection": "analysis_results",
            "storage_enabled": os.getenv("STORAGE_ENABLED", "false").lower() == "true",
            "storage_bucket": os.getenv("STORAGE_BUCKET"),
            "bigquery_enabled": os.getenv("BIGQUERY_ENABLED", "false").lower() == "true",
            "bigquery_dataset": os.getenv("BIGQUERY_DATASET"),
            "bigquery_table": os.getenv("BIGQUERY_TABLE"),
        }
    }
    
    # Optionally load additional config from Secret Manager
    if os.getenv("CONFIG_SECRET_NAME"):
        try:
            secrets_mgr = get_secrets_manager(PROJECT_ID)
            secret_config = secrets_mgr.get_secret_json(
                os.getenv("CONFIG_SECRET_NAME")
            )
            # Merge with default config
            config.update(secret_config)
        except Exception as e:
            logger.warning(
                "failed_to_load_secret_config",
                error=str(e)
            )
    
    return config


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with service information
    """
    return {
        "service": "data-analysis-microservice",
        "version": "1.0.0",
        "workflow": WORKFLOW_NAME,
        "environment": ENVIRONMENT,
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "run_analysis": "/run-analysis",
            "status": "/status",
            "reset": "/reset",
            "history": "/history"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    
    logger.info(
        "starting_server",
        port=port,
        environment=ENVIRONMENT
    )
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
