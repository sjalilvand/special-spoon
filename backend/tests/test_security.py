from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_random_password,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("S3cretPass!123")
    assert h != "S3cretPass!123"
    assert verify_password(h, "S3cretPass!123")
    assert not verify_password(h, "wrong-password")


def test_password_hash_is_argon2id() -> None:
    assert hash_password("x-S3cret-Pass").startswith("$argon2id$")


def test_access_token_roundtrip() -> None:
    token = create_access_token(user_id="00000000-0000-0000-0000-000000000001", auth_version=3)
    payload = decode_access_token(token)
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["ver"] == 3


def test_random_password_length() -> None:
    assert len(generate_random_password()) == 16
