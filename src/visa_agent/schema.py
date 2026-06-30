from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApplicantIdentity:
    surname: str
    given_names: str
    native_full_name: str | None
    sex: str
    marital_status: str
    date_of_birth: str
    birth_city: str
    birth_province: str | None
    birth_country: str
    nationality: str
    passport_number: str
    passport_issuance_country: str
    passport_issue_date: str
    passport_expiration_date: str
    passport_book_number: str | None
    other_nationality: bool = False
    permanent_resident_other_country: bool = False
    national_id_number: str | None = None
    us_social_security_number: str | None = None
    us_taxpayer_id_number: str | None = None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TravelPlan:
    visa_class: str
    purpose_notes: str | None
    intended_arrival_date: str | None
    intended_length_of_stay_value: str | None
    intended_length_of_stay_unit: str | None
    payer_name: str | None
    us_contact_name: str | None
    us_contact_organization: str | None
    us_contact_address_line1: str | None
    us_contact_city: str | None
    us_contact_state: str | None
    us_contact_postal_code: str | None
    us_contact_phone: str | None
    us_contact_email: str | None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EmploymentEducation:
    primary_occupation: str | None
    current_employer_name: str | None
    current_employer_address: str | None
    monthly_income_local: str | None
    school_name: str | None
    # Current employment detail
    current_employer_address_line2: str | None = None
    employer_city: str | None = None
    employer_state: str | None = None
    employer_postal_code: str | None = None
    employer_country: str | None = None
    employer_phone: str | None = None
    current_employment_start_date: str | None = None
    current_job_title: str | None = None
    current_job_duties: str | None = None
    current_supervisor_surname: str | None = None
    current_supervisor_given_name: str | None = None
    # Previous employment
    previous_employer_name: str | None = None
    previous_employer_address: str | None = None
    previous_employer_city: str | None = None
    previous_employer_state: str | None = None
    previous_employer_postal_code: str | None = None
    previous_employer_country: str | None = None
    previous_employer_phone: str | None = None
    previous_job_title: str | None = None
    previous_supervisor_surname: str | None = None
    previous_supervisor_given_name: str | None = None
    previous_employment_start_date: str | None = None
    previous_employment_end_date: str | None = None
    previous_job_duties: str | None = None
    # Education
    school_address_line1: str | None = None
    school_city: str | None = None
    school_state: str | None = None
    school_postal_code: str | None = None
    school_country: str | None = None
    major_or_course_of_study: str | None = None
    school_attendance_start_date: str | None = None
    school_attendance_end_date: str | None = None
    # Additional
    languages: str | None = None
    countries_visited: str | None = None
    clan_or_tribe_name: str | None = None
    organization_memberships: str | None = None
    specialized_skills_description: str | None = None
    military_service_country: str | None = None
    military_branch: str | None = None
    military_rank: str | None = None
    military_specialty: str | None = None
    military_service_start_date: str | None = None
    military_service_end_date: str | None = None
    insurgent_organization_explanation: str | None = None
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FamilyContacts:
    father_full_name: str | None
    mother_full_name: str | None
    spouse_full_name: str | None
    us_relative_name: str | None
    us_relative_status: str | None
    father_date_of_birth: str | None = None
    mother_date_of_birth: str | None = None
    spouse_date_of_birth: str | None = None
    spouse_nationality: str | None = None
    spouse_birth_city: str | None = None
    spouse_birth_country: str | None = None
    father_in_us: bool = False
    mother_in_us: bool = False
    has_us_immediate_relatives: bool = False
    has_us_other_relatives: bool = False
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SecurityBackground:
    yes_no_answers: dict[str, bool]
    explanations: dict[str, str]
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PersonalContactInfo:
    home_address_line1: str | None = None
    home_address_line2: str | None = None
    home_city: str | None = None
    home_state: str | None = None
    home_postal_code: str | None = None
    home_country: str | None = None
    primary_phone: str | None = None
    secondary_phone: str | None = None
    work_phone: str | None = None
    email: str | None = None
    social_media_platform: str | None = None
    social_media_handle: str | None = None
    mailing_same_as_home: bool = True
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreviousTravelInfo:
    has_previous_us_travel: bool = False
    last_arrival_date: str | None = None
    last_length_of_stay_value: str | None = None
    last_length_of_stay_unit: str | None = None
    has_previous_us_visa: bool = False
    previous_visa_number: str | None = None
    previous_visa_issue_date: str | None = None
    visa_ever_refused: bool = False
    visa_ever_lost: bool = False
    visa_ever_cancelled: bool = False
    has_immigrant_petition: bool = False
    has_us_driver_license: bool = False
    ten_print_collected: bool = False
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: str
    description: str


@dataclass(frozen=True)
class ApplicantDossier:
    case_id: str
    identity: ApplicantIdentity
    travel_plan: TravelPlan
    employment_education: EmploymentEducation
    family_contacts: FamilyContacts
    security_background: SecurityBackground
    evidence_catalog: dict[str, EvidenceItem]
    personal_contact: PersonalContactInfo | None = None
    previous_travel: PreviousTravelInfo | None = None


def _load_identity(payload: dict[str, Any]) -> ApplicantIdentity:
    return ApplicantIdentity(
        surname=payload["surname"],
        given_names=payload["given_names"],
        native_full_name=payload.get("native_full_name"),
        sex=payload["sex"],
        marital_status=payload["marital_status"],
        date_of_birth=payload["date_of_birth"],
        birth_city=payload["birth_city"],
        birth_province=payload.get("birth_province"),
        birth_country=payload["birth_country"],
        nationality=payload["nationality"],
        passport_number=payload["passport_number"],
        passport_issuance_country=payload["passport_issuance_country"],
        passport_issue_date=payload["passport_issue_date"],
        passport_expiration_date=payload["passport_expiration_date"],
        passport_book_number=payload.get("passport_book_number"),
        other_nationality=bool(payload.get("other_nationality", False)),
        permanent_resident_other_country=bool(payload.get("permanent_resident_other_country", False)),
        national_id_number=payload.get("national_id_number"),
        us_social_security_number=payload.get("us_social_security_number"),
        us_taxpayer_id_number=payload.get("us_taxpayer_id_number"),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_travel_plan(payload: dict[str, Any]) -> TravelPlan:
    return TravelPlan(
        visa_class=payload["visa_class"],
        purpose_notes=payload.get("purpose_notes"),
        intended_arrival_date=payload.get("intended_arrival_date"),
        intended_length_of_stay_value=payload.get("intended_length_of_stay_value"),
        intended_length_of_stay_unit=payload.get("intended_length_of_stay_unit"),
        payer_name=payload.get("payer_name"),
        us_contact_name=payload.get("us_contact_name"),
        us_contact_organization=payload.get("us_contact_organization"),
        us_contact_address_line1=payload.get("us_contact_address_line1"),
        us_contact_city=payload.get("us_contact_city"),
        us_contact_state=payload.get("us_contact_state"),
        us_contact_postal_code=payload.get("us_contact_postal_code"),
        us_contact_phone=payload.get("us_contact_phone"),
        us_contact_email=payload.get("us_contact_email"),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_employment(payload: dict[str, Any]) -> EmploymentEducation:
    return EmploymentEducation(
        primary_occupation=payload.get("primary_occupation"),
        current_employer_name=payload.get("current_employer_name"),
        current_employer_address=payload.get("current_employer_address"),
        monthly_income_local=payload.get("monthly_income_local"),
        school_name=payload.get("school_name"),
        current_employer_address_line2=payload.get("current_employer_address_line2"),
        employer_city=payload.get("employer_city"),
        employer_state=payload.get("employer_state"),
        employer_postal_code=payload.get("employer_postal_code"),
        employer_country=payload.get("employer_country"),
        employer_phone=payload.get("employer_phone"),
        current_employment_start_date=payload.get("current_employment_start_date"),
        current_job_title=payload.get("current_job_title"),
        current_job_duties=payload.get("current_job_duties"),
        current_supervisor_surname=payload.get("current_supervisor_surname"),
        current_supervisor_given_name=payload.get("current_supervisor_given_name"),
        previous_employer_name=payload.get("previous_employer_name"),
        previous_employer_address=payload.get("previous_employer_address"),
        previous_employer_city=payload.get("previous_employer_city"),
        previous_employer_state=payload.get("previous_employer_state"),
        previous_employer_postal_code=payload.get("previous_employer_postal_code"),
        previous_employer_country=payload.get("previous_employer_country"),
        previous_employer_phone=payload.get("previous_employer_phone"),
        previous_job_title=payload.get("previous_job_title"),
        previous_supervisor_surname=payload.get("previous_supervisor_surname"),
        previous_supervisor_given_name=payload.get("previous_supervisor_given_name"),
        previous_employment_start_date=payload.get("previous_employment_start_date"),
        previous_employment_end_date=payload.get("previous_employment_end_date"),
        previous_job_duties=payload.get("previous_job_duties"),
        school_address_line1=payload.get("school_address_line1"),
        school_city=payload.get("school_city"),
        school_state=payload.get("school_state"),
        school_postal_code=payload.get("school_postal_code"),
        school_country=payload.get("school_country"),
        major_or_course_of_study=payload.get("major_or_course_of_study"),
        school_attendance_start_date=payload.get("school_attendance_start_date"),
        school_attendance_end_date=payload.get("school_attendance_end_date"),
        languages=payload.get("languages"),
        countries_visited=payload.get("countries_visited"),
        clan_or_tribe_name=payload.get("clan_or_tribe_name"),
        organization_memberships=payload.get("organization_memberships"),
        specialized_skills_description=payload.get("specialized_skills_description"),
        military_service_country=payload.get("military_service_country"),
        military_branch=payload.get("military_branch"),
        military_rank=payload.get("military_rank"),
        military_specialty=payload.get("military_specialty"),
        military_service_start_date=payload.get("military_service_start_date"),
        military_service_end_date=payload.get("military_service_end_date"),
        insurgent_organization_explanation=payload.get("insurgent_organization_explanation"),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_family(payload: dict[str, Any]) -> FamilyContacts:
    return FamilyContacts(
        father_full_name=payload.get("father_full_name"),
        mother_full_name=payload.get("mother_full_name"),
        spouse_full_name=payload.get("spouse_full_name"),
        us_relative_name=payload.get("us_relative_name"),
        us_relative_status=payload.get("us_relative_status"),
        father_date_of_birth=payload.get("father_date_of_birth"),
        mother_date_of_birth=payload.get("mother_date_of_birth"),
        spouse_date_of_birth=payload.get("spouse_date_of_birth"),
        spouse_nationality=payload.get("spouse_nationality"),
        spouse_birth_city=payload.get("spouse_birth_city"),
        spouse_birth_country=payload.get("spouse_birth_country"),
        father_in_us=bool(payload.get("father_in_us", False)),
        mother_in_us=bool(payload.get("mother_in_us", False)),
        has_us_immediate_relatives=bool(payload.get("has_us_immediate_relatives", False)),
        has_us_other_relatives=bool(payload.get("has_us_other_relatives", False)),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_personal_contact(payload: dict[str, Any] | None) -> PersonalContactInfo | None:
    if not payload:
        return None
    return PersonalContactInfo(
        home_address_line1=payload.get("home_address_line1"),
        home_address_line2=payload.get("home_address_line2"),
        home_city=payload.get("home_city"),
        home_state=payload.get("home_state"),
        home_postal_code=payload.get("home_postal_code"),
        home_country=payload.get("home_country"),
        primary_phone=payload.get("primary_phone"),
        secondary_phone=payload.get("secondary_phone"),
        work_phone=payload.get("work_phone"),
        email=payload.get("email"),
        social_media_platform=payload.get("social_media_platform"),
        social_media_handle=payload.get("social_media_handle"),
        mailing_same_as_home=bool(payload.get("mailing_same_as_home", True)),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_previous_travel(payload: dict[str, Any] | None) -> PreviousTravelInfo | None:
    if not payload:
        return None
    return PreviousTravelInfo(
        has_previous_us_travel=bool(payload.get("has_previous_us_travel", False)),
        last_arrival_date=payload.get("last_arrival_date"),
        last_length_of_stay_value=payload.get("last_length_of_stay_value"),
        last_length_of_stay_unit=payload.get("last_length_of_stay_unit"),
        has_previous_us_visa=bool(payload.get("has_previous_us_visa", False)),
        previous_visa_number=payload.get("previous_visa_number"),
        previous_visa_issue_date=payload.get("previous_visa_issue_date"),
        visa_ever_refused=bool(payload.get("visa_ever_refused", False)),
        visa_ever_lost=bool(payload.get("visa_ever_lost", False)),
        visa_ever_cancelled=bool(payload.get("visa_ever_cancelled", False)),
        has_immigrant_petition=bool(payload.get("has_immigrant_petition", False)),
        has_us_driver_license=bool(payload.get("has_us_driver_license", False)),
        ten_print_collected=bool(payload.get("ten_print_collected", False)),
        source_ids=list(payload.get("source_ids", [])),
    )


def _load_security(payload: dict[str, Any]) -> SecurityBackground:
    return SecurityBackground(
        yes_no_answers=dict(payload.get("yes_no_answers", {})),
        explanations=dict(payload.get("explanations", {})),
        source_ids=list(payload.get("source_ids", [])),
    )


def load_dossier(path: str | Path, passphrase: str | None = None) -> ApplicantDossier:
    text = Path(path).read_text(encoding="utf-8")
    from visa_agent.encryption import decrypt_dossier_json, is_encrypted_dossier

    if is_encrypted_dossier(text):
        if not passphrase:
            raise ValueError("Encrypted dossier requires a passphrase")
        text = decrypt_dossier_json(text, passphrase)
    raw = json.loads(text)
    return load_dossier_payload(raw)


def load_dossier_payload(raw: dict[str, Any]) -> ApplicantDossier:
    evidence_catalog = {
        item["id"]: EvidenceItem(
            id=item["id"],
            kind=item["kind"],
            description=item["description"],
        )
        for item in raw.get("evidence_catalog", [])
    }
    return ApplicantDossier(
        case_id=raw["case_id"],
        identity=_load_identity(raw["identity"]),
        travel_plan=_load_travel_plan(raw["travel_plan"]),
        employment_education=_load_employment(raw["employment_education"]),
        family_contacts=_load_family(raw["family_contacts"]),
        security_background=_load_security(raw["security_background"]),
        evidence_catalog=evidence_catalog,
        personal_contact=_load_personal_contact(raw.get("personal_contact")),
        previous_travel=_load_previous_travel(raw.get("previous_travel")),
    )
