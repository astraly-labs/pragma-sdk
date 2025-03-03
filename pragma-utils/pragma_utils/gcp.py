import json
import os
from google.cloud import secretmanager


PRIVATE_KEY_COLUMN = "PUBLISHER_PRIVATE_KEY"

def fetch_gcp_private_key(secret_name: str) -> str:
    """
    Loads a private key from Google Cloud Secret Manager.
    Args:
        secret_name: Simple name of the secret (e.g., 'xxx-secrets')
    Returns:
        The private key string stored in the secret
    Raises:
        EnvironmentError: If GCP_PROJECT_ID environment variable is not set
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise EnvironmentError("GCP_PROJECT_ID environment variable must be set")

    client = secretmanager.SecretManagerServiceClient()

    # Construct the full secret path
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    response = client.access_secret_version(request={"name": name})
    secret_data = response.payload.data.decode("UTF-8")

    try:
        # Try to parse as JSON if the secret is stored in JSON format
        secret_json = json.loads(secret_data)
        return str(secret_json[PRIVATE_KEY_COLUMN])
    except json.JSONDecodeError:
        # If not JSON, return the raw secret value
        return secret_data
