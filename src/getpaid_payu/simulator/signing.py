"""PayU webhook signing helpers for the simulator plugin."""

from hashlib import sha256


def compute_signature(body: bytes, second_key: str) -> str:
    """Return the PayU callback signature."""
    return sha256(body + second_key.encode()).hexdigest()


def sign_payload(body: bytes, second_key: str) -> str:
    """Return the full PayU signature header value."""
    signature = compute_signature(body, second_key)
    return f"signature={signature};algorithm=SHA-256;sender=checkout"
