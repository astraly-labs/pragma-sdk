import os

from pragma_utils.aws import fetch_aws_private_key


def load_private_key_from_cli_arg(private_key: str) -> str:
    """
    Load the private key either from AWS, environment variable, or from the provided plain value.

    Args:
        private_key: The private key string, either prefixed with 'aws:', 'plain:', or 'env:'.

    Returns:
        str
    """
    if private_key.startswith("aws:"):
        secret_name = private_key.split("aws:", 1)[1]
        return fetch_aws_private_key(secret_name)
    elif private_key.startswith("plain:"):
        return private_key.split("plain:", 1)[1]
    elif private_key.startswith("env:"):
        env_var_name = private_key.split("env:", 1)[1]
        return os.environ[env_var_name]
    else:
        raise ValueError("Private key must be prefixed with either 'aws:', 'plain:', or 'env:'")
