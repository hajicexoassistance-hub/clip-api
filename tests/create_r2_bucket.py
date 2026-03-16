import os
import sys
import boto3
from botocore.config import Config
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def create_bucket(bucket_name):
    endpoint_url = os.environ.get('PORTRAITGEN_R2_ENDPOINT')
    access_key_id = os.environ.get('PORTRAITGEN_R2_ACCESS_KEY_ID')
    secret_access_key = os.environ.get('PORTRAITGEN_R2_SECRET_ACCESS_KEY')
    
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    print(f"--- Creating R2 Bucket: {bucket_name} ---")
    try:
        s3.create_bucket(Bucket=bucket_name)
        print(f"SUCCESS: Bucket '{bucket_name}' created.")
    except Exception as e:
        print(f"FAILED: Could not create bucket: {e}")

if __name__ == "__main__":
    create_bucket("portraitgenerator")
