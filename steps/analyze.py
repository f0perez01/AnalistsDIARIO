"""
Analyze Step - Data Analysis and Metrics Calculation
Performs analysis on transformed data
"""

from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import pandas as pd
import numpy as np
from saga_orchestrator import WorkflowStep

logger = structlog.get_logger()


class AnalyzeStep(WorkflowStep):
    """
    Step for analyzing data and calculating metrics
    """
    
    name = "analyze_data"
    
    def __init__(
        self,
        input_data: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize analyze step
        
        Args:
            input_data: Transformed data from previous step
            config: Configuration dictionary with analysis parameters
        """
        self.input_data = input_data
        self.config = config or {}
        self.analysis_results = None
        
    async def run(self) -> Dict[str, Any]:
        """
        Execute data analysis
        
        Returns:
            Dictionary with analysis results
        """
        logger.info(
            "analyze_step_started",
            step=self.name
        )
        
        try:
            # Convert to DataFrame if needed
            if isinstance(self.input_data, list):
                df = pd.DataFrame(self.input_data)
            elif isinstance(self.input_data, pd.DataFrame):
                df = self.input_data.copy()
            else:
                raise ValueError("Unsupported input data type")
            
            # Perform different types of analysis
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_records": len(df),
                "descriptive_stats": await self._calculate_descriptive_stats(df),
                "aggregations": await self._calculate_aggregations(df),
                "trends": await self._calculate_trends(df),
                "anomalies": await self._detect_anomalies(df),
                "metrics": await self._calculate_custom_metrics(df)
            }
            
            self.analysis_results = results
            
            logger.info(
                "analyze_step_completed",
                step=self.name,
                records_analyzed=len(df),
                metrics_count=len(results.get("metrics", {}))
            )
            
            return {
                "status": "success",
                "records_analyzed": len(df),
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "analyze_step_failed",
                step=self.name,
                error=str(e)
            )
            raise
    
    async def _calculate_descriptive_stats(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate descriptive statistics
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary with statistics
        """
        logger.info("calculating_descriptive_stats")
        
        stats = {}
        
        # Numeric columns statistics
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            stats[col] = {
                "mean": float(df[col].mean()),
                "median": float(df[col].median()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "q25": float(df[col].quantile(0.25)),
                "q75": float(df[col].quantile(0.75))
            }
        
        logger.info(
            "descriptive_stats_calculated",
            numeric_columns=len(numeric_cols)
        )
        
        return stats
    
    async def _calculate_aggregations(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate aggregations by different dimensions
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary with aggregations
        """
        logger.info("calculating_aggregations")
        
        aggregations = {}
        
        # Group by category if exists
        if "category" in df.columns and "value" in df.columns:
            category_agg = df.groupby("category")["value"].agg([
                "sum", "mean", "count", "min", "max"
            ]).to_dict("index")
            
            # Convert numpy types to native Python types
            aggregations["by_category"] = {
                k: {key: float(val) for key, val in v.items()}
                for k, v in category_agg.items()
            }
        
        # Group by date if exists
        if "date" in df.columns and "value" in df.columns:
            date_agg = df.groupby("date")["value"].agg([
                "sum", "mean", "count"
            ]).to_dict("index")
            
            aggregations["by_date"] = {
                str(k): {key: float(val) for key, val in v.items()}
                for k, v in date_agg.items()
            }
        
        logger.info(
            "aggregations_calculated",
            dimensions=len(aggregations)
        )
        
        return aggregations
    
    async def _calculate_trends(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate trends and growth rates
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary with trend analysis
        """
        logger.info("calculating_trends")
        
        trends = {}
        
        if "value" in df.columns:
            # Overall trend
            if len(df) > 1:
                first_value = df["value"].iloc[0]
                last_value = df["value"].iloc[-1]
                
                if first_value != 0:
                    growth_rate = ((last_value - first_value) / first_value) * 100
                    trends["overall_growth_rate"] = float(growth_rate)
                
                # Moving average if we have date column
                if "date" in df.columns:
                    df_sorted = df.sort_values("date")
                    df_sorted["moving_avg_7d"] = df_sorted["value"].rolling(
                        window=min(7, len(df_sorted))
                    ).mean()
                    
                    trends["latest_moving_average"] = float(
                        df_sorted["moving_avg_7d"].iloc[-1]
                    )
        
        logger.info(
            "trends_calculated",
            metrics_count=len(trends)
        )
        
        return trends
    
    async def _detect_anomalies(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect anomalies using statistical methods
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary with anomaly detection results
        """
        logger.info("detecting_anomalies")
        
        anomalies = {
            "count": 0,
            "records": []
        }
        
        if "value" in df.columns:
            # Simple outlier detection using IQR
            Q1 = df["value"].quantile(0.25)
            Q3 = df["value"].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            anomaly_mask = (df["value"] < lower_bound) | (df["value"] > upper_bound)
            anomaly_records = df[anomaly_mask]
            
            anomalies["count"] = len(anomaly_records)
            anomalies["lower_bound"] = float(lower_bound)
            anomalies["upper_bound"] = float(upper_bound)
            
            # Limit anomaly records to prevent large payloads
            if len(anomaly_records) > 0:
                anomalies["records"] = anomaly_records.head(10).to_dict("records")
        
        logger.info(
            "anomalies_detected",
            count=anomalies["count"]
        )
        
        return anomalies
    
    async def _calculate_custom_metrics(
        self,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate custom business metrics
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary with custom metrics
        """
        logger.info("calculating_custom_metrics")
        
        metrics = {}
        
        # Example custom metrics based on configuration
        custom_metrics_config = self.config.get("custom_metrics", {})
        
        for metric_name, metric_config in custom_metrics_config.items():
            try:
                # Example: Simple column aggregation
                if metric_config.get("type") == "sum":
                    column = metric_config.get("column")
                    if column in df.columns:
                        metrics[metric_name] = float(df[column].sum())
                
                elif metric_config.get("type") == "count":
                    filter_condition = metric_config.get("filter")
                    if filter_condition:
                        # Apply filter and count
                        # metrics[metric_name] = len(df.query(filter_condition))
                        pass
                    else:
                        metrics[metric_name] = len(df)
                
                elif metric_config.get("type") == "percentage":
                    numerator_col = metric_config.get("numerator")
                    denominator_col = metric_config.get("denominator")
                    if numerator_col in df.columns and denominator_col in df.columns:
                        total_numerator = df[numerator_col].sum()
                        total_denominator = df[denominator_col].sum()
                        if total_denominator != 0:
                            metrics[metric_name] = float(
                                (total_numerator / total_denominator) * 100
                            )
                
            except Exception as e:
                logger.error(
                    "custom_metric_calculation_failed",
                    metric=metric_name,
                    error=str(e)
                )
                continue
        
        # Default metrics if no custom config
        if not metrics and "value" in df.columns:
            metrics["total_value"] = float(df["value"].sum())
            metrics["average_value"] = float(df["value"].mean())
            metrics["record_count"] = len(df)
        
        logger.info(
            "custom_metrics_calculated",
            count=len(metrics)
        )
        
        return metrics
    
    async def compensate(self) -> None:
        """
        Compensate/rollback analysis step
        Clear analysis results
        """
        logger.info(
            "analyze_step_compensation_started",
            step=self.name
        )
        
        try:
            # Clear analysis results
            self.analysis_results = None
            
            logger.info(
                "analyze_step_compensation_completed",
                step=self.name
            )
            
        except Exception as e:
            logger.error(
                "analyze_step_compensation_failed",
                step=self.name,
                error=str(e)
            )
            raise
