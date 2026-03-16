import os
import sys
import boto3
from botocore.config import Config
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def list_buckets():
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
    
    print("--- R2 Buckets ---")
    response = s3.list_buckets()
    for bucket in response['Buckets']:
        print(f"Bucket: {bucket['Name']}")

if __name__ == "__main__":
    list_buckets()
