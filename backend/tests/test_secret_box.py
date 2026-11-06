"""Tokens users connect are stored encrypted; a wrong key or changed data can't open them."""

import pytest
from cryptography.fernet import Fernet

from services.secret_box import SecretBox, SecretBoxError


def test_seal_then_open_and_tampering_fails() -> None:
    box = SecretBox(Fernet.generate_key().decode())
    sealed = box.seal("github_pat_abc")
    assert b"github_pat_abc" not in sealed
    assert box.open(sealed) == "github_pat_abc"
    with pytest.raises(SecretBoxError):
        SecretBox(Fernet.generate_key().decode()).open(sealed)  # another key
    with pytest.raises(SecretBoxError):
        box.open(sealed[:-2] + b"xx")  # changed
    with pytest.raises(ValueError):
        SecretBox("not-a-key")
