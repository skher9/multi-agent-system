"""Who is calling the API: a logged-in website user, proven by a short-lived token.

The website (Better Auth's jwt plugin) signs a 15-minute token with EdDSA, holding the
user's id, name and email. The browser sends it as `Authorization: Bearer <token>`.
We check the signature against the website's public keys (/api/auth/jwks), plus the
issuer and audience (both the website's address) and the expiry. The API never sees
passwords or sessions.

Fails closed: with WEBSITE_URL unset, every protected endpoint answers 503.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from api.config import get_settings

ALGORITHMS = ["EdDSA"]  # Better Auth's default; never accept "none" or a symmetric alg


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str


@lru_cache
def jwks_client(url: str) -> jwt.PyJWKClient:
    """Public keys from the website, cached; refetched only for a key id it hasn't seen."""
    return jwt.PyJWKClient(url, cache_keys=True, timeout=5)


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    website = (get_settings().website_url or "").rstrip("/")
    if not website:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API login is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("log in first")
    try:
        key = jwks_client(f"{website}/api/auth/jwks").get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=website,
            issuer=website,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as exc:
        raise _unauthorized("invalid or expired login token") from exc
    return User(id=claims["sub"], email=claims.get("email", ""), name=claims.get("name", ""))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


CurrentUser = Annotated[User, Depends(current_user)]
