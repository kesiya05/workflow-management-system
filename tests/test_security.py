from app.auth import hash_password, verify_password


def test_passwords_are_hashed_and_salted():
    a, b = hash_password("secret1"), hash_password("secret1")
    assert a != b and "secret1" not in a
    assert verify_password("secret1", a) and not verify_password("secret2", a)
