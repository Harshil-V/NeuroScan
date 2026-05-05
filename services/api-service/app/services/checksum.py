import hashlib


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
