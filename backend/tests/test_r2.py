"""R2 client against moto, an in-memory fake of the S3 API (no network, no bucket)."""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from services.r2 import R2Credentials, R2Storage

CREDS = R2Credentials(
    account_id="test", access_key_id="test", secret_access_key="test", bucket="uploads"
)


@pytest.fixture
def storage() -> Iterator[R2Storage]:
    with mock_aws():
        # moto intercepts AWS-style URLs, so tests point the client at one.
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="uploads")
        yield R2Storage(CREDS, endpoint_url="https://s3.amazonaws.com")


def test_upload_download_delete(storage: R2Storage) -> None:
    storage.upload("prds/1/v1.md", b"# My PRD", content_type="text/markdown")
    assert storage.download("prds/1/v1.md") == b"# My PRD"

    storage.delete("prds/1/v1.md")
    with pytest.raises(storage._s3.exceptions.NoSuchKey):
        storage.download("prds/1/v1.md")


def test_ping_ok_when_bucket_exists(storage: R2Storage) -> None:
    storage.ping()


def test_ping_fails_for_missing_bucket() -> None:
    with mock_aws():
        missing = R2Storage(
            R2Credentials("test", "test", "test", bucket="nope"),
            endpoint_url="https://s3.amazonaws.com",
        )
        with pytest.raises(Exception, match="404"):
            missing.ping()


def test_default_endpoint_is_the_r2_account_url() -> None:
    s3 = R2Storage(CREDS)._s3
    assert s3.meta.endpoint_url == "https://test.r2.cloudflarestorage.com"
