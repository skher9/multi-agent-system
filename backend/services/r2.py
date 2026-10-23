"""Cloudflare R2 file storage (uploaded PRDs).

R2 speaks the S3 API, so we use boto3, AWS's S3 library, pointed at Cloudflare.
Postgres stores only a file's key (its name in the bucket), never the file itself.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

if TYPE_CHECKING:  # type stubs are a dev dependency, used only by pyright
    from mypy_boto3_s3 import S3Client


@dataclass(frozen=True)
class R2Credentials:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str


class R2Storage:
    def __init__(self, creds: R2Credentials, endpoint_url: str | None = None) -> None:
        self.bucket = creds.bucket
        self._s3: S3Client = boto3.client(
            "s3",
            # Per Cloudflare's docs: account endpoint, region "auto".
            # endpoint_url is overridable only so tests can use a fake S3.
            endpoint_url=endpoint_url or f"https://{creds.account_id}.r2.cloudflarestorage.com",
            region_name="auto",
            aws_access_key_id=creds.access_key_id,
            aws_secret_access_key=creds.secret_access_key,
            config=Config(connect_timeout=3, read_timeout=10, retries={"max_attempts": 2}),
        )

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def download(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=key)

    def ping(self) -> None:
        """Raise if the bucket is unreachable or the token can't access it."""
        self._s3.head_bucket(Bucket=self.bucket)
