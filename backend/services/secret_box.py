"""Encrypts the tokens users give us (their Jira API token, their GitHub token) before
they go into the database, and decrypts them when a run needs them.

Fernet (from the `cryptography` package): AES-128 in CBC mode plus an HMAC, so a
changed or wrong-key ciphertext fails to open instead of decrypting to garbage. The
key lives only in the environment (INTEGRATIONS_KEY on the API and the worker), never
in the database, so a leaked database dump holds no usable tokens.

Make a key:
    uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken


class SecretBoxError(Exception):
    """A stored token can't be opened (wrong key, or the data was changed)."""


class SecretBox:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())  # raises ValueError on a malformed key

    def seal(self, secret: str) -> bytes:
        return self._fernet.encrypt(secret.encode())

    def open(self, sealed: bytes) -> str:
        try:
            return self._fernet.decrypt(sealed).decode()
        except InvalidToken as exc:
            raise SecretBoxError("can't decrypt a stored token") from exc
