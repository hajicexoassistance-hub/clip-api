import os
import boto3
from botocore.config import Config
from pathlib import Path

class R2StorageService:
    def __init__(self):
        self.endpoint_url = os.environ.get('PORTRAITGEN_R2_ENDPOINT')
        self.access_key_id = os.environ.get('PORTRAITGEN_R2_ACCESS_KEY_ID')
        self.secret_access_key = os.environ.get('PORTRAITGEN_R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.environ.get('PORTRAITGEN_R2_BUCKET_NAME', 'portraitgenerator')
        self.public_domain = os.environ.get('PORTRAITGEN_R2_PUBLIC_DOMAIN', '').rstrip('/')

        if not all([self.endpoint_url, self.access_key_id, self.secret_access_key]):
            print("[STORAGE] Warning: R2 credentials not fully configured in .env")
            self.client = None
        else:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(signature_version='s3v4'),
                region_name='auto' # R2 uses auto
            )

    def upload_file(self, local_path, remote_path):
        """
        Upload a file to R2.
        remote_path should be the key in the bucket (e.g. 'jobs/uuid/clip.mp4')
        """
        if not self.client:
            raise RuntimeError("R2 Client not initialized. Check credentials.")

        local_file = Path(local_path)
        if not local_file.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        print(f"[STORAGE] Uploading {local_path} to R2 as {remote_path}...")
        
        # Determine content type
        content_type = "video/mp4"
        if local_path.endswith(".srt"): content_type = "text/plain"
        elif local_path.endswith(".json"): content_type = "application/json"
        elif local_path.endswith(".mp3"): content_type = "audio/mpeg"

        self.client.upload_file(
            str(local_file),
            self.bucket_name,
            remote_path,
            ExtraArgs={'ContentType': content_type}
        )
        
        url = f"{self.public_domain}/{remote_path}" if self.public_domain else f"{self.endpoint_url}/{self.bucket_name}/{remote_path}"
        print(f"[STORAGE] Upload complete: {url}")
        return url

    def delete_local_file(self, local_path):
        """Helper to delete local file safely."""
        try:
            p = Path(local_path)
            if p.exists():
                p.unlink()
                print(f"[STORAGE] Deleted local file: {local_path}")
        except Exception as e:
            print(f"[STORAGE] Error deleting {local_path}: {e}")

def get_storage_service():
    return R2StorageService()
