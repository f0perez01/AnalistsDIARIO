"""
Secrets Manager Integration
Retrieves secrets from Google Cloud Secret Manager
"""

from typing import Optional
import structlog
from google.cloud import secretmanager
from functools import lru_cache

logger = structlog.get_logger()


class SecretsManager:
    """
    Manager for retrieving secrets from Google Cloud Secret Manager
    """
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Secrets Manager
        
        Args:
            project_id: GCP project ID (optional, uses default if not provided)
        """
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
        
        logger.info(
            "secrets_manager_initialized",
            project_id=project_id
        )
    
    @lru_cache(maxsize=128)
    def get_secret(
        self,
        secret_name: str,
        version: str = "latest"
    ) -> str:
        """
        Retrieve a secret from Secret Manager
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")
            
        Returns:
            Secret value as string
        """
        try:
            # Build the resource name
            if self.project_id:
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            else:
                # Use default project from environment
                name = f"projects/-/secrets/{secret_name}/versions/{version}"
            
            logger.info(
                "retrieving_secret",
                secret_name=secret_name,
                version=version
            )
            
            # Access the secret version
            response = self.client.access_secret_version(request={"name": name})
            
            # Decode the secret payload
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.info(
                "secret_retrieved_successfully",
                secret_name=secret_name
            )
            
            return secret_value
            
        except Exception as e:
            logger.error(
                "secret_retrieval_failed",
                secret_name=secret_name,
                error=str(e)
            )
            raise
    
    def get_secret_json(self, secret_name: str, version: str = "latest") -> dict:
        """
        Retrieve a secret and parse it as JSON
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret
            
        Returns:
            Secret value parsed as dictionary
        """
        import json
        
        secret_value = self.get_secret(secret_name, version)
        
        try:
            return json.loads(secret_value)
        except json.JSONDecodeError as e:
            logger.error(
                "secret_json_parse_failed",
                secret_name=secret_name,
                error=str(e)
            )
            raise


# Global instance for easy access
_secrets_manager_instance: Optional[SecretsManager] = None


def get_secrets_manager(project_id: Optional[str] = None) -> SecretsManager:
    """
    Get or create a global SecretsManager instance
    
    Args:
        project_id: GCP project ID
        
    Returns:
        SecretsManager instance
    """
    global _secrets_manager_instance
    
    if _secrets_manager_instance is None:
        _secrets_manager_instance = SecretsManager(project_id)
    
    return _secrets_manager_instance
