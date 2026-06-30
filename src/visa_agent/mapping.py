from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Callable

from visa_agent.schema import ApplicantDossier


Status = str


@dataclass(frozen=True)
class MappedField:
    field_id: str
    proposed_value: str | bool | None
    confidence: float
    evidence_refs: list[str]
    status: Status
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


Resolver = Callable[[ApplicantDossier], MappedField]


def _missing(field_id: str, evidence_refs: list[str], notes: str) -> MappedField:
    return MappedField(
        field_id=field_id,
        proposed_value=None,
        confidence=0.0,
        evidence_refs=evidence_refs,
        status="blocked",
        notes=notes,
    )


def _ready(
    field_id: str,
    value: str | bool,
    evidence_refs: list[str],
    confidence: float = 0.96,
    notes: str | None = None,
) -> MappedField:
    return MappedField(
        field_id=field_id,
        proposed_value=value,
        confidence=confidence,
        evidence_refs=evidence_refs,
        status="ready",
        notes=notes,
    )


def _review(
    field_id: str,
    value: str | bool | None,
    evidence_refs: list[str],
    notes: str,
    confidence: float = 0.6,
) -> MappedField:
    return MappedField(
        field_id=field_id,
        proposed_value=value,
        confidence=confidence,
        evidence_refs=evidence_refs,
        status="needs_review",
        notes=notes,
    )


def _purpose_of_trip(dossier: ApplicantDossier) -> MappedField:
    travel = dossier.travel_plan
    if not travel.visa_class:
        return _missing(
            "travel.purpose_of_trip",
            travel.source_ids,
            "Visa class is required before selecting the DS-160 trip purpose.",
        )
    if travel.visa_class == "B1/B2":
        return _review(
            "travel.purpose_of_trip",
            travel.visa_class,
            travel.source_ids,
            "Mixed business/tourism cases should be confirmed by an operator before final submission.",
            confidence=0.72,
        )
    return _ready("travel.purpose_of_trip", travel.visa_class, travel.source_ids)


def _security_answer(field_id: str, answer_key: str) -> Resolver:
    def resolve(dossier: ApplicantDossier) -> MappedField:
        security = dossier.security_background
        if answer_key not in security.yes_no_answers:
            return _missing(
                field_id,
                security.source_ids,
                f"Missing security answer for `{answer_key}`.",
            )
        answer = security.yes_no_answers[answer_key]
        if answer:
            explanation = security.explanations.get(answer_key)
            if not explanation:
                return _review(
                    field_id,
                    answer,
                    security.source_ids,
                    f"`{answer_key}` is yes and needs an operator-supplied explanation.",
                    confidence=0.5,
                )
        return _ready(field_id, answer, security.source_ids, confidence=0.93)

    return resolve


def _family_field(field_id: str, value: str | None, evidence_refs: list[str], notes: str) -> MappedField:
    if not value:
        return _review(field_id, None, evidence_refs, notes, confidence=0.4)
    return _ready(field_id, value, evidence_refs, confidence=0.9)


def _resolve_personal_contact(field_id: str, value: str | None, evidence_refs: list[str]) -> MappedField:
    if not value:
        return _missing(field_id, evidence_refs, "Personal contact info not provided in dossier.")
    return _ready(field_id, value, evidence_refs, confidence=0.85)


def _ready_optional(
    field_id: str, value: str | None, evidence_refs: list[str],
    confidence: float = 0.85, notes: str | None = None,
) -> MappedField:
    if not value:
        return _review(field_id, None, evidence_refs,
                       notes or f"{field_id} is not provided; needs manual input.",
                       confidence=0.4)
    return _ready(field_id, value, evidence_refs, confidence=confidence, notes=notes)


def _ready_optional_bool(
    field_id: str, value: bool | None, evidence_refs: list[str],
) -> MappedField:
    if value is None:
        return _review(field_id, None, evidence_refs,
                       f"{field_id} is not provided; needs manual input.",
                       confidence=0.4)
    return _ready(field_id, "YES" if value else "NO", evidence_refs, confidence=0.9)


def _family_field_dob(field_id: str, value: str | None, evidence_refs: list[str], notes: str) -> MappedField:
    if not value:
        return _review(field_id, None, evidence_refs, notes, confidence=0.4)
    return _ready(field_id, value, evidence_refs, confidence=0.85)


def _pc_evidence(dossier: ApplicantDossier) -> list[str]:
    """Evidence refs for personal contact fields; fall back to identity source_ids."""
    if dossier.personal_contact and dossier.personal_contact.source_ids:
        return dossier.personal_contact.source_ids
    return dossier.identity.source_ids


def _pt_evidence(dossier: ApplicantDossier) -> list[str]:
    """Evidence refs for previous travel fields."""
    if dossier.previous_travel and dossier.previous_travel.source_ids:
        return dossier.previous_travel.source_ids
    return dossier.travel_plan.source_ids


def _resolve_previous_employed(dossier: ApplicantDossier) -> MappedField:
    e = dossier.employment_education
    field_id = "employment.previous_employed"
    if e.previous_employer_name:
        return _ready(field_id, "YES", e.source_ids, confidence=0.9)
    return _ready(field_id, "NO", e.source_ids, confidence=0.85,
                  notes="No previous employer recorded; defaulting to NO.")


def _resolve_other_education(dossier: ApplicantDossier) -> MappedField:
    e = dossier.employment_education
    field_id = "employment.other_education"
    if e.school_name:
        return _ready(field_id, "YES", e.source_ids, confidence=0.9)
    return _ready(field_id, "NO", e.source_ids, confidence=0.85,
                  notes="No additional education recorded; defaulting to NO.")


FIELD_RESOLVERS: list[Resolver] = [
    lambda dossier: _ready(
        "identity.surname",
        dossier.identity.surname,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.given_names",
        dossier.identity.given_names,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.native_full_name",
        dossier.identity.native_full_name or "DOES NOT APPLY",
        dossier.identity.source_ids,
        confidence=0.88 if dossier.identity.native_full_name else 0.8,
        notes="Native alphabet field is supplied from PRC passport data when available.",
    ),
    lambda dossier: _ready("identity.sex", dossier.identity.sex, dossier.identity.source_ids),
    lambda dossier: _ready(
        "identity.marital_status",
        dossier.identity.marital_status,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.date_of_birth",
        dossier.identity.date_of_birth,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.birth_city",
        dossier.identity.birth_city,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.birth_country",
        dossier.identity.birth_country,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "identity.nationality",
        dossier.identity.nationality,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "passport.number",
        dossier.identity.passport_number,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "passport.issue_date",
        dossier.identity.passport_issue_date,
        dossier.identity.source_ids,
    ),
    lambda dossier: _ready(
        "passport.expiration_date",
        dossier.identity.passport_expiration_date,
        dossier.identity.source_ids,
    ),
    lambda dossier: _review(
        "passport.book_number",
        dossier.identity.passport_book_number,
        dossier.identity.source_ids,
        "Chinese applicants often do not have a passport book number; confirm whether DS-160 should be marked as not applicable.",
        confidence=0.55,
    ),
    _purpose_of_trip,
    lambda dossier: _ready(
        "travel.intended_arrival_date",
        dossier.travel_plan.intended_arrival_date,
        dossier.travel_plan.source_ids,
        confidence=0.89,
    )
    if dossier.travel_plan.intended_arrival_date
    else _missing(
        "travel.intended_arrival_date",
        dossier.travel_plan.source_ids,
        "The first U.S. arrival date is missing.",
    ),
    lambda dossier: _ready(
        "travel.intended_length_of_stay",
        f"{dossier.travel_plan.intended_length_of_stay_value} {dossier.travel_plan.intended_length_of_stay_unit}",
        dossier.travel_plan.source_ids,
        confidence=0.87,
    )
    if dossier.travel_plan.intended_length_of_stay_value and dossier.travel_plan.intended_length_of_stay_unit
    else _review(
        "travel.intended_length_of_stay",
        None,
        dossier.travel_plan.source_ids,
        "Length of stay needs confirmation.",
    ),
    lambda dossier: _ready(
        "travel.payer_name",
        dossier.travel_plan.payer_name,
        dossier.travel_plan.source_ids,
        confidence=0.85,
    )
    if dossier.travel_plan.payer_name
    else _review(
        "travel.payer_name",
        None,
        dossier.travel_plan.source_ids,
        "The payer should be confirmed before final submission.",
    ),
    lambda dossier: _ready(
        "travel.us_contact_name",
        dossier.travel_plan.us_contact_name,
        dossier.travel_plan.source_ids,
        confidence=0.86,
    )
    if dossier.travel_plan.us_contact_name
    else _missing(
        "travel.us_contact_name",
        dossier.travel_plan.source_ids,
        "A U.S. contact is required for the DS-160 draft.",
    ),
    lambda dossier: _missing(
        "travel.us_contact_phone",
        dossier.travel_plan.source_ids,
        "U.S. contact phone is missing.",
    )
    if not dossier.travel_plan.us_contact_phone
    else _ready(
        "travel.us_contact_phone",
        dossier.travel_plan.us_contact_phone,
        dossier.travel_plan.source_ids,
        confidence=0.82,
    ),
    lambda dossier: _ready(
        "travel.us_contact_address_line1",
        dossier.travel_plan.us_contact_address_line1,
        dossier.travel_plan.source_ids,
        confidence=0.84,
    )
    if dossier.travel_plan.us_contact_address_line1
    else _review(
        "travel.us_contact_address_line1",
        None,
        dossier.travel_plan.source_ids,
        "U.S. contact address line 1 should be confirmed.",
    ),
    lambda dossier: _ready(
        "travel.us_contact_city",
        dossier.travel_plan.us_contact_city,
        dossier.travel_plan.source_ids,
        confidence=0.84,
    )
    if dossier.travel_plan.us_contact_city
    else _review(
        "travel.us_contact_city",
        None,
        dossier.travel_plan.source_ids,
        "U.S. contact city should be confirmed.",
    ),
    lambda dossier: _ready(
        "travel.us_contact_state",
        dossier.travel_plan.us_contact_state,
        dossier.travel_plan.source_ids,
        confidence=0.84,
    )
    if dossier.travel_plan.us_contact_state
    else _review(
        "travel.us_contact_state",
        None,
        dossier.travel_plan.source_ids,
        "U.S. contact state should be confirmed.",
    ),
    lambda dossier: _ready(
        "travel.us_contact_postal_code",
        dossier.travel_plan.us_contact_postal_code,
        dossier.travel_plan.source_ids,
        confidence=0.8,
    )
    if dossier.travel_plan.us_contact_postal_code
    else _review(
        "travel.us_contact_postal_code",
        None,
        dossier.travel_plan.source_ids,
        "U.S. contact postal code should be confirmed.",
    ),
    lambda dossier: _ready(
        "employment.primary_occupation",
        dossier.employment_education.primary_occupation,
        dossier.employment_education.source_ids,
        confidence=0.85,
    )
    if dossier.employment_education.primary_occupation
    else _review(
        "employment.primary_occupation",
        None,
        dossier.employment_education.source_ids,
        "Primary occupation is missing or ambiguous.",
    ),
    lambda dossier: _ready(
        "employment.current_employer_name",
        dossier.employment_education.current_employer_name,
        dossier.employment_education.source_ids,
        confidence=0.88,
    )
    if dossier.employment_education.current_employer_name
    else _review(
        "employment.current_employer_name",
        dossier.employment_education.school_name,
        dossier.employment_education.source_ids,
        "Use school information only after operator confirmation if the applicant is a student.",
    ),
    lambda dossier: _family_field(
        "family.father_full_name",
        dossier.family_contacts.father_full_name,
        dossier.family_contacts.source_ids,
        "Father's full name should be confirmed.",
    ),
    lambda dossier: _family_field(
        "family.mother_full_name",
        dossier.family_contacts.mother_full_name,
        dossier.family_contacts.source_ids,
        "Mother's full name should be confirmed.",
    ),
    _security_answer("security.communicable_disease", "communicable_disease"),
    _security_answer("security.arrest_history", "arrested_or_convicted"),
    # ---- identity extras ----
    lambda dossier: _ready(
        "identity.other_nationality", "NO",
        dossier.identity.source_ids, confidence=0.9,
        notes="Default NO for Chinese applicants without other nationality.",
    ),
    lambda dossier: _ready(
        "identity.permanent_resident_other_country", "NO",
        dossier.identity.source_ids, confidence=0.9,
        notes="Default NO for applicants without foreign permanent residency.",
    ),
    lambda dossier: _ready(
        "identity.national_id_number", "DOES NOT APPLY",
        dossier.identity.source_ids, confidence=0.9,
        notes="Chinese applicants use passport number, not national ID.",
    ),
    lambda dossier: _ready(
        "identity.us_social_security_number", "DOES NOT APPLY",
        dossier.identity.source_ids, confidence=0.9,
        notes="Default DOES NOT APPLY unless applicant has US SSN.",
    ),
    lambda dossier: _ready(
        "identity.us_taxpayer_id_number", "DOES NOT APPLY",
        dossier.identity.source_ids, confidence=0.9,
        notes="Default DOES NOT APPLY unless applicant has US TIN.",
    ),
    # ---- address & phone ----
    lambda dossier: _resolve_personal_contact(
        "address.home_address_line1",
        dossier.personal_contact.home_address_line1 if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "address.city",
        dossier.personal_contact.home_city if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "address.state_province",
        dossier.personal_contact.home_state if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "address.postal_code",
        dossier.personal_contact.home_postal_code if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "address.country",
        dossier.personal_contact.home_country if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "phone.primary_phone",
        dossier.personal_contact.primary_phone if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _ready(
        "phone.secondary_phone", "DOES NOT APPLY",
        _pc_evidence(dossier),
        confidence=0.85,
        notes="Default DOES NOT APPLY unless applicant provides secondary phone.",
    ),
    lambda dossier: _resolve_personal_contact(
        "phone.work_phone",
        dossier.personal_contact.work_phone if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "phone.email",
        dossier.personal_contact.email if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "social.primary_platform",
        dossier.personal_contact.social_media_platform if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    lambda dossier: _resolve_personal_contact(
        "social.primary_handle",
        dossier.personal_contact.social_media_handle if dossier.personal_contact else None,
        _pc_evidence(dossier),
    ),
    # ---- current employment detail ----
    lambda dossier: _ready_optional(
        "employment.current_employer_city", dossier.employment_education.employer_city,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_employer_state", dossier.employment_education.employer_state,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_employer_postal_code", dossier.employment_education.employer_postal_code,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_employer_country", dossier.employment_education.employer_country,
        dossier.employment_education.source_ids, confidence=0.88,
    ),
    lambda dossier: _ready_optional(
        "employment.current_employer_phone", dossier.employment_education.employer_phone,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_employment_start_date", dossier.employment_education.current_employment_start_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_job_duties", dossier.employment_education.current_job_duties,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_supervisor_surname", dossier.employment_education.current_supervisor_surname,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.current_supervisor_given_name", dossier.employment_education.current_supervisor_given_name,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    # ---- previous employment ----
    lambda dossier: _resolve_previous_employed(dossier),
    lambda dossier: _ready_optional(
        "employment.previous_employer_name", dossier.employment_education.previous_employer_name,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employer_city", dossier.employment_education.previous_employer_city,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employer_state", dossier.employment_education.previous_employer_state,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employer_postal_code", dossier.employment_education.previous_employer_postal_code,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employer_country", dossier.employment_education.previous_employer_country,
        dossier.employment_education.source_ids, confidence=0.88,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employer_phone", dossier.employment_education.previous_employer_phone,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_job_title", dossier.employment_education.previous_job_title,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_supervisor_surname", dossier.employment_education.previous_supervisor_surname,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_supervisor_given_name", dossier.employment_education.previous_supervisor_given_name,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employment_start_date", dossier.employment_education.previous_employment_start_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_employment_end_date", dossier.employment_education.previous_employment_end_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.previous_job_duties", dossier.employment_education.previous_job_duties,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    # ---- education ----
    lambda dossier: _resolve_other_education(dossier),
    lambda dossier: _ready_optional(
        "employment.school_address_line1", dossier.employment_education.school_address_line1,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.school_city", dossier.employment_education.school_city,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.major_or_course_of_study", dossier.employment_education.major_or_course_of_study,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.school_attendance_start_date", dossier.employment_education.school_attendance_start_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.school_attendance_end_date", dossier.employment_education.school_attendance_end_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    # ---- additional ----
    lambda dossier: _ready_optional(
        "employment.languages", dossier.employment_education.languages,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.countries_visited", dossier.employment_education.countries_visited,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.clan_or_tribe_name", dossier.employment_education.clan_or_tribe_name,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.organization_memberships", dossier.employment_education.organization_memberships,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.specialized_skills_description", dossier.employment_education.specialized_skills_description,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.military_service_country", dossier.employment_education.military_service_country,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.military_branch", dossier.employment_education.military_branch,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.military_rank", dossier.employment_education.military_rank,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.military_service_start_date", dossier.employment_education.military_service_start_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.military_service_end_date", dossier.employment_education.military_service_end_date,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "employment.insurgent_organization_explanation", dossier.employment_education.insurgent_organization_explanation,
        dossier.employment_education.source_ids, confidence=0.85,
    ),
    # ---- family expansions ----
    lambda dossier: _family_field_dob(
        "family.father_date_of_birth", dossier.family_contacts.father_date_of_birth,
        dossier.family_contacts.source_ids, "Father's date of birth should be confirmed.",
    ),
    lambda dossier: _family_field_dob(
        "family.mother_date_of_birth", dossier.family_contacts.mother_date_of_birth,
        dossier.family_contacts.source_ids, "Mother's date of birth should be confirmed.",
    ),
    lambda dossier: _family_field_dob(
        "family.spouse_date_of_birth", dossier.family_contacts.spouse_date_of_birth,
        dossier.family_contacts.source_ids, "Spouse's date of birth should be confirmed if applicable.",
    ),
    lambda dossier: _ready_optional(
        "family.spouse_nationality", dossier.family_contacts.spouse_nationality,
        dossier.family_contacts.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "family.spouse_birth_city", dossier.family_contacts.spouse_birth_city,
        dossier.family_contacts.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "family.spouse_birth_country", dossier.family_contacts.spouse_birth_country,
        dossier.family_contacts.source_ids, confidence=0.85,
    ),
    lambda dossier: _ready(
        "family.father_in_us", "NO",
        dossier.family_contacts.source_ids, confidence=0.9,
        notes="Default NO unless father lives in the US.",
    ),
    lambda dossier: _ready(
        "family.mother_in_us", "NO",
        dossier.family_contacts.source_ids, confidence=0.9,
        notes="Default NO unless mother lives in the US.",
    ),
    lambda dossier: _ready(
        "family.has_us_immediate_relatives", "NO",
        dossier.family_contacts.source_ids, confidence=0.9,
        notes="Default NO unless applicant has immediate relatives in the US.",
    ),
    lambda dossier: _ready(
        "family.has_us_other_relatives", "NO",
        dossier.family_contacts.source_ids, confidence=0.9,
        notes="Default NO unless applicant has other relatives in the US.",
    ),
    # ---- previous US travel ----
    lambda dossier: _ready_optional_bool(
        "previous_us_travel.has_previous_us_travel",
        dossier.previous_travel.has_previous_us_travel if dossier.previous_travel else None,
        _pt_evidence(dossier),
    ),
    lambda dossier: _ready_optional(
        "previous_us_travel.last_arrival_date",
        dossier.previous_travel.last_arrival_date if dossier.previous_travel else None,
        _pt_evidence(dossier),
        confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "previous_us_travel.last_length_of_stay",
        f"{dossier.previous_travel.last_length_of_stay_value} {dossier.previous_travel.last_length_of_stay_unit}".strip()
        if dossier.previous_travel and dossier.previous_travel.last_length_of_stay_value
        else None,
        _pt_evidence(dossier),
        confidence=0.85,
    ),
    lambda dossier: _ready_optional_bool(
        "previous_us_travel.has_previous_us_visa",
        dossier.previous_travel.has_previous_us_visa if dossier.previous_travel else None,
        _pt_evidence(dossier),
    ),
    lambda dossier: _ready_optional(
        "previous_us_travel.previous_visa_number",
        dossier.previous_travel.previous_visa_number if dossier.previous_travel else None,
        _pt_evidence(dossier),
        confidence=0.85,
    ),
    lambda dossier: _ready_optional(
        "previous_us_travel.previous_visa_issue_date",
        dossier.previous_travel.previous_visa_issue_date if dossier.previous_travel else None,
        _pt_evidence(dossier),
        confidence=0.85,
    ),
    # ---- travel companions ----
    lambda dossier: _ready(
        "travel_companions.has_companions", "NO",
        dossier.travel_plan.source_ids, confidence=0.9,
        notes="Default NO unless applicant travels with companions.",
    ),
]


def map_dossier_to_ds160(dossier: ApplicantDossier) -> list[MappedField]:
    return [resolver(dossier) for resolver in FIELD_RESOLVERS]


def render_mapping_json(mapped_fields: list[MappedField]) -> str:
    return json.dumps([field.to_dict() for field in mapped_fields], indent=2, ensure_ascii=False)
