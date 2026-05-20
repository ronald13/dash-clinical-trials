import os
import boto3
from dotenv import load_dotenv

load_dotenv()


def setup_duckdb_s3(con):
    """Configure DuckDB httpfs for S3 access.

    Local dev:  reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from .env
    EC2:        no env vars → uses IAM instance role via credential chain
                (auto-refreshes, never expires)
    """
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region     = os.getenv('AWS_REGION', 'eu-west-3')

    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    con.execute(f"SET s3_region='{region}';")

    if access_key and secret_key:
        # Local dev: explicit credentials from .env
        con.execute(f"SET s3_access_key_id='{access_key}';")
        con.execute(f"SET s3_secret_access_key='{secret_key}';")
        token = os.getenv('AWS_SESSION_TOKEN', '')
        if token:
            con.execute(f"SET s3_session_token='{token}';")
        print(f"DuckDB S3: explicit credentials (region={region})")
    else:
        # EC2 / IAM role: let DuckDB use the AWS credential provider chain.
        # This picks up the instance role automatically and refreshes tokens
        # before they expire — no manual rotation needed.
        # con.execute("SET s3_use_credential_chain=true;")
        con.execute("INSTALL httpfs;")
        con.execute("LOAD httpfs;")
        con.execute("INSTALL aws;")
        con.execute("LOAD aws;")
        con.execute("CREATE SECRET (TYPE S3, PROVIDER CREDENTIAL_CHAIN);")
        print(f"DuckDB S3: IAM credential chain (region={region})")


def get_boto3_session():
    """Return a boto3 Session (used for any non-DuckDB AWS calls)."""
    region = os.getenv('AWS_REGION', 'eu-west-3')
    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS session OK — ARN: {identity['Arn']}")
        return session
    except Exception as e:
        print(f"AWS session warning: {e}")
        return None


