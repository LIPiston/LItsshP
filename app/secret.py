"""Encode/decode tssh's ``#!! encPassword`` values.

tssh encrypts stored secrets with AES-256-GCM under a constant key that ships
in its source (``THE_UNSAFE_KEY_FOR_ENCODING_ONLY``) and stores
``hex(nonce || ciphertext || tag)``. It is obfuscation, not real secrecy, and
this module mirrors it byte for byte so passwords written by tssh open here and
vice versa.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = b"THE_UNSAFE_KEY_FOR_ENCODING_ONLY"
NONCE_SIZE = 12


def encode_secret(secret: str) -> str:
    nonce = os.urandom(NONCE_SIZE)
    blob = AESGCM(KEY).encrypt(nonce, secret.encode("utf-8"), None)
    return (nonce + blob).hex()


def decode_secret(value: str) -> str | None:
    try:
        raw = bytes.fromhex(value.strip())
    except ValueError:
        return None
    if len(raw) <= NONCE_SIZE:
        return None
    try:
        return AESGCM(KEY).decrypt(raw[:NONCE_SIZE], raw[NONCE_SIZE:], None).decode("utf-8")
    except Exception:
        return None
