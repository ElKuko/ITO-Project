"""Cloud storage abstraction for file uploads.

Supports:
- Local filesystem (development)
- Cloudflare R2 / S3-compatible storage (production)

Usage:
    from .storage import storage

    # Upload
    url = await storage.upload(file_bytes, filename, content_type)

    # Delete
    await storage.delete(filename)
"""

import os
from typing import Optional

import boto3
from botocore.config import Config


class LocalStorage:
    """Local filesystem storage for development."""

    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    async def upload(self, content: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        """Save file locally and return URL path."""
        filepath = os.path.join(self.upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        return f"/uploads/{filename}"

    async def delete(self, filename: str) -> bool:
        """Delete a file from local storage."""
        filepath = os.path.join(self.upload_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def get_url(self, filename: str) -> str:
        """Get the URL for a file."""
        return f"/uploads/{filename}"


class R2Storage:
    """Cloudflare R2 storage for production."""

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_url: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.public_url = public_url or f"https://{bucket_name}.{account_id}.r2.cloudflarestorage.com"

        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    async def upload(self, content: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        """Upload file to R2 and return public URL."""
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=filename,
            Body=content,
            ContentType=content_type,
        )
        return f"{self.public_url}/{filename}"

    async def delete(self, filename: str) -> bool:
        """Delete a file from R2."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=filename)
            return True
        except Exception:
            return False

    def get_url(self, filename: str) -> str:
        """Get the public URL for a file."""
        return f"{self.public_url}/{filename}"


def get_storage():
    """Factory function to get the appropriate storage backend."""
    r2_account_id = os.getenv("R2_ACCOUNT_ID")
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket = os.getenv("R2_BUCKET_NAME")
    r2_public_url = os.getenv("R2_PUBLIC_URL")

    if all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket]):
        print("Using Cloudflare R2 storage")
        return R2Storage(
            account_id=r2_account_id,
            access_key_id=r2_access_key,
            secret_access_key=r2_secret_key,
            bucket_name=r2_bucket,
            public_url=r2_public_url,
        )
    else:
        from .config import UPLOAD_DIR
        print("Using local filesystem storage")
        return LocalStorage(UPLOAD_DIR)


# Singleton instance
storage = get_storage()
