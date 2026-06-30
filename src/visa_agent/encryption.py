"""
AES-256-GCM encryption with Argon2id key derivation for dossier data at rest.

Encrypted file format:
{
  "format": "ds160-encrypted-v1",
  "salt_b64": "<base64>",
  "nonce_b64": "<base64>",
  "ciphertext_b64": "<base64>"
}

Distinguishable from plaintext dossier JSON by the "format" key.
"""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


ENCRYPTED_FORMAT_MARKER = "ds160-encrypted-v1"

# Argon2id parameters
ARGON_MEMORY_COST = 65536  # 64 MB
ARGON_TIME_COST = 3
ARGON_PARALLELISM = 4
ARGON_KEY_LENGTH = 32  # 256 bits for AES-256
GCM_NONCE_LENGTH = 12  # 96 bits, standard for GCM


@dataclass(frozen=True)
class EncryptedBundle:
    """Container for an encrypted dossier."""
    salt_b64: str
    nonce_b64: str
    ciphertext_b64: str


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase using Argon2id."""
    kdf = Argon2id(
        salt=salt,
        length=ARGON_KEY_LENGTH,
        memory_cost=ARGON_MEMORY_COST,
        iterations=ARGON_TIME_COST,
        lanes=ARGON_PARALLELISM,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_dossier_json(plaintext_json: str, passphrase: str) -> str:
    """Encrypt a dossier JSON string. Returns an encrypted JSON string."""
    salt = secrets.token_bytes(16)
    key = derive_key(passphrase, salt)
    nonce = secrets.token_bytes(GCM_NONCE_LENGTH)
    plaintext = plaintext_json.encode("utf-8")

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    payload = {
        "format": ENCRYPTED_FORMAT_MARKER,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }
    return json.dumps(payload, ensure_ascii=False)


def decrypt_dossier_json(encrypted_json: str, passphrase: str) -> str:
    """Decrypt an encrypted dossier JSON string. Returns the original plaintext JSON."""
    payload = json.loads(encrypted_json)

    if payload.get("format") != ENCRYPTED_FORMAT_MARKER:
        raise ValueError("Not an encrypted dossier file")

    salt = base64.b64decode(payload["salt_b64"])
    nonce = base64.b64decode(payload["nonce_b64"])
    ciphertext = base64.b64decode(payload["ciphertext_b64"])

    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def is_encrypted_dossier(data: str | dict[str, Any]) -> bool:
    """Check whether a JSON string or parsed dict is an encrypted dossier."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return False
    return isinstance(data, dict) and data.get("format") == ENCRYPTED_FORMAT_MARKER


def save_encrypted_dossier(plaintext_json: str, passphrase: str, path: Path) -> Path:
    """Encrypt and persist a dossier JSON string to disk."""
    encrypted = encrypt_dossier_json(plaintext_json, passphrase)
    path.write_text(encrypted, encoding="utf-8")
    return path


def load_encrypted_dossier(path: Path, passphrase: str) -> dict[str, Any]:
    """Load and decrypt an encrypted dossier from disk. Returns the parsed dossier dict."""
    encrypted = path.read_text(encoding="utf-8")
    plaintext = decrypt_dossier_json(encrypted, passphrase)
    return json.loads(plaintext)
