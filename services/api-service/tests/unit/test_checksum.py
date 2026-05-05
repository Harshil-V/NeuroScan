from app.services.checksum import sha256_of


def test_sha256_of_empty_bytes():
    assert sha256_of(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_of_known_input():
    assert sha256_of(b"hello").startswith("2cf24dba5fb0a30e")


def test_sha256_of_is_hex():
    digest = sha256_of(b"abc")
    assert len(digest) == 64
    int(digest, 16)  # raises if not hex
