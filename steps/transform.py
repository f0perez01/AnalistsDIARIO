"""
Transform Step - Data Transformation and Cleaning
Transforms and cleans extracted data
"""

from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import pandas as pd
from saga_orchestrator import WorkflowStep

logger = structlog.get_logger()


class TransformStep(WorkflowStep):
    """
    Step for transforming and cleaning data
    """
    
    name = "transform_data"
    
    def __init__(
        self,
        input_data: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize transform step
        
        Args:
            input_data: Data from previous step
            config: Configuration dictionary with transformation parameters
        """
        self.input_data = input_data
        self.config = config or {}
        self.transformed_data = None
        self.backup_data = None
        
    async def run(self) -> Dict[str, Any]:
        """
        Execute data transformation
        
        Returns:
            Dictionary with transformation results
        """
        logger.info(
            "transform_step_started",
            step=self.name
        )
        
        try:
            # Backup original data for potential compensation
            self.backup_data = self.input_data
            
            # Convert to DataFrame if needed
            if isinstance(self.input_data, list):
                df = pd.DataFrame(self.input_data)
            elif isinstance(self.input_data, pd.DataFrame):
                df = self.input_data.copy()
            else:
                raise ValueError("Unsupported input data type")
            
            # Apply transformations
            df = await self._clean_data(df)
            df = await self._normalize_data(df)
            df = await self._enrich_data(df)
            df = await self._validate_data(df)
            
            self.transformed_data = df
            
            logger.info(
                "transform_step_completed",
                step=self.name,
                input_records=len(self.input_data) if isinstance(self.input_data, (list, pd.DataFrame)) else "N/A",
                output_records=len(df)
            )
            
            return {
                "status": "success",
                "input_records": len(self.input_data) if isinstance(self.input_data, (list, pd.DataFrame)) else 0,
                "output_records": len(df),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "transform_step_failed",
                step=self.name,
                error=str(e)
            )
            raise
    
    async def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean data - remove nulls, duplicates, etc.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Cleaned DataFrame
        """
        logger.info("cleaning_data")
        
        initial_rows = len(df)
        
        # Remove duplicates
        df = df.drop_duplicates()
        
        # Handle missing values
        df = df.dropna(subset=self.config.get("required_columns", []))
        
        # Fill other missing values
        df = df.fillna(self.config.get("fill_values", {}))
        
        rows_removed = initial_rows - len(df)
        
        logger.info(
            "data_cleaned",
            initial_rows=initial_rows,
            final_rows=len(df),
            rows_removed=rows_removed
        )
        
        return df
    
    async def _normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize data - standardize formats, types, etc.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Normalized DataFrame
        """
        logger.info("normalizing_data")
        
        # Convert timestamp columns to datetime
        timestamp_columns = self.config.get("timestamp_columns", ["timestamp"])
        for col in timestamp_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # Normalize string columns
        string_columns = df.select_dtypes(include=["object"]).columns
        for col in string_columns:
            df[col] = df[col].str.strip().str.lower()
        
        # Convert numeric columns
        numeric_columns = self.config.get("numeric_columns", [])
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        logger.info(
            "data_normalized",
            rows=len(df)
        )
        
        return df
    
    async def _enrich_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich data - add calculated fields, categories, etc.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Enriched DataFrame
        """
        logger.info("enriching_data")
        
        # Add date components if timestamp exists
        if "timestamp" in df.columns:
            df["date"] = pd.to_datetime(df["timestamp"]).dt.date
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
            df["day_of_week"] = pd.to_datetime(df["timestamp"]).dt.dayofweek
        
        # Add calculated fields based on config
        calculated_fields = self.config.get("calculated_fields", {})
        for field_name, calculation in calculated_fields.items():
            # Example: df[field_name] = df.eval(calculation)
            pass
        
        logger.info(
            "data_enriched",
            rows=len(df),
            columns=len(df.columns)
        )
        
        return df
    
    async def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate data quality
        
        Args:
            df: Input DataFrame
            
        Returns:
            Validated DataFrame
        """
        logger.info("validating_data")
        
        # Check for required columns
        required_columns = self.config.get("required_columns", [])
        missing_columns = set(required_columns) - set(df.columns)
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Check data ranges
        validations = self.config.get("validations", {})
        for column, rules in validations.items():
            if column in df.columns:
                if "min" in rules:
                    invalid_count = (df[column] < rules["min"]).sum()
                    if invalid_count > 0:
                        logger.warning(
                            "validation_warning",
                            column=column,
                            rule="min",
                            invalid_count=invalid_count
                        )
                
                if "max" in rules:
                    invalid_count = (df[column] > rules["max"]).sum()
                    if invalid_count > 0:
                        logger.warning(
                            "validation_warning",
                            column=column,
                            rule="max",
                            invalid_count=invalid_count
                        )
        
        logger.info(
            "data_validated",
            rows=len(df)
        )
        
        return df
    
    async def compensate(self) -> None:
        """
        Compensate/rollback transformation step
        Restore original data
        """
        logger.info(
            "transform_step_compensation_started",
            step=self.name
        )
        
        try:
            # Restore backup data
            if self.backup_data is not None:
                self.transformed_data = self.backup_data
                logger.info(
                    "data_restored_from_backup",
                    step=self.name
                )
            
            # Clear transformed data
            self.transformed_data = None
            
            logger.info(
                "transform_step_compensation_completed",
                step=self.name
            )
            
        except Exception as e:
            logger.error(
                "transform_step_compensation_failed",
                step=self.name,
                error=str(e)
            )
            raise
