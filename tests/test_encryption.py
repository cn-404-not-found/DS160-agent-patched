"""Tests for dossier encryption / decryption."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from visa_agent.encryption import (
    decrypt_dossier_json,
    encrypt_dossier_json,
    is_encrypted_dossier,
    load_encrypted_dossier,
    save_encrypted_dossier,
)


SAMPLE_DOSSIER = {
    "case_id": "CHN-TEST-001",
    "identity": {
        "surname": "ZHANG",
        "given_names": "SAN",
        "native_full_name": None,
        "sex": "MALE",
        "marital_status": "SINGLE",
        "date_of_birth": "1990-01-15",
        "birth_city": "SHANGHAI",
        "birth_province": "SHANGHAI",
        "birth_country": "CHINA",
        "nationality": "CHINA",
        "passport_number": "E12345678",
        "passport_issuance_country": "CHINA",
        "passport_issue_date": "2020-03-01",
        "passport_expiration_date": "2030-03-01",
        "passport_book_number": None,
        "source_ids": ["passport-scan"],
    },
    "travel_plan": {
        "visa_class": "B2",
        "purpose_notes": None,
        "intended_arrival_date": "2025-06-01",
        "intended_length_of_stay_value": "14",
        "intended_length_of_stay_unit": "DAYS",
        "payer_name": "SELF",
        "us_contact_name": None,
        "us_contact_organization": None,
        "us_contact_address_line1": None,
        "us_contact_city": None,
        "us_contact_state": None,
        "us_contact_postal_code": None,
        "us_contact_phone": None,
        "us_contact_email": None,
        "source_ids": ["itinerary"],
    },
    "employment_education": {
        "primary_occupation": "BUSINESSPERSON",
        "current_employer_name": "Shanghai Tech Co",
        "current_employer_address": "100 Nanjing Rd",
        "monthly_income_local": "20000",
        "school_name": None,
        "source_ids": ["employment-letter"],
    },
    "family_contacts": {
        "father_full_name": "ZHANG DA",
        "mother_full_name": "LI FANG",
        "spouse_full_name": None,
        "us_relative_name": None,
        "us_relative_status": None,
        "source_ids": ["family-record"],
    },
    "security_background": {
        "yes_no_answers": {"communicable_disease": False, "arrest_history": False},
        "explanations": {},
        "source_ids": ["self-declaration"],
    },
    "evidence_catalog": [
        {"id": "passport-scan", "kind": "document", "description": "Passport scan"},
    ],
}


class TestEncryptDecrypt:
    def test_roundtrip(self):
        plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
        encrypted = encrypt_dossier_json(plaintext, "my-secret-passphrase")
        assert "ciphertext_b64" in encrypted
        result = decrypt_dossier_json(encrypted, "my-secret-passphrase")
        assert json.loads(result) == SAMPLE_DOSSIER

    def test_wrong_passphrase_fails(self):
        plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
        encrypted = encrypt_dossier_json(plaintext, "correct-passphrase")
        with pytest.raises(Exception):
            decrypt_dossier_json(encrypted, "wrong-passphrase")

    def test_is_encrypted_dossier_detection(self):
        plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
        encrypted = encrypt_dossier_json(plaintext, "passphrase")
        assert is_encrypted_dossier(encrypted)
        assert is_encrypted_dossier(json.loads(encrypted))
        assert not is_encrypted_dossier(plaintext)
        assert not is_encrypted_dossier(SAMPLE_DOSSIER)
        assert not is_encrypted_dossier("not json at all")
        assert not is_encrypted_dossier({"some": "random dict"})

    def test_file_roundtrip(self):
        dest = Path(tempfile.mktemp(suffix=".enc.json"))
        try:
            plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
            save_encrypted_dossier(plaintext, "file-passphrase", dest)
            assert dest.exists()
            assert is_encrypted_dossier(dest.read_text(encoding="utf-8"))
            result = load_encrypted_dossier(dest, "file-passphrase")
            assert result == SAMPLE_DOSSIER
        finally:
            dest.unlink(missing_ok=True)

    def test_wrong_passphrase_file_fails(self):
        dest = Path(tempfile.mktemp(suffix=".enc.json"))
        try:
            plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
            save_encrypted_dossier(plaintext, "right-pass", dest)
            with pytest.raises(Exception):
                load_encrypted_dossier(dest, "wrong-pass")
        finally:
            dest.unlink(missing_ok=True)

    def test_corrupted_file_fails(self):
        dest = Path(tempfile.mktemp(suffix=".enc.json"))
        try:
            dest.write_text('{"format": "ds160-encrypted-v1", "salt_b64": "!!bad!!", "nonce_b64": "x", "ciphertext_b64": "y"}', encoding="utf-8")
            with pytest.raises(Exception):
                load_encrypted_dossier(dest, "passphrase")
        finally:
            dest.unlink(missing_ok=True)

    def test_encrypted_json_not_valid_plain_json(self):
        """Ensure encrypted output does not look like a DS-160 dossier."""
        plaintext = json.dumps(SAMPLE_DOSSIER, ensure_ascii=False)
        encrypted = encrypt_dossier_json(plaintext, "passphrase")
        parsed = json.loads(encrypted)
        assert "case_id" not in parsed
        assert parsed["format"] == "ds160-encrypted-v1"

    def test_empty_dossier_roundtrip(self):
        empty = {
            "case_id": "MIN",
            "identity": {
                "surname": "X",
                "given_names": "Y",
                "sex": "MALE",
                "marital_status": "SINGLE",
                "date_of_birth": "2000-01-01",
                "birth_city": "A",
                "birth_country": "CHINA",
                "nationality": "CHINA",
                "passport_number": "E0",
                "passport_issuance_country": "CHINA",
                "passport_issue_date": "2020-01-01",
                "passport_expiration_date": "2030-01-01",
                "source_ids": ["s1"],
            },
            "travel_plan": {"visa_class": "B2", "source_ids": ["s2"]},
            "employment_education": {"source_ids": []},
            "family_contacts": {"source_ids": []},
            "security_background": {
                "yes_no_answers": {"communicable_disease": False, "arrest_history": False},
                "explanations": {},
                "source_ids": [],
            },
            "evidence_catalog": [],
        }
        plaintext = json.dumps(empty, ensure_ascii=False)
        encrypted = encrypt_dossier_json(plaintext, "test")
        result = json.loads(decrypt_dossier_json(encrypted, "test"))
        assert result == empty
