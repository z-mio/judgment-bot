import hashlib


def get_hash(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()[:8]
