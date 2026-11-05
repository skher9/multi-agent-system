"""The API login check (api/auth.py), with a real Ed25519 key and real token checks.

Only the key download is faked: tokens are signed here and checked as in production.
"""

import base64
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from api import auth
from api.config import get_settings
from api.main import app

pytestmark = pytest.mark.real_auth

SITE = "https://site.example"
client = TestClient(app)
PRIVATE = Ed25519PrivateKey.generate()


class FakeJwks:
    def get_signing_key_from_jwt(self, token: str) -> Any:
        return PRIVATE.public_key()


@pytest.fixture(autouse=True)
def site(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "website_url", SITE + "/")
    monkeypatch.setattr(auth, "jwks_client", lambda url: FakeJwks())


def token(**overrides: Any) -> str:
    now = int(time.time())
    claims = {"sub": "u1", "email": "a@b.c", "name": "A", "iss": SITE, "aud": SITE}
    claims |= {"iat": now, "exp": now + 900} | overrides
    return jwt.encode(claims, PRIVATE, algorithm="EdDSA")


def call(headers: dict[str, str] | None = None) -> int:
    return client.post("/runs", json={"ticket": "bad"}, headers=headers or {}).status_code


def test_valid_token_gets_past_the_login_check() -> None:
    # 422 = the login passed and the bad ticket key was rejected next
    assert call({"Authorization": f"Bearer {token()}"}) == 422


def test_no_token_is_refused() -> None:
    assert call() == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},  # expired
        {"aud": "https://other.example"},  # for another site
        {"iss": "https://other.example"},  # from another site
    ],
)
def test_bad_tokens_are_refused(overrides: dict[str, Any]) -> None:
    assert call({"Authorization": f"Bearer {token(**overrides)}"}) == 401


def test_token_signed_with_another_key_is_refused() -> None:
    forged = jwt.encode(
        {"sub": "u1", "iss": SITE, "aud": SITE, "iat": 1, "exp": int(time.time()) + 60},
        Ed25519PrivateKey.generate(),
        algorithm="EdDSA",
    )
    assert call({"Authorization": f"Bearer {forged}"}) == 401


def test_unsigned_token_is_refused() -> None:
    # Built by hand, as an attacker would: header says alg "none", no signature
    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    claims = {"sub": "u1", "iss": SITE, "aud": SITE, "iat": 1, "exp": int(time.time()) + 60}
    unsigned = f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}."
    assert call({"Authorization": f"Bearer {unsigned}"}) == 401


def test_without_website_url_the_api_refuses_everyone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "website_url", None)
    assert call({"Authorization": f"Bearer {token()}"}) == 503


def test_health_stays_public() -> None:
    assert client.get("/health").status_code in (200, 503)  # never 401
