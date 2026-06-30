from __future__ import annotations


PAGE_ID_NORMALIZE = {
    "personal_page_1": "personal1",
    "personal_page_2": "personal2",
    "passport_page": "passport",
    "travel_page": "travel",
    "travel_companions_page": "travel_companions",
    "previous_travel_page": "travel",
    "previous_us_travel_page": "previous_travel",
    "address_phone_page": "address_phone",
    "work_education_present_page": "work_education_present",
    "work_education_previous_page": "work_education_previous",
    "work_education_additional_page": "work_education_additional",
    "employment_page": "work_education_present",
    "us_contact_page": "us_contact",
    "family_relatives_page": "family_relatives",
    "family_spouse_page": "family_spouse",
    "family_page": "family_relatives",
    "security_part1_page": "security_part1",
    "security_part2_page": "security_part2",
    "security_part3_page": "security_part3",
    "security_part4_page": "security_part4",
    "security_part5_page": "security_part5",
    "security_page": "security_part1",
}

# Reverse mapping: live_form_fill page_key → bundle page_id (prefer the canonical _page form)
_PAGE_ID_REVERSE: dict[str, str] = {}
for _bundle_id, _fill_key in PAGE_ID_NORMALIZE.items():
    if _bundle_id.endswith("_page") and _fill_key not in _PAGE_ID_REVERSE:
        _PAGE_ID_REVERSE[_fill_key] = _bundle_id


def bundle_page_id(fill_page_key: str) -> str | None:
    """Map a live_form_fill page_key (e.g. 'personal1') back to the bundle page_id (e.g. 'personal_page_1')."""
    return _PAGE_ID_REVERSE.get(fill_page_key)
