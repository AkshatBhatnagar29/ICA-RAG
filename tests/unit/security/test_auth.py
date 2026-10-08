import base64
import json
import uuid

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.security.auth import _claims, create_access_token, hash_password, verify_password


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-that-is-long-enough")
    get_settings.cache_clear()


def test_scrypt_password_hash_is_salted_and_verifies() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("scrypt$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_validates_required_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    user_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id, tenant_id)
    claims = _claims(token)
    assert claims["sub"] == str(user_id)
    assert claims["tenant_id"] == str(tenant_id)
    assert claims["typ"] == "access"


@pytest.mark.parametrize("mutate", ["signature", "algorithm", "missing_claim"])
def test_invalid_tokens_fail_closed(monkeypatch: pytest.MonkeyPatch, mutate: str) -> None:
    _configure(monkeypatch)
    token = create_access_token(uuid.uuid4(), uuid.uuid4())
    head, body, signature = token.split(".")
    if mutate == "signature":
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    elif mutate == "algorithm":
        header = {"alg": "none", "typ": "JWT"}
        head = base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode()).rstrip(b"=").decode()
    else:
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        del claims["sub"]
        body = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).rstrip(b"=").decode()
    malformed = f"{head}.{body}.{signature}"
    with pytest.raises(HTTPException) as error:
        _claims(malformed)
    assert error.value.status_code == 401
