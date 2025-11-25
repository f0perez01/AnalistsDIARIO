"""
Store Step - Store Analysis Results
Stores results to various destinations (Firestore, BigQuery, Cloud Storage)
"""

from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import json
from google.cloud import firestore, storage
from saga_orchestrator import WorkflowStep

logger = structlog.get_logger()


class StoreStep(WorkflowStep):
    """
    Step for storing analysis results
    """
    
    name = "store_results"
    
    def __init__(
        self,
        input_data: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize store step
        
        Args:
            input_data: Analysis results from previous step
            config: Configuration dictionary with storage parameters
        """
        self.input_data = input_data
        self.config = config or {}
        self.stored_references = []
        
    async def run(self) -> Dict[str, Any]:
        """
        Execute storage of results
        
        Returns:
            Dictionary with storage results
        """
        logger.info(
            "store_step_started",
            step=self.name
        )
        
        try:
            storage_results = {}
            
            # Store to Firestore
            if self.config.get("firestore_enabled", True):
                firestore_result = await self._store_to_firestore()
                storage_results["firestore"] = firestore_result
            
            # Store to Cloud Storage
            if self.config.get("storage_enabled", False):
                storage_result = await self._store_to_cloud_storage()
                storage_results["cloud_storage"] = storage_result
            
            # Store to BigQuery
            if self.config.get("bigquery_enabled", False):
                bigquery_result = await self._store_to_bigquery()
                storage_results["bigquery"] = bigquery_result
            
            logger.info(
                "store_step_completed",
                step=self.name,
                destinations=list(storage_results.keys())
            )
            
            return {
                "status": "success",
                "storage_results": storage_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "store_step_failed",
                step=self.name,
                error=str(e)
            )
            raise
    
    async def _store_to_firestore(self) -> Dict[str, Any]:
        """
        Store results to Firestore
        
        Returns:
            Dictionary with Firestore storage result
        """
        logger.info("storing_to_firestore")
        
        try:
            db = firestore.Client(project=self.config.get("project_id"))
            
            # Collection name from config or default
            collection_name = self.config.get(
                "firestore_collection",
                "analysis_results"
            )
            
            # Prepare document data
            doc_data = {
                "timestamp": datetime.utcnow(),
                "results": self.input_data,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            
            # Add document
            doc_ref = db.collection(collection_name).add(doc_data)
            doc_id = doc_ref[1].id
            
            # Track for potential compensation
            self.stored_references.append({
                "type": "firestore",
                "collection": collection_name,
                "document_id": doc_id
            })
            
            logger.info(
                "firestore_storage_completed",
                collection=collection_name,
                document_id=doc_id
            )
            
            return {
                "success": True,
                "collection": collection_name,
                "document_id": doc_id
            }
            
        except Exception as e:
            logger.error(
                "firestore_storage_failed",
                error=str(e)
            )
            raise
    
    async def _store_to_cloud_storage(self) -> Dict[str, Any]:
        """
        Store results to Cloud Storage as JSON
        
        Returns:
            Dictionary with Cloud Storage result
        """
        logger.info("storing_to_cloud_storage")
        
        try:
            storage_client = storage.Client(
                project=self.config.get("project_id")
            )
            
            # Bucket name from config
            bucket_name = self.config.get("storage_bucket")
            if not bucket_name:
                raise ValueError("storage_bucket not configured")
            
            bucket = storage_client.bucket(bucket_name)
            
            # Generate blob name with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob_name = self.config.get(
                "storage_path_template",
                "analysis_results/{timestamp}.json"
            ).format(timestamp=timestamp)
            
            blob = bucket.blob(blob_name)
            
            # Convert results to JSON
            json_data = json.dumps(self.input_data, indent=2, default=str)
            
            # Upload
            blob.upload_from_string(
                json_data,
                content_type="application/json"
            )
            
            # Track for potential compensation
            self.stored_references.append({
                "type": "cloud_storage",
                "bucket": bucket_name,
                "blob": blob_name
            })
            
            logger.info(
                "cloud_storage_completed",
                bucket=bucket_name,
                blob=blob_name
            )
            
            return {
                "success": True,
                "bucket": bucket_name,
                "blob": blob_name,
                "uri": f"gs://{bucket_name}/{blob_name}"
            }
            
        except Exception as e:
            logger.error(
                "cloud_storage_failed",
                error=str(e)
            )
            raise
    
    async def _store_to_bigquery(self) -> Dict[str, Any]:
        """
        Store results to BigQuery
        
        Returns:
            Dictionary with BigQuery storage result
        """
        logger.info("storing_to_bigquery")
        
        try:
            from google.cloud import bigquery
            
            bq_client = bigquery.Client(
                project=self.config.get("project_id")
            )
            
            # Table reference from config
            dataset_id = self.config.get("bigquery_dataset")
            table_id = self.config.get("bigquery_table")
            
            if not dataset_id or not table_id:
                raise ValueError("BigQuery dataset or table not configured")
            
            table_ref = bq_client.dataset(dataset_id).table(table_id)
            
            # Prepare rows for insertion
            rows_to_insert = self._prepare_bigquery_rows()
            
            # Insert rows
            errors = bq_client.insert_rows_json(table_ref, rows_to_insert)
            
            if errors:
                raise Exception(f"BigQuery insertion errors: {errors}")
            
            # Track for potential compensation
            self.stored_references.append({
                "type": "bigquery",
                "dataset": dataset_id,
                "table": table_id,
                "rows_inserted": len(rows_to_insert)
            })
            
            logger.info(
                "bigquery_storage_completed",
                dataset=dataset_id,
                table=table_id,
                rows=len(rows_to_insert)
            )
            
            return {
                "success": True,
                "dataset": dataset_id,
                "table": table_id,
                "rows_inserted": len(rows_to_insert)
            }
            
        except Exception as e:
            logger.error(
                "bigquery_storage_failed",
                error=str(e)
            )
            raise
    
    def _prepare_bigquery_rows(self) -> List[Dict[str, Any]]:
        """
        Prepare data for BigQuery insertion
        
        Returns:
            List of row dictionaries
        """
        rows = []
        
        # Flatten results for BigQuery schema
        # Adjust based on your actual data structure and BigQuery schema
        
        if isinstance(self.input_data, dict):
            # Single result record
            row = {
                "timestamp": datetime.utcnow().isoformat(),
                "results_json": json.dumps(self.input_data, default=str)
            }
            
            # Extract specific metrics if available
            if "results" in self.input_data:
                results = self.input_data["results"]
                
                if "metrics" in results:
                    for metric_name, metric_value in results["metrics"].items():
                        row[f"metric_{metric_name}"] = metric_value
            
            rows.append(row)
        
        return rows
    
    async def compensate(self) -> None:
        """
        Compensate/rollback storage step
        Delete stored data
        """
        logger.info(
            "store_step_compensation_started",
            step=self.name,
            references_count=len(self.stored_references)
        )
        
        try:
            for ref in self.stored_references:
                try:
                    if ref["type"] == "firestore":
                        # Delete Firestore document
                        db = firestore.Client(
                            project=self.config.get("project_id")
                        )
                        db.collection(ref["collection"]).document(
                            ref["document_id"]
                        ).delete()
                        
                        logger.info(
                            "firestore_document_deleted",
                            collection=ref["collection"],
                            document_id=ref["document_id"]
                        )
                    
                    elif ref["type"] == "cloud_storage":
                        # Delete Cloud Storage blob
                        storage_client = storage.Client(
                            project=self.config.get("project_id")
                        )
                        bucket = storage_client.bucket(ref["bucket"])
                        blob = bucket.blob(ref["blob"])
                        blob.delete()
                        
                        logger.info(
                            "cloud_storage_blob_deleted",
                            bucket=ref["bucket"],
                            blob=ref["blob"]
                        )
                    
                    elif ref["type"] == "bigquery":
                        # BigQuery doesn't support row-level deletes easily
                        # Log for manual cleanup or implement custom logic
                        logger.warning(
                            "bigquery_compensation_requires_manual_cleanup",
                            dataset=ref["dataset"],
                            table=ref["table"]
                        )
                
                except Exception as e:
                    logger.error(
                        "compensation_delete_failed",
                        reference=ref,
                        error=str(e)
                    )
                    continue
            
            # Clear stored references
            self.stored_references = []
            
            logger.info(
                "store_step_compensation_completed",
                step=self.name
            )
            
        except Exception as e:
            logger.error(
                "store_step_compensation_failed",
                step=self.name,
                error=str(e)
            )
            raise
