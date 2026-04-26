"""Tenant + API key generation/verification — security-critical math."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from janus.saas.tenant import (
    ApiKeyRecord,
    Tenant,
    generate_api_key,
    parse_api_key,
    verify_api_key,
)


def test_generate_and_verify_roundtrip() -> None:
    pepper = "pepper_secret"
    gen = generate_api_key(pepper)
    assert gen.plaintext.startswith("jns_")
    assert verify_api_key(plaintext=gen.plaintext, expected_hash=gen.hashed_secret, pepper=pepper)


def test_verify_rejects_wrong_pepper() -> None:
    gen = generate_api_key("pepper_a")
    assert not verify_api_key(plaintext=gen.plaintext, expected_hash=gen.hashed_secret, pepper="pepper_b")


def test_verify_rejects_tampered_secret() -> None:
    pepper = "pepper"
    gen = generate_api_key(pepper)
    tampered = gen.plaintext[:-3] + "AAA"
    assert not verify_api_key(plaintext=tampered, expected_hash=gen.hashed_secret, pepper=pepper)


def test_parse_rejects_bad_shape() -> None:
    assert parse_api_key("not-a-key") is None
    assert parse_api_key("jns_short_") is None
    assert parse_api_key("jns_short") is None


def test_short_id_has_fixed_length() -> None:
    gen = generate_api_key("p")
    assert len(gen.short_id) == 8


def test_keys_are_unique() -> None:
    keys = {generate_api_key("p").plaintext for _ in range(200)}
    assert len(keys) == 200


def test_apikey_record_active_predicate() -> None:
    fresh = ApiKeyRecord(
        id="x", tenant_id="t", short_id="abcdefgh",
        hashed_secret="0", label="", scopes=("read",),
        expires_at=None, revoked=False,
    )
    assert fresh.is_active

    revoked = ApiKeyRecord(**{**fresh.__dict__, "revoked": True})
    assert not revoked.is_active

    expired = ApiKeyRecord(**{
        **fresh.__dict__,
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    })
    assert not expired.is_active


def test_apikey_record_scope_predicate() -> None:
    rec = ApiKeyRecord(
        id="x", tenant_id="t", short_id="abcdefgh",
        hashed_secret="0", label="", scopes=("read", "write"),
        expires_at=None, revoked=False,
    )
    assert rec.has_scope("read")
    assert rec.has_scope("write")
    assert not rec.has_scope("admin")

    admin_rec = ApiKeyRecord(**{**rec.__dict__, "scopes": ("admin",)})
    assert admin_rec.has_scope("read")  # admin implies all
    assert admin_rec.has_scope("write")
