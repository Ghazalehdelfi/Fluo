"""
Load secrets from AWS SSM Parameter Store into environment variables.
Falls back to .env file for local development.
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def load_secrets(prefix="/vocab-practice"):
    """
    Fetch all parameters under the given prefix from SSM Parameter Store
    and set them as environment variables. Silently skips if AWS credentials
    are not available (local dev).
    """
    try:
        ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "ca-central-1"))
        paginator = ssm.get_paginator("get_parameters_by_path")
        for page in paginator.paginate(Path=prefix, WithDecryption=True):
            for param in page["Parameters"]:
                key = param["Name"].rsplit("/", 1)[-1]
                os.environ[key] = param["Value"]
    except (NoCredentialsError, ClientError):
        # No AWS credentials available — local dev, load .env instead
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
