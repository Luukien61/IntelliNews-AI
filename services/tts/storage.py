"""
TTS Storage Service - S3 upload for generated audio files
"""
import logging
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import settings

logger = logging.getLogger(__name__)


class TTSStorageService:
    """
    Service to upload TTS audio files to SeaweedFS S3 storage.
    Implements singleton pattern.
    """

    _instance: Optional['TTSStorageService'] = None
    _s3_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize S3 client if not already initialized."""
        if self._s3_client is None:
            self._init_s3_client()

    def _init_s3_client(self):
        """Initialize boto3 S3 client with SeaweedFS endpoint."""
        try:
            logger.info(f"Initializing S3 client for endpoint: {settings.s3_endpoint_url}")
            
            self._s3_client = boto3.client(
                's3',
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name='us-east-1'  # Required but value doesn't matter for SeaweedFS
            )
            
            # Ensure bucket exists
            self._ensure_bucket_exists()
            
            logger.info("S3 client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise RuntimeError(f"S3 client initialization failed: {str(e)}")

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self._s3_client.head_bucket(Bucket=settings.s3_bucket_name)
            logger.info(f"Bucket '{settings.s3_bucket_name}' exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"Creating bucket: {settings.s3_bucket_name}")
                try:
                    self._s3_client.create_bucket(Bucket=settings.s3_bucket_name)
                    logger.info(f"Bucket '{settings.s3_bucket_name}' created successfully")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket: {e}")
                raise

    def upload_file(
        self,
        file_path: str,
        object_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        delete_local: bool = True
    ) -> Optional[str]:
        """
        Upload audio file to S3 storage.
        
        Args:
            file_path: Path to local file
            object_name: S3 object name (default: uses filename)
            metadata: Optional metadata dict
            delete_local: Whether to delete local file after upload (default: True)
            
        Returns:
            S3 object key if successful, None otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        if object_name is None:
            object_name = os.path.basename(file_path)

        # Add prefix for organization
        s3_key = f"{settings.s3_audio_prefix}/{object_name}"

        try:
            # Prepare extra args
            extra_args = {
                'ContentType': 'audio/wav'
            }
            
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}

            # Upload file
            logger.info(f"Uploading to S3: {file_path} -> s3://{settings.s3_bucket_name}/{s3_key}")
            self._s3_client.upload_file(
                file_path,
                settings.s3_bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )

            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            logger.info(f"Upload successful: {s3_key} ({file_size:.2f} MB)")

            # Delete local file if requested
            if delete_local:
                try:
                    os.remove(file_path)
                    logger.info(f"Local file deleted: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete local file {file_path}: {e}")

            return s3_key

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            return None

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for accessing audio file.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL or None if failed
        """
        try:
            url = self._s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.s3_bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {s3_key} (expires in {expiration}s)")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    def delete_object(self, s3_key: str) -> bool:
        """
        Delete object from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._s3_client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted S3 object: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete object: {e}")
            return False

    def get_public_url(self, s3_key: str) -> str:
        """
        Get public URL for S3 object (if bucket is public).
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Public URL
        """
        return f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{s3_key}"


# Global storage service instance
tts_storage = TTSStorageService()
