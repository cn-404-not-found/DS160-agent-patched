from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class LocatorSpec:
    strategy: str
    target: str
    input_kind: str
    choice_labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PAGE_LOCATORS: dict[str, dict[str, LocatorSpec]] = {
    # -----------------------------------------------------------------------
    # Personal 1 – Name, DOB, birth place
    # -----------------------------------------------------------------------
    "personal_page_1": {
        "identity_surname": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SURNAME", "text"),
        "identity_given_names": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_GIVEN_NAME", "text"),
        "identity_native_full_name": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_FULL_NAME_NATIVE", "text"),
        "identity_sex": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_GENDER", "select"),
        "identity_marital_status": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_MARITAL_STATUS", "select"),
        "identity_dob_day": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBDay", "select"),
        "identity_dob_month": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBMonth", "select"),
        "identity_dob_year": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDOBYear", "text"),
        "identity_birth_city": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_CITY", "text"),
        "identity_birth_province": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_ST_PROVINCE", "text"),
        "identity_birth_country": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_POB_CNTRY", "select"),
        "identity_other_names": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblOtherNames']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "identity_telecode": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblTelecodeQuestion']", "radio", choice_labels={"true": "Y", "false": "N"}),
    },
    # -----------------------------------------------------------------------
    # Personal 2 – Nationality, IDs
    # -----------------------------------------------------------------------
    "personal_page_2": {
        "identity_nationality": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_NATL", "select"),
        "identity_other_nationality": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblAPP_OTH_NATL_IND']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "identity_perm_res_other": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblPermResOtherCntryInd']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "identity_national_id_na": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_NATIONAL_ID_NA", "checkbox"),
        "identity_ssn_na": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_SSN_NA", "checkbox"),
        "identity_tax_id_na": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_TAX_ID_NA", "checkbox"),
    },
    # -----------------------------------------------------------------------
    # Passport
    # -----------------------------------------------------------------------
    "passport_page": {
        "passport_number": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_PASS_NO", "text"),
        "passport_issuance_country": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_PASS_CNTRY", "select"),
        "passport_issue_day": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlPPTIssuedDay", "select"),
        "passport_issue_month": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlPPTIssuedMonth", "select"),
        "passport_issue_year": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxPPTIssuedYear", "text"),
        "passport_expiry_day": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlPPTExpDay", "select"),
        "passport_expiry_month": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlPPTExpMonth", "select"),
        "passport_expiry_year": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxPPTExpYear", "text"),
        "passport_book_no_na": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_PASS_BOOK_NO_NA", "checkbox"),
    },
    # -----------------------------------------------------------------------
    # Travel
    # -----------------------------------------------------------------------
    "travel_page": {
        "travel_visa_type": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlPurposeOfTrip", "select"),
        "travel_specific_plans": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblSpecificTravel']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "travel_arrival_day": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEDay", "select"),
        "travel_arrival_month": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEMonth", "select"),
        "travel_arrival_year": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxARRIVAL_US_DTEYear", "text"),
        "travel_departure_day": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEDay", "select"),
        "travel_departure_month": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEMonth", "select"),
        "travel_departure_year": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDEPARTURE_US_DTEYear", "text"),
        "travel_us_addr1": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxStreetAddress1", "text"),
        "travel_us_city": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxCity", "text"),
        "travel_us_state": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlTravelState", "select"),
        "travel_us_zip": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbZIPCode", "text"),
        "travel_who_paying": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlWhoIsPaying", "select"),
    },
    # -----------------------------------------------------------------------
    # Travel Companions
    # -----------------------------------------------------------------------
    "travel_companions_page": {
        "travel_companions_ind": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblOtherPersonsTravelingWithYou']", "radio", choice_labels={"true": "Y", "false": "N"}),
    },
    # -----------------------------------------------------------------------
    # Previous US Travel
    # -----------------------------------------------------------------------
    "previous_travel_page": {
        "prev_us_travel_ind": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblPREV_US_TRAVEL_IND']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "prev_visa_ind": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_IND']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "prev_visa_refused_ind": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_REFUSED_IND']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "iv_petition_ind": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblIV_PETITION_IND']", "radio", choice_labels={"true": "Y", "false": "N"}),
    },
    # -----------------------------------------------------------------------
    # Address & Phone
    # -----------------------------------------------------------------------
    "address_phone_page": {
        "home_addr1": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_HOME_ADDR1", "text"),
        "home_tel": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_HOME_TEL", "text"),
        "email_addr": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_EMAIL_ADDR", "text"),
    },
    # -----------------------------------------------------------------------
    # Employment / Education
    # -----------------------------------------------------------------------
    "work_education_present_page": {
        "employment_primary_occupation": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_ddlEmpType", "select"),
        "employment_current_employer_name": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxCURR_EMPL_NAME", "text"),
        "employment_current_employer_addr": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxCURR_EMPL_ADDR1", "text"),
        "employment_monthly_income": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxCURR_EMPL_MONTHLY_INCOME", "text"),
    },
    # -----------------------------------------------------------------------
    # Family
    # -----------------------------------------------------------------------
    "family_relatives_page": {
        "family_father_surname": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_SURNAME", "text"),
        "family_father_given_name": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_GIVEN_NAME", "text"),
        "family_mother_surname": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_SURNAME", "text"),
        "family_mother_given_name": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_GIVEN_NAME", "text"),
    },
    "family_spouse_page": {
        "family_spouse_surname": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxSPOUSE_SURNAME", "text"),
        "family_spouse_given_name": LocatorSpec("css", "#ctl00_SiteContentPlaceHolder_FormView1_tbxSPOUSE_GIVEN_NAME", "text"),
    },
    # -----------------------------------------------------------------------
    # Security Background
    # -----------------------------------------------------------------------
    "security_page": {
        "security_communicable_disease": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblMEDICAL']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_mental_disorder": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblMEDICAL_DIS']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_drug_abuse": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblDRUG_USE']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_arrest_history": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblARRESTED']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_controlled_substance": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblCONTROLLED_SUBSTANCE']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_prostitution": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblPROSTITUTION']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_money_laundering": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblMONEY_LAUNDERING']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_human_trafficking": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblHUMAN_TRAFFICKING']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_terrorist": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblTERRORIST']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_genocide": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblGENOCIDE']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_child_custody": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblCHILD_CUSTODY']", "radio", choice_labels={"true": "Y", "false": "N"}),
        "security_tax_evasion": LocatorSpec("css", "input[name='ctl00$SiteContentPlaceHolder$FormView1$rblTAX_EVASION']", "radio", choice_labels={"true": "Y", "false": "N"}),
    },
}


def resolve_locator(page_id: str, locator_key: str) -> LocatorSpec | None:
    return PAGE_LOCATORS.get(page_id, {}).get(locator_key)
