import json
import boto3

AWS_REGION: str = "eu-west-3"
PRIVATE_KEY_COLUMN = "PUBLISHER_PRIVATE_KEY"


def fetch_aws_private_key(secret_name: str) -> str:
    """
    Loads a private key from AWS secrets manager.
    """
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=secret_name)
    return str(json.loads(response["SecretString"])[PRIVATE_KEY_COLUMN])
