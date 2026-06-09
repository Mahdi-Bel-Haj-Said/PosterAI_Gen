"""
Cloudflare R2 Storage implementation.

R2 is S3-compatible, so this uses boto3's S3 client pointed at the R2
endpoint. The bucket is shared with Defendr; every key written here is
already namespaced by `storage.keys.StorageKeys` under R2_KEY_PREFIX.

boto3 is imported lazily so the rest of the storage package (and its tests)
work without boto3 installed.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.storage.base import StorageError, guess_content_type

logger = logging.getLogger(__name__)


class R2Storage:
    """Object storage backed by a Cloudflare R2 bucket."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        s = settings or get_settings()

        missing = [
            name
            for name, value in (
                ("R2_ACCESS_KEY_ID", s.r2_access_key_id),
                ("R2_SECRET_ACCESS_KEY", s.r2_secret_access_key),
                ("R2_ENDPOINT", s.r2_endpoint),
                ("R2_BUCKET", s.r2_bucket),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"R2 storage is not configured. Missing in .env: {', '.join(missing)}."
            )

        self._bucket = s.r2_bucket

        # Lazy import so boto3 is only required when R2 is actually used.
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint,
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",  # R2 ignores region but boto3 requires one.
            config=Config(signature_version="s3v4"),
        )

    def _is_not_found(self, error: Exception) -> bool:
        from botocore.exceptions import ClientError

        if not isinstance(error, ClientError):
            return False
        code = error.response.get("Error", {}).get("Code", "")
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return code in {"NoSuchKey", "404", "NotFound"} or status == 404

    def get_bytes(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if self._is_not_found(e):
                raise FileNotFoundError(f"No object at key: {key}") from e
            raise StorageError(f"R2 get_object failed for {key}: {e}") from e

    def put_bytes(
        self, key: str, data: bytes, *, content_type: Optional[str] = None
    ) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type or guess_content_type(key),
            )
        except ClientError as e:
            raise StorageError(f"R2 put_object failed for {key}: {e}") from e
        logger.info("storage.r2.put", extra={"key": key, "bytes": len(data)})

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            if self._is_not_found(e):
                return False
            raise StorageError(f"R2 head_object failed for {key}: {e}") from e

    def delete(self, key: str) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            raise StorageError(f"R2 delete_object failed for {key}: {e}") from e
        logger.info("storage.r2.delete", extra={"key": key})

    def signed_url(self, key: str, *, expires_in: int = 3600) -> str:
        from botocore.exceptions import ClientError

        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise StorageError(f"R2 presign failed for {key}: {e}") from e

    def list_keys(self, prefix: str) -> List[str]:
        from botocore.exceptions import ClientError

        keys: List[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
        except ClientError as e:
            raise StorageError(f"R2 list failed for prefix {prefix}: {e}") from e
        return keys


__all__ = ["R2Storage"]
