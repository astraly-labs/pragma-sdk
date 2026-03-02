import json
import boto3

PRIVATE_KEY_COLUMN = "PUBLISHER_PRIVATE_KEY"


def fetch_aws_private_key(secret_name: str, region: str = "eu-west-3") -> str:
    """
    Loads a private key from AWS secrets manager.

    Args:
        secret_name: The name of the secret in AWS Secrets Manager.
        region: The AWS region where the secret is stored. Defaults to "eu-west-3".

    Returns:
        The private key string.
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return str(json.loads(response["SecretString"])[PRIVATE_KEY_COLUMN])
