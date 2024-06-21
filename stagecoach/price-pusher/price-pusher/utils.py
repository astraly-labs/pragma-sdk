import boto3
import json

def load_pvt_key_from_aws(secret_name):
    """
    Loads a private key from AWS secrets manager
    """
    region_name = "eu-west-3"
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    return int(
        json.loads(get_secret_value_response["SecretString"])["PUBLISHER_PRIVATE_KEY"],
        16,
    )

