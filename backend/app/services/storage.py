import uuid
import functools
import boto3
from app.core.config import settings
from app.core.errors import AppError, storage_error


def _wrap(fn):
    """Turn every boto failure into an AppError that names the real cause.

    Without this an unpaid Selectel account surfaced as an empty `str(exc)` and the
    operator had no way to tell it apart from a wrong bucket name.
    """
    @functools.wraps(fn)
    def inner(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except AppError:
            raise
        except Exception as exc:
            key = ""
            for a in args:
                if isinstance(a, str) and "/" in a:
                    key = a
                    break
            raise storage_error(exc, endpoint=self._endpoint_url,
                                bucket=self._bucket, key=key) from exc
    return inner


class StorageService:
    def __init__(self, endpoint_url: str | None = None, access_key: str | None = None,
                 secret_key: str | None = None, bucket: str | None = None, region: str | None = None):
        # Per-instance credentials; fall back to env settings when not provided.
        self._endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self._access_key = access_key or settings.S3_ACCESS_KEY
        self._secret_key = secret_key or settings.S3_SECRET_KEY
        self._bucket = bucket or settings.S3_BUCKET
        self._region = region or settings.S3_REGION
        self._client = None

    def _get_client(self):
        if not (self._access_key and self._secret_key):
            raise AppError(
                "STORAGE_NOT_CONFIGURED", "Объектное хранилище: не заданы ключи доступа.",
                "Администрирование → Хранилище (Selectel): заполните Access Key и Secret Key.",
                subsystem="storage", provider="selectel" if "selectel" in (self._endpoint_url or "") else "storage",
                http_status=503)
        if not self._client:
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._client

    @_wrap
    def upload_file(self, file_bytes: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
        self._get_client().put_object(Bucket=self._bucket, Key=s3_key, Body=file_bytes, ContentType=content_type)
        return s3_key

    @_wrap
    def download_file(self, s3_key: str) -> bytes:
        response = self._get_client().get_object(Bucket=self._bucket, Key=s3_key)
        return response["Body"].read()

    @_wrap
    def delete_file(self, s3_key: str) -> None:
        self._get_client().delete_object(Bucket=self._bucket, Key=s3_key)

    @_wrap
    def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        return self._get_client().generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": s3_key}, ExpiresIn=expires_in,
        )

    @_wrap
    def test_connection(self) -> bool:
        # Let errors propagate so the admin endpoint can report the real message.
        self._get_client().head_bucket(Bucket=self._bucket)
        return True

    @staticmethod
    def generate_s3_key(product_id: str, file_type: str, filename: str) -> str:
        uid = str(uuid.uuid4())
        return f"products/{product_id}/{file_type}/{uid}/{filename}"


# Backward-compatible env-based singleton.
storage_service = StorageService()


async def get_storage_service(db) -> "StorageService":
    """Build a StorageService from admin-panel config (system_config), falling back to env."""
    from app.services import config_service
    return StorageService(
        endpoint_url=(await config_service.get_config(db, "s3_endpoint_url")) or settings.S3_ENDPOINT_URL,
        access_key=(await config_service.get_config(db, "s3_access_key")) or settings.S3_ACCESS_KEY,
        secret_key=(await config_service.get_config(db, "s3_secret_key")) or settings.S3_SECRET_KEY,
        bucket=(await config_service.get_config(db, "s3_bucket")) or settings.S3_BUCKET,
        region=(await config_service.get_config(db, "s3_region")) or settings.S3_REGION,
    )
