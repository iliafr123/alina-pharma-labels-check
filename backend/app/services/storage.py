import uuid
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


class StorageService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if not self._client:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
            )
        return self._client

    def upload_file(self, file_bytes: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
        client = self._get_client()
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return s3_key

    def download_file(self, s3_key: str) -> bytes:
        client = self._get_client()
        response = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        return response["Body"].read()

    def delete_file(self, s3_key: str) -> None:
        client = self._get_client()
        client.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)

    def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        client = self._get_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
            ExpiresIn=expires_in,
        )

    def test_connection(self) -> bool:
        try:
            client = self._get_client()
            client.head_bucket(Bucket=settings.S3_BUCKET)
            return True
        except ClientError:
            return False

    @staticmethod
    def generate_s3_key(product_id: str, file_type: str, filename: str) -> str:
        uid = str(uuid.uuid4())
        return f"products/{product_id}/{file_type}/{uid}/{filename}"


storage_service = StorageService()
