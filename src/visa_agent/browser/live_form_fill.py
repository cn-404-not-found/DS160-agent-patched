from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, unquote, urlparse

from visa_agent.browser.cdp_client import CDPWebSocket, find_target_websocket_url, list_debug_targets
from visa_agent.browser.visible_control import VisibleControlResult, _runtime_eval
from visa_agent.schema import ApplicantDossier


PERSONAL1_URL_SUBSTRING = "node=Personal1"
PERSONAL2_URL_SUBSTRING = "node=Personal2"
TRAVEL_URL_SUBSTRING = "node=Travel"
TRAVEL_COMPANIONS_URL_SUBSTRING = "node=TravelCompanions"
PREVIOUS_TRAVEL_URL_SUBSTRING = "node=PreviousUSTravel"
ADDRESS_PHONE_URL_SUBSTRING = "node=AddressPhone"
PASSPORT_URL_SUBSTRING = "node=PptVisa"
US_CONTACT_URL_SUBSTRING = "node=USContact"
WORK_EDUCATION_PRESENT_URL_SUBSTRING = "node=WorkEducation1"
WORK_EDUCATION_PREVIOUS_URL_SUBSTRING = "node=WorkEducation2"
WORK_EDUCATION_ADDITIONAL_URL_SUBSTRING = "node=WorkEducation3"
FAMILY_RELATIVES_URL_SUBSTRING = "node=Relatives"
FAMILY_SPOUSE_URL_SUBSTRING = "node=Spouse"
SECURITY_URL_SUBSTRING = "node=Security"

PAGE_MATCHERS = {
    "personal1": ["node=Personal1", "Personal Information 1"],
    "personal2": ["node=Personal2", "Personal Information 2"],
    "travel": ["node=Travel", "Travel Information"],
    "travel_companions": ["node=TravelCompanions", "Travel Companions"],
    "previous_travel": ["node=PreviousUSTravel", "Previous U.S. Travel Information"],
    "address_phone": ["node=AddressPhone", "Address and Phone Information"],
    "passport": ["node=PptVisa", "node=PassportType", "Passport Information"],
    "us_contact": ["node=USContact", "U.S. Point of Contact Information"],
    "work_education_present": ["node=WorkEducation1", "Present Work/Education/Training Information"],
    "work_education_previous": ["node=WorkEducation2", "Previous Work/Education/Training Information"],
    "work_education_additional": ["node=WorkEducation3", "Additional Work/Education/Training Information"],
    "family_relatives": ["node=Relatives", "Family Information: Relatives"],
    "family_spouse": ["node=Spouse", "Family Information: Spouse"],
    "security_part1": ["node=SecurityandBackground1", "Security and Background: Part 1"],
    "security_part2": ["node=SecurityandBackground2", "Security and Background: Part 2"],
    "security_part3": ["node=SecurityandBackground3", "Security and Background: Part 3"],
    "security_part4": ["node=SecurityandBackground4", "Security and Background: Part 4"],
    "security_part5": ["node=SecurityandBackground5", "Security and Background: Part 5"],
}

# All DS-160 page URL fragments we know about
ALL_PAGE_SUBSTRINGS = {
    key: matchers[0] for key, matchers in PAGE_MATCHERS.items()
}


def _url_node_value(url: str) -> str | None:
    parsed = urlparse(url)
    node = parse_qs(parsed.query).get("node", [None])[0]
    if node:
        return unquote(node)
    marker = "node="
    if marker not in url:
        return None
    tail = url.split(marker, 1)[1]
    return unquote(tail.split("&", 1)[0].split("#", 1)[0])


def _matches_page(page_key: str, url: str, title: str) -> bool:
    node = _url_node_value(url)
    node_matchers = [matcher.split("=", 1)[1] for matcher in PAGE_MATCHERS[page_key] if matcher.startswith("node=")]
    if node is not None and node_matchers:
        return node in node_matchers

    for matcher in PAGE_MATCHERS[page_key]:
        if matcher.startswith("node="):
            if matcher in url:
                return True
            continue
        if matcher in title or matcher in url:
            return True
    return False


def _detect_page_key(url: str, title: str) -> str:
    for key in PAGE_MATCHERS:
        if _matches_page(key, url, title):
            return key
    return "unsupported"


# JS helper functions injected at the start of every fill expression
_JS_HELPERS = (
    "const setText = (sel, val) => { "
    "  const el = document.querySelector(sel); "
    "  if (!el) return false; "
    "  el.value = val; "
    "  el.dispatchEvent(new Event('input', {bubbles:true})); "
    "  el.dispatchEvent(new Event('change', {bubbles:true})); "
    "  return true; "
    "}; "
    "const setSelect = (sel, val) => { "
    "  const el = document.querySelector(sel); "
    "  if (!el) return false; "
    "  el.value = val; "
    "  el.dispatchEvent(new Event('change', {bubbles:true})); "
    "  return true; "
    "}; "
    "const setSelectText = (sel, text) => { "
    "  const el = document.querySelector(sel); "
    "  if (!el) return false; "
    "  const opt = [...el.options].find(o => (o.textContent||'').trim() === text); "
    "  if (!opt) { "
    "    const optPartial = [...el.options].find(o => (o.textContent||'').trim().toLowerCase().includes(text.toLowerCase())); "
    "    if (!optPartial) return false; "
    "    el.value = optPartial.value; "
    "  } else { el.value = opt.value; } "
    "  el.dispatchEvent(new Event('change', {bubbles:true})); "
    "  return true; "
    "}; "
    "const setRadio = (name, val) => { "
    "  const el = document.querySelector(`input[name=\"${name}\"][value=\"${val}\"]`); "
    "  if (!el) return false; "
    "  el.checked = true; "
    "  el.dispatchEvent(new Event('click', {bubbles:true})); "
    "  el.dispatchEvent(new Event('change', {bubbles:true})); "
    "  return true; "
    "}; "
    "const setRadioClick = (name, val) => { "
    "  const el = document.querySelector(`input[name=\"${name}\"][value=\"${val}\"]`); "
    "  if (!el) return false; "
    "  el.click(); "
    "  return true; "
    "}; "
    "const setRadioYesNo = (name, boolVal) => setRadio(name, boolVal ? 'Y' : 'N'); "
    "const setCb = (sel, checked) => { "
    "  const el = document.querySelector(sel); "
    "  if (!el) return false; "
    "  if (el.checked !== checked) el.click(); "
    "  return true; "
    "}; "
    "const r = {filled:[], missing:[]}; "
    "const ok = (name) => r.filled.push(name); "
    "const miss = (name) => r.missing.push(name); "
    "const vr = {checked:[], mismatches:[]}; "
    "const vok = (name) => vr.checked.push(name); "
    "const vmiss = (name, detail) => vr.mismatches.push({field:name, detail}); "
    "const verifyText = (sel, expected) => { "
    "  const el = document.querySelector(sel); if(!el) { vmiss(sel,'ELEMENT_NOT_FOUND'); return false; } "
    "  if(el.value !== expected) { vmiss(sel, `got '${el.value}', expected '${expected}'`); return false; } "
    "  vok(sel); return true; "
    "}; "
    "const verifyRadio = (name, val) => { "
    "  const el = document.querySelector(`input[name=\"${name}\"][value=\"${val}\"]`); "
    "  if(!el || !el.checked) { vmiss(name, `radio ${val} not checked`); return false; } "
    "  vok(name); return true; "
    "}; "
    "const verifyCb = (sel, expected) => { "
    "  const el = document.querySelector(sel); if(!el) { vmiss(sel,'ELEMENT_NOT_FOUND'); return false; } "
    "  if(el.checked !== expected) { vmiss(sel, `got ${el.checked}, expected ${expected}`); return false; } "
    "  vok(sel); return true; "
    "}; "
)


def fill_personal1_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("personal1")
    d = dossier.identity
    dob = d.date_of_birth  # YYYY-MM-DD
    ensure_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblOtherNames', 'N') ? ok('other_names_no') : miss('other_names_no'); "
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblTelecodeQuestion', 'N') ? ok('telecode_no') : miss('telecode_no'); "
        "return r; })()"
    )
    ensure_result = _runtime_eval(ws_url, ensure_expression)
    ensure_payload = dict(ensure_result.get("value") or {})
    time.sleep(1)

    ws_url = _find_page_ws_url("personal1")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SURNAME', {json.dumps(d.surname)}) ? ok('surname') : miss('surname'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_GIVEN_NAME', {json.dumps(d.given_names)}) ? ok('given_names') : miss('given_names'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_FULL_NAME_NATIVE', {json.dumps(d.native_full_name or '')}) ? ok('native_full_name') : miss('native_full_name'); "
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_FULL_NAME_NATIVE_NA', false); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_GENDER', {json.dumps(d.sex)}) ? ok('sex') : miss('sex'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_MARITAL_STATUS', {json.dumps(d.marital_status)}) ? ok('marital_status') : miss('marital_status'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBDay', {json.dumps(dob[8:10])}) ? ok('dob_day') : miss('dob_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBMonth', {json.dumps(_month_abbrev(dob[5:7]))}) ? ok('dob_month') : miss('dob_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxDOBYear', {json.dumps(dob[0:4])}) ? ok('dob_year') : miss('dob_year'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_CITY', {json.dumps(d.birth_city)}) ? ok('birth_city') : miss('birth_city'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_ST_PROVINCE', {json.dumps(d.birth_province or '')}) ? ok('birth_province') : miss('birth_province'); "
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_POB_ST_PROVINCE_NA', false); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_POB_CNTRY', {json.dumps(d.birth_country)}) ? ok('birth_country') : miss('birth_country'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = list(ensure_payload.get("filled") or []) + list(payload.get("filled") or [])
    payload["missing"] = list(ensure_payload.get("missing") or []) + list(payload.get("missing") or [])
    return VisibleControlResult(action="fill_personal1_page", ok=not payload.get("missing"), payload=payload)


def fill_personal2_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("personal2")
    d = dossier.identity
    ensure_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblAPP_OTH_NATL_IND', 'N') ? ok('other_nationality_no') : miss('other_nationality_no'); "
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblPermResOtherCntryInd', 'N') ? ok('perm_res_other_no') : miss('perm_res_other_no'); "
        "return r; })()"
    )
    ensure_result = _runtime_eval(ws_url, ensure_expression)
    ensure_payload = dict(ensure_result.get("value") or {})
    time.sleep(1)

    ws_url = _find_page_ws_url("personal2")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_NATL', {json.dumps(d.nationality)}) ? ok('nationality') : miss('nationality'); "
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_NATIONAL_ID_NA', true) ? ok('national_id_na') : miss('national_id_na'); "
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_SSN_NA', true) ? ok('ssn_na') : miss('ssn_na'); "
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_TAX_ID_NA', true) ? ok('tax_id_na') : miss('tax_id_na'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = list(ensure_payload.get("filled") or []) + list(payload.get("filled") or [])
    payload["missing"] = list(ensure_payload.get("missing") or []) + list(payload.get("missing") or [])
    return VisibleControlResult(action="fill_personal2_page", ok=not payload.get("missing"), payload=payload)


def fill_passport_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("passport")
    d = dossier.identity
    issue = d.passport_issue_date  # YYYY-MM-DD
    expiry = d.passport_expiration_date
    expression = (
        "(() => { "
        + _JS_HELPERS
        + "setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_TYPE', 'REGULAR') ? ok('passport_type') : miss('passport_type'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_NUM', {json.dumps(d.passport_number)}) ? ok('passport_number') : miss('passport_number'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexPPT_BOOK_NUM_NA', true) ? ok('book_no_na') : miss('book_no_na'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_CNTRY', {json.dumps(d.passport_issuance_country)}) ? ok('passport_issued_country') : miss('passport_issued_country'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUED_IN_CITY', {json.dumps(d.birth_city)}) ? ok('passport_issue_city') : miss('passport_issue_city'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUED_IN_STATE', {json.dumps(d.birth_province or '')}) ? ok('passport_issue_state') : miss('passport_issue_state'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_IN_CNTRY', {json.dumps(d.passport_issuance_country)}) ? ok('passport_issue_country_region') : miss('passport_issue_country_region'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_DTEDay', {json.dumps(issue[8:10])}) ? ok('issue_day') : miss('issue_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_DTEMonth', {json.dumps(_month_abbrev(issue[5:7]))}) ? ok('issue_month') : miss('issue_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUEDYear', {json.dumps(issue[0:4])}) ? ok('issue_year') : miss('issue_year'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxPPT_EXPIRE_NA', false) ? ok('expiry_na_off') : miss('expiry_na_off'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_EXPIRE_DTEDay', {json.dumps(expiry[8:10])}) ? ok('expiry_day') : miss('expiry_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_EXPIRE_DTEMonth', {json.dumps(_month_abbrev(expiry[5:7]))}) ? ok('expiry_month') : miss('expiry_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_EXPIREYear', {json.dumps(expiry[0:4])}) ? ok('expiry_year') : miss('expiry_year'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblLOST_PPT_IND', 'N') ? ok('lost_passport_no') : miss('lost_passport_no'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(action="fill_passport_page", ok=not payload.get("missing"), payload=payload)


def fill_travel_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("travel")
    t = dossier.travel_plan
    arrival = t.intended_arrival_date or ""  # YYYY-MM-DD
    # Compute departure date from arrival + length_of_stay_value (days)
    departure = ""
    if arrival and t.intended_length_of_stay_value:
        try:
            from datetime import date, timedelta
            arr_date = date.fromisoformat(arrival)
            dep_date = arr_date + timedelta(days=int(t.intended_length_of_stay_value))
            departure = dep_date.strftime("%Y-%m-%d")
        except Exception:
            pass
    # Map visa_class → dropdown value: "B1/B2" → "B"
    _visa_map = {"B1/B2": "B", "B1": "B", "B2": "B", "F1": "F", "J1": "J", "H1B": "H"}
    visa_val = _visa_map.get(t.visa_class.upper(), t.visa_class[0] if t.visa_class else "B")
    other_purpose_val = _travel_other_purpose_value(t.visa_class)
    payer_val = "P" if t.payer_name else "S"
    # Travel location for "specific plans = Y" mode: use city + state
    travel_location = ", ".join(filter(None, [t.us_contact_city, t.us_contact_state]))

    # Pre-compute JS date strings to avoid repeating logic in both branches
    arrival_js = (
        f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEDay', {json.dumps(arrival[8:10].lstrip('0') or arrival[8:10])}) ? ok('arrival_day') : miss('arrival_day'); "
        f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEMonth', {json.dumps(_month_abbrev(arrival[5:7]))}) ? ok('arrival_month') : miss('arrival_month'); "
        f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxARRIVAL_US_DTEYear', {json.dumps(arrival[0:4])}) ? ok('arrival_year') : miss('arrival_year'); "
        if arrival else "miss('arrival_day'); miss('arrival_month'); miss('arrival_year'); "
    )
    departure_js = (
        f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEDay', {json.dumps(departure[8:10].lstrip('0') or departure[8:10])}) ? ok('departure_day') : miss('departure_day'); "
        f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEMonth', {json.dumps(_month_abbrev(departure[5:7]))}) ? ok('departure_month') : miss('departure_month'); "
        f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxDEPARTURE_US_DTEYear', {json.dumps(departure[0:4])}) ? ok('departure_year') : miss('departure_year'); "
        if departure else "miss('departure_day'); miss('departure_month'); miss('departure_year'); "
    )
    addr_js = (
        f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxStreetAddress1', {json.dumps(t.us_contact_address_line1 or '')}) ? ok('us_addr1') : miss('us_addr1'); "
        f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxCity', {json.dumps(t.us_contact_city or '')}) ? ok('us_city') : miss('us_city'); "
        f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlTravelState', {json.dumps(t.us_contact_state or '')}) ? ok('us_state') : miss('us_state'); "
        f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbZIPCode', {json.dumps(t.us_contact_postal_code or '')}) ? ok('us_zip') : miss('us_zip'); "
    )

    ensure_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblSpecificTravel', 'Y') ? ok('specific_travel_yes') : miss('specific_travel_yes'); "
        "return r; })()"
    )
    ensure_result = _runtime_eval(ws_url, ensure_expression)
    ensure_payload = dict(ensure_result.get("value") or {})
    time.sleep(1)
    _wait_for_selector("travel", "#ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEDay", timeout_s=5)

    ws_url = _find_page_ws_url("travel")
    ensure_visa_expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setSelect('#ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlPurposeOfTrip', {json.dumps(visa_val)}) ? ok('visa_type') : miss('visa_type'); "
        "return r; })()"
    )
    ensure_visa_result = _runtime_eval(ws_url, ensure_visa_expression)
    ensure_visa_payload = dict(ensure_visa_result.get("value") or {})
    time.sleep(1)
    _wait_for_selector("travel", "#ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlOtherPurpose", timeout_s=5)

    ws_url = _find_page_ws_url("travel")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setSelect('#ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlOtherPurpose', {json.dumps(other_purpose_val)}) ? ok('purpose_specify') : miss('purpose_specify'); "
        + arrival_js
        + departure_js
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxArriveCity', {json.dumps(t.us_contact_city or '')}) ? ok('arrive_city') : miss('arrive_city'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxDepartCity', {json.dumps(t.us_contact_city or '')}) ? ok('depart_city') : miss('depart_city'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlTravelLoc_ctl00_tbxSPECTRAVEL_LOCATION', {json.dumps(travel_location)}) ? ok('travel_location') : miss('travel_location'); "
        + addr_js
        # Payer (always fill)
        + f"setSelect('#ctl00_SiteContentPlaceHolder_FormView1_ddlWhoIsPaying', {json.dumps(payer_val)}) ? ok('payer') : miss('payer'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = (
        list(ensure_payload.get("filled") or [])
        + list(ensure_visa_payload.get("filled") or [])
        + list(payload.get("filled") or [])
    )
    payload["missing"] = (
        list(ensure_payload.get("missing") or [])
        + list(ensure_visa_payload.get("missing") or [])
        + list(payload.get("missing") or [])
    )
    return VisibleControlResult(action="fill_travel_page", ok=not payload.get("missing"), payload=payload)


def fill_travel_companions_page(_dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("travel_companions")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblOtherPersonsTravelingWithYou', 'N') ? ok('no_companions') : miss('no_companions'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(action="fill_travel_companions_page", ok=not payload.get("missing"), payload=payload)


def fill_previous_travel_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("previous_travel")
    previous = dossier.previous_travel
    has_previous_us_travel = bool(previous and previous.has_previous_us_travel)
    has_previous_us_visa = bool(previous and previous.has_previous_us_visa)
    prev_visit_date = previous.last_arrival_date if previous and previous.last_arrival_date else ""
    prev_visa_date = previous.previous_visa_issue_date if previous and previous.previous_visa_issue_date else ""
    los = previous.last_length_of_stay_value if previous and previous.last_length_of_stay_value else ""
    los_unit = _previous_travel_los_unit(previous.last_length_of_stay_unit if previous else None)

    ensure_prev_travel_expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_US_TRAVEL_IND', {json.dumps('Y' if has_previous_us_travel else 'N')}) ? ok({json.dumps('prev_us_travel_yes' if has_previous_us_travel else 'prev_us_travel_no')}) : miss('prev_us_travel'); "
        "return r; })()"
    )
    ensure_prev_travel_result = _runtime_eval(ws_url, ensure_prev_travel_expression)
    ensure_prev_travel_payload = dict(ensure_prev_travel_result.get("value") or {})
    if has_previous_us_travel:
        time.sleep(1)
        _wait_for_selector("previous_travel", "#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEDay", timeout_s=5)

    ws_url = _find_page_ws_url("previous_travel")
    ensure_prev_visa_expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_IND', {json.dumps('Y' if has_previous_us_visa else 'N')}) ? ok({json.dumps('prev_visa_yes' if has_previous_us_visa else 'prev_visa_no')}) : miss('prev_visa'); "
        "return r; })()"
    )
    ensure_prev_visa_result = _runtime_eval(ws_url, ensure_prev_visa_expression)
    ensure_prev_visa_payload = dict(ensure_prev_visa_result.get("value") or {})
    if has_previous_us_visa:
        time.sleep(1)
        _wait_for_selector("previous_travel", "#ctl00_SiteContentPlaceHolder_FormView1_ddlPREV_VISA_ISSUED_DTEDay", timeout_s=5)

    ws_url = _find_page_ws_url("previous_travel")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_REFUSED_IND', {json.dumps('Y' if previous and previous.visa_ever_refused else 'N')}) ? ok({json.dumps('prev_visa_refused_yes' if previous and previous.visa_ever_refused else 'prev_visa_refused_no')}) : miss('prev_visa_refused'); "
        + f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblIV_PETITION_IND', {json.dumps('Y' if previous and previous.has_immigrant_petition else 'N')}) ? ok({json.dumps('iv_petition_yes' if previous and previous.has_immigrant_petition else 'iv_petition_no')}) : miss('iv_petition'); "
        # Previous US Travel details
        + (
            f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEDay', {json.dumps(prev_visit_date[8:10].lstrip('0') or prev_visit_date[8:10])}) ? ok('prev_visit_day') : miss('prev_visit_day'); "
            f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEMonth', {json.dumps(_month_abbrev(prev_visit_date[5:7]))}) ? ok('prev_visit_month') : miss('prev_visit_month'); "
            f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_tbxPREV_US_VISIT_DTEYear', {json.dumps(prev_visit_date[0:4])}) ? ok('prev_visit_year') : miss('prev_visit_year'); "
            if has_previous_us_travel and prev_visit_date else ("miss('prev_visit_day'); miss('prev_visit_month'); miss('prev_visit_year'); " if has_previous_us_travel else "")
        )
        + (
            f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_tbxPREV_US_VISIT_LOS', {json.dumps(los)}) ? ok('prev_los_value') : miss('prev_los_value'); "
            f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_LOS_CD', {json.dumps(los_unit)}) ? ok('prev_los_unit') : miss('prev_los_unit'); "
            f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_US_DRIVER_LIC_IND', {json.dumps('Y' if previous and previous.has_us_driver_license else 'N')}) ? ok({json.dumps('driver_lic_yes' if previous and previous.has_us_driver_license else 'driver_lic_no')}) : miss('driver_lic'); "
            if has_previous_us_travel else ""
        )
        # Previous visa details
        + (
            f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPREV_VISA_ISSUED_DTEDay', {json.dumps(prev_visa_date[8:10].lstrip('0') or prev_visa_date[8:10])}) ? ok('prev_visa_day') : miss('prev_visa_day'); "
            f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlPREV_VISA_ISSUED_DTEMonth', {json.dumps(_month_abbrev(prev_visa_date[5:7]))}) ? ok('prev_visa_month') : miss('prev_visa_month'); "
            f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_ISSUED_DTEYear', {json.dumps(prev_visa_date[0:4])}) ? ok('prev_visa_year') : miss('prev_visa_year'); "
            if has_previous_us_visa and prev_visa_date else ("miss('prev_visa_day'); miss('prev_visa_month'); miss('prev_visa_year'); " if has_previous_us_visa else "")
        )
        + (
            "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxPREV_VISA_FOIL_NUMBER_NA', true) ? ok('foil_na') : miss('foil_na'); "
            + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_SAME_TYPE_IND', 'Y') ? ok('same_type_yes') : miss('same_type_yes'); "
            + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_SAME_CNTRY_IND', 'Y') ? ok('same_country_yes') : miss('same_country_yes'); "
            + f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_TEN_PRINT_IND', {json.dumps('Y' if previous and previous.ten_print_collected else 'N')}) ? ok({json.dumps('ten_print_yes' if previous and previous.ten_print_collected else 'ten_print_no')}) : miss('ten_print'); "
            + f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_LOST_IND', {json.dumps('Y' if previous and previous.visa_ever_lost else 'N')}) ? ok({json.dumps('visa_lost_yes' if previous and previous.visa_ever_lost else 'visa_lost_no')}) : miss('visa_lost'); "
            + f"setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblPREV_VISA_CANCELLED_IND', {json.dumps('Y' if previous and previous.visa_ever_cancelled else 'N')}) ? ok({json.dumps('visa_cancelled_yes' if previous and previous.visa_ever_cancelled else 'visa_cancelled_no')}) : miss('visa_cancelled'); "
            if has_previous_us_visa else ""
        )
        + "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = (
        list(ensure_prev_travel_payload.get("filled") or [])
        + list(ensure_prev_visa_payload.get("filled") or [])
        + list(payload.get("filled") or [])
    )
    payload["missing"] = (
        list(ensure_prev_travel_payload.get("missing") or [])
        + list(ensure_prev_visa_payload.get("missing") or [])
        + list(payload.get("missing") or [])
    )
    return VisibleControlResult(action="fill_previous_travel_page", ok=not payload.get("missing"), payload=payload)


def fill_address_phone_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("address_phone")
    data = _address_phone_defaults(dossier)
    if data is None:
        return VisibleControlResult(action="fill_address_phone_page", ok=False,
                                    payload={"filled": [], "missing": ["personal_contact"],
                                             "validations": {"checked": [], "mismatches": []}})
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_LN1', {json.dumps(data['home_addr1'])}) ? ok('home_addr1') : miss('home_addr1'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_LN2', {json.dumps(data['home_addr2'])}) ? ok('home_addr2') : miss('home_addr2'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_CITY', {json.dumps(data['home_city'])}) ? ok('home_city') : miss('home_city'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_STATE', {json.dumps(data['home_state'])}) ? ok('home_state') : miss('home_state'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_ADDR_STATE_NA', false) ? ok('home_state_na_off') : miss('home_state_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_POSTAL_CD', {json.dumps(data['home_postal'])}) ? ok('home_postal') : miss('home_postal'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_ADDR_POSTAL_CD_NA', false) ? ok('home_postal_na_off') : miss('home_postal_na_off'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlCountry', {json.dumps(data['home_country'])}) ? ok('home_country') : miss('home_country'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblMailingAddrSame', 'Y') ? ok('mailing_same_yes') : miss('mailing_same_yes'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_HOME_TEL', {json.dumps(data['primary_phone'])}) ? ok('primary_phone') : miss('primary_phone'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_MOBILE_TEL_NA', true) ? ok('secondary_phone_na') : miss('secondary_phone_na'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_BUS_TEL', {json.dumps(data['work_phone'])}) ? ok('work_phone') : miss('work_phone'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_BUS_TEL_NA', false) ? ok('work_phone_na_off') : miss('work_phone_na_off'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblAddPhone', 'N') ? ok('other_phone_no') : miss('other_phone_no'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_EMAIL_ADDR', {json.dumps(data['email'])}) ? ok('email') : miss('email'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblAddEmail', 'N') ? ok('other_email_no') : miss('other_email_no'); "
        + "setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlSocial_ctl00_ddlSocialMedia', 'NONE') ? ok('social_none') : miss('social_none'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlSocial_ctl00_tbxSocialMediaIdent', {json.dumps('')}) ? ok('social_ident') : miss('social_ident'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblAddSocial', 'N') ? ok('other_platform_no') : miss('other_platform_no'); "
        + f"verifyText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_LN1', {json.dumps(data['home_addr1'])}); "
        + f"verifyText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_CITY', {json.dumps(data['home_city'])}); "
        + f"verifyText('#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_EMAIL_ADDR', {json.dumps(data['email'])}); "
        "return {filled: r.filled, missing: r.missing, validations: vr}; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["_vr"] = payload.pop("validations", {})
    return VisibleControlResult(action="fill_address_phone_page", ok=not payload.get("missing"), payload=payload)


def fill_us_contact_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("us_contact")
    t = dossier.travel_plan
    surname, given_names = _split_contact_name(t.us_contact_name)
    relationship = _us_contact_relationship(t)
    us_phone = _normalize_phone_number(t.us_contact_phone, fallback="4155550100")
    ensure_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxUS_POC_NAME_NA', false) ? ok('contact_name_known') : miss('contact_name_known'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxUS_POC_ORG_NA_IND', false) ? ok('contact_org_known') : miss('contact_org_known'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlUS_POC_REL_TO_APP', {json.dumps(relationship)}) ? ok('contact_relationship') : miss('contact_relationship'); "
        "return r; })()"
    )
    ensure_result = _runtime_eval(ws_url, ensure_expression)
    ensure_payload = dict(ensure_result.get("value") or {})
    time.sleep(1.5)
    _wait_for_selector("us_contact", "#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN1", timeout_s=8)
    _wait_for_selector("us_contact", "#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_HOME_TEL", timeout_s=8)
    _wait_for_selector("us_contact", "#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_EMAIL_ADDR", timeout_s=8)

    ws_url = _find_page_ws_url("us_contact")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_SURNAME', {json.dumps(surname)}) ? ok('contact_surname') : miss('contact_surname'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_GIVEN_NAME', {json.dumps(given_names)}) ? ok('contact_given_names') : miss('contact_given_names'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ORGANIZATION', {json.dumps(t.us_contact_organization or '')}) ? ok('contact_organization') : miss('contact_organization'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN1', {json.dumps(t.us_contact_address_line1 or '')}) ? ok('contact_addr1') : miss('contact_addr1'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN2', {json.dumps('')}) ? ok('contact_addr2') : miss('contact_addr2'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_CITY', {json.dumps(t.us_contact_city or '')}) ? ok('contact_city') : miss('contact_city'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlUS_POC_ADDR_STATE', {json.dumps((t.us_contact_state or '').upper())}) ? ok('contact_state') : miss('contact_state'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_POSTAL_CD', {json.dumps(t.us_contact_postal_code or '')}) ? ok('contact_postal') : miss('contact_postal'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_HOME_TEL', {json.dumps(us_phone)}) ? ok('contact_phone') : miss('contact_phone'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexUS_POC_EMAIL_ADDR_NA', false) ? ok('contact_email_na_off') : miss('contact_email_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_EMAIL_ADDR', {json.dumps(t.us_contact_email or '')}) ? ok('contact_email') : miss('contact_email'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = list(ensure_payload.get("filled") or []) + list(payload.get("filled") or [])
    payload["missing"] = list(ensure_payload.get("missing") or []) + list(payload.get("missing") or [])
    return VisibleControlResult(action="fill_us_contact_page", ok=not payload.get("missing"), payload=payload)


def fill_work_education_present_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("work_education_present")
    e = dossier.employment_education
    defaults = _work_education_present_defaults(dossier)
    ensure_expression = (
        "(() => { "
        + _JS_HELPERS
        + "const el = document.querySelector('#ctl00_SiteContentPlaceHolder_FormView1_ddlPresentOccupation'); "
        + "if (!el) { miss('occupation'); return r; } "
        + f"const opt = [...el.options].find(o => (o.textContent || '').trim() === {json.dumps(defaults['occupation'])}); "
        + "if (!opt) { miss('occupation'); return r; } "
        + "el.value = opt.value; "
        + "el.dispatchEvent(new Event('change', {bubbles:true})); "
        + "ok('occupation'); "
        + "return r; })()"
    )
    ensure_result = _runtime_eval(ws_url, ensure_expression)
    ensure_payload = dict(ensure_result.get("value") or {})
    time.sleep(2.5)
    _wait_for_selector("work_education_present", "#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchName", timeout_s=5)

    ws_url = _find_page_ws_url("work_education_present")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchName', {json.dumps(_sanitize_ds160_name(e.current_employer_name))}) ? ok('employer_name') : miss('employer_name'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchAddr1', {json.dumps(defaults['addr1'])}) ? ok('employer_addr1') : miss('employer_addr1'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchAddr2', {json.dumps(defaults['addr2'])}) ? ok('employer_addr2') : miss('employer_addr2'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchCity', {json.dumps(defaults['city'])}) ? ok('employer_city') : miss('employer_city'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxWORK_EDUC_ADDR_STATE_NA', false) ? ok('employer_state_na_off') : miss('employer_state_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_ADDR_STATE', {json.dumps(defaults['state'])}) ? ok('employer_state') : miss('employer_state'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxWORK_EDUC_ADDR_POSTAL_CD_NA', false) ? ok('employer_postal_na_off') : miss('employer_postal_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_ADDR_POSTAL_CD', {json.dumps(defaults['postal'])}) ? ok('employer_postal') : miss('employer_postal'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_TEL', {json.dumps(defaults['phone'])}) ? ok('employer_phone') : miss('employer_phone'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlEmpSchCountry', {json.dumps(defaults['country'])}) ? ok('employer_country') : miss('employer_country'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlEmpDateFromDay', {json.dumps(defaults['start_date'][8:10].lstrip('0') or defaults['start_date'][8:10])}) ? ok('start_day') : miss('start_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlEmpDateFromMonth', {json.dumps(_month_abbrev(defaults['start_date'][5:7]))}) ? ok('start_month') : miss('start_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpDateFromYear', {json.dumps(defaults['start_date'][0:4])}) ? ok('start_year') : miss('start_year'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxCURR_MONTHLY_SALARY_NA', false) ? ok('salary_na_off') : miss('salary_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxCURR_MONTHLY_SALARY', {json.dumps(e.monthly_income_local or '')}) ? ok('monthly_income') : miss('monthly_income'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxDescribeDuties', {json.dumps(defaults['duties'])}) ? ok('duties') : miss('duties'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = list(ensure_payload.get("filled") or []) + list(payload.get("filled") or [])
    payload["missing"] = list(ensure_payload.get("missing") or []) + list(payload.get("missing") or [])
    return VisibleControlResult(action="fill_work_education_present_page", ok=not payload.get("missing"), payload=payload)


def fill_work_education_previous_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("work_education_previous")
    defaults = _work_education_previous_defaults(dossier)
    ensure_prev_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblPreviouslyEmployed', 'Y') ? ok('previously_employed_yes') : miss('previously_employed_yes'); "
        "return r; })()"
    )
    ensure_prev_result = _runtime_eval(ws_url, ensure_prev_expression)
    ensure_prev_payload = dict(ensure_prev_result.get("value") or {})
    time.sleep(1)

    ws_url = _find_page_ws_url("work_education_previous")
    ensure_educ_expression = (
        "(() => { "
        + _JS_HELPERS
        + "setRadioClick('ctl00$SiteContentPlaceHolder$FormView1$rblOtherEduc', 'Y') ? ok('other_education_yes') : miss('other_education_yes'); "
        "return r; })()"
    )
    ensure_educ_result = _runtime_eval(ws_url, ensure_educ_expression)
    ensure_educ_payload = dict(ensure_educ_result.get("value") or {})
    time.sleep(1)

    ws_url = _find_page_ws_url("work_education_previous")
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerName', {json.dumps(defaults['prev_employer_name'])}) ? ok('prev_employer_name') : miss('prev_employer_name'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerStreetAddress1', {json.dumps(defaults['prev_employer_addr1'])}) ? ok('prev_employer_addr1') : miss('prev_employer_addr1'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerStreetAddress2', {json.dumps(defaults['prev_employer_addr2'])}) ? ok('prev_employer_addr2') : miss('prev_employer_addr2'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerCity', {json.dumps(defaults['prev_employer_city'])}) ? ok('prev_employer_city') : miss('prev_employer_city'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_cbxPREV_EMPL_ADDR_STATE_NA', false) ? ok('prev_employer_state_na_off') : miss('prev_employer_state_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbxPREV_EMPL_ADDR_STATE', {json.dumps(defaults['prev_employer_state'])}) ? ok('prev_employer_state') : miss('prev_employer_state'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_cbxPREV_EMPL_ADDR_POSTAL_CD_NA', false) ? ok('prev_employer_postal_na_off') : miss('prev_employer_postal_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbxPREV_EMPL_ADDR_POSTAL_CD', {json.dumps(defaults['prev_employer_postal'])}) ? ok('prev_employer_postal') : miss('prev_employer_postal'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_DropDownList2', {json.dumps(defaults['prev_employer_country'])}) ? ok('prev_employer_country') : miss('prev_employer_country'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerPhone', {json.dumps(defaults['prev_employer_phone'])}) ? ok('prev_employer_phone') : miss('prev_employer_phone'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbJobTitle', {json.dumps(defaults['prev_job_title'])}) ? ok('prev_job_title') : miss('prev_job_title'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_cbxSupervisorSurname_NA', false) ? ok('prev_supervisor_surname_known') : miss('prev_supervisor_surname_known'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_cbxSupervisorGivenName_NA', false) ? ok('prev_supervisor_given_known') : miss('prev_supervisor_given_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbSupervisorSurname', {json.dumps(defaults['prev_supervisor_surname'])}) ? ok('prev_supervisor_surname') : miss('prev_supervisor_surname'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbSupervisorGivenName', {json.dumps(defaults['prev_supervisor_given'])}) ? ok('prev_supervisor_given') : miss('prev_supervisor_given'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_ddlEmpDateFromDay', {json.dumps(defaults['prev_emp_from'][8:10].lstrip('0') or defaults['prev_emp_from'][8:10])}) ? ok('prev_emp_from_day') : miss('prev_emp_from_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_ddlEmpDateFromMonth', {json.dumps(_month_abbrev(defaults['prev_emp_from'][5:7]))}) ? ok('prev_emp_from_month') : miss('prev_emp_from_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbxEmpDateFromYear', {json.dumps(defaults['prev_emp_from'][0:4])}) ? ok('prev_emp_from_year') : miss('prev_emp_from_year'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_ddlEmpDateToDay', {json.dumps(defaults['prev_emp_to'][8:10].lstrip('0') or defaults['prev_emp_to'][8:10])}) ? ok('prev_emp_to_day') : miss('prev_emp_to_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_ddlEmpDateToMonth', {json.dumps(_month_abbrev(defaults['prev_emp_to'][5:7]))}) ? ok('prev_emp_to_month') : miss('prev_emp_to_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbxEmpDateToYear', {json.dumps(defaults['prev_emp_to'][0:4])}) ? ok('prev_emp_to_year') : miss('prev_emp_to_year'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbDescribeDuties', {json.dumps(defaults['prev_emp_duties'])}) ? ok('prev_emp_duties') : miss('prev_emp_duties'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolName', {json.dumps(defaults['school_name'])}) ? ok('school_name') : miss('school_name'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolAddr1', {json.dumps(defaults['school_addr1'])}) ? ok('school_addr1') : miss('school_addr1'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolAddr2', {json.dumps(defaults['school_addr2'])}) ? ok('school_addr2') : miss('school_addr2'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolCity', {json.dumps(defaults['school_city'])}) ? ok('school_city') : miss('school_city'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_cbxEDUC_INST_ADDR_STATE_NA', false) ? ok('school_state_na_off') : miss('school_state_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxEDUC_INST_ADDR_STATE', {json.dumps(defaults['school_state'])}) ? ok('school_state') : miss('school_state'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_cbxEDUC_INST_POSTAL_CD_NA', false) ? ok('school_postal_na_off') : miss('school_postal_na_off'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxEDUC_INST_POSTAL_CD', {json.dumps(defaults['school_postal'])}) ? ok('school_postal') : miss('school_postal'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_ddlSchoolCountry', {json.dumps(defaults['school_country'])}) ? ok('school_country') : miss('school_country'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolCourseOfStudy', {json.dumps(defaults['school_course'])}) ? ok('school_course') : miss('school_course'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_ddlSchoolFromDay', {json.dumps(defaults['school_from'][8:10].lstrip('0') or defaults['school_from'][8:10])}) ? ok('school_from_day') : miss('school_from_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_ddlSchoolFromMonth', {json.dumps(_month_abbrev(defaults['school_from'][5:7]))}) ? ok('school_from_month') : miss('school_from_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolFromYear', {json.dumps(defaults['school_from'][0:4])}) ? ok('school_from_year') : miss('school_from_year'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_ddlSchoolToDay', {json.dumps(defaults['school_to'][8:10].lstrip('0') or defaults['school_to'][8:10])}) ? ok('school_to_day') : miss('school_to_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_ddlSchoolToMonth', {json.dumps(_month_abbrev(defaults['school_to'][5:7]))}) ? ok('school_to_month') : miss('school_to_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolToYear', {json.dumps(defaults['school_to'][0:4])}) ? ok('school_to_year') : miss('school_to_year'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = (
        list(ensure_prev_payload.get("filled") or [])
        + list(ensure_educ_payload.get("filled") or [])
        + list(payload.get("filled") or [])
    )
    payload["missing"] = (
        list(ensure_prev_payload.get("missing") or [])
        + list(ensure_educ_payload.get("missing") or [])
        + list(payload.get("missing") or [])
    )
    return VisibleControlResult(action="fill_work_education_previous_page", ok=not payload.get("missing"), payload=payload)


def fill_work_education_additional_page(_dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("work_education_additional")
    defaults = _work_education_additional_defaults()
    staged_names = [
        ("ctl00$SiteContentPlaceHolder$FormView1$rblCLAN_TRIBE_IND", "clan_tribe_yes"),
        ("ctl00$SiteContentPlaceHolder$FormView1$rblCOUNTRIES_VISITED_IND", "countries_visited_yes"),
        ("ctl00$SiteContentPlaceHolder$FormView1$rblORGANIZATION_IND", "organization_yes"),
        ("ctl00$SiteContentPlaceHolder$FormView1$rblSPECIALIZED_SKILLS_IND", "specialized_skills_yes"),
        ("ctl00$SiteContentPlaceHolder$FormView1$rblMILITARY_SERVICE_IND", "military_service_yes"),
        ("ctl00$SiteContentPlaceHolder$FormView1$rblINSURGENT_ORG_IND", "insurgent_org_yes"),
    ]
    staged_filled: list[str] = []
    staged_missing: list[str] = []
    for name, label in staged_names:
        staged_expression = (
            "(() => { "
            + _JS_HELPERS
            + f"setRadioClick({json.dumps(name)}, 'Y') ? ok({json.dumps(label)}) : miss({json.dumps(label)}); "
            "return r; })()"
        )
        staged_result = _runtime_eval(ws_url, staged_expression)
        staged_payload = dict(staged_result.get("value") or {})
        staged_filled.extend(staged_payload.get("filled") or [])
        staged_missing.extend(staged_payload.get("missing") or [])
        time.sleep(1)
        ws_url = _find_page_ws_url("work_education_additional")

    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxCLAN_TRIBE_NAME', {json.dumps(defaults['clan_name'])}) ? ok('clan_name') : miss('clan_name'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlLANGUAGES_ctl00_tbxLANGUAGE_NAME', {json.dumps(defaults['language_name'])}) ? ok('language_name') : miss('language_name'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlCountriesVisited_ctl00_ddlCOUNTRIES_VISITED', {json.dumps(defaults['country_visited'])}) ? ok('country_visited') : miss('country_visited'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlORGANIZATIONS_ctl00_tbxORGANIZATION_NAME', {json.dumps(defaults['organization_name'])}) ? ok('organization_name') : miss('organization_name'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxSPECIALIZED_SKILLS_EXPL', {json.dumps(defaults['specialized_skills_expl'])}) ? ok('specialized_skills_expl') : miss('specialized_skills_expl'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_CNTRY', {json.dumps(defaults['military_country'])}) ? ok('military_country') : miss('military_country'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_tbxMILITARY_SVC_BRANCH', {json.dumps(defaults['military_branch'])}) ? ok('military_branch') : miss('military_branch'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_tbxMILITARY_SVC_RANK', {json.dumps(defaults['military_rank'])}) ? ok('military_rank') : miss('military_rank'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_tbxMILITARY_SVC_SPECIALTY', {json.dumps(defaults['military_specialty'])}) ? ok('military_specialty') : miss('military_specialty'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_FROMDay', {json.dumps(defaults['military_from'][8:10].lstrip('0') or defaults['military_from'][8:10])}) ? ok('military_from_day') : miss('military_from_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_FROMMonth', {json.dumps(_month_abbrev(defaults['military_from'][5:7]))}) ? ok('military_from_month') : miss('military_from_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_tbxMILITARY_SVC_FROMYear', {json.dumps(defaults['military_from'][0:4])}) ? ok('military_from_year') : miss('military_from_year'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_TODay', {json.dumps(defaults['military_to'][8:10].lstrip('0') or defaults['military_to'][8:10])}) ? ok('military_to_day') : miss('military_to_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_TOMonth', {json.dumps(_month_abbrev(defaults['military_to'][5:7]))}) ? ok('military_to_month') : miss('military_to_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_tbxMILITARY_SVC_TOYear', {json.dumps(defaults['military_to'][0:4])}) ? ok('military_to_year') : miss('military_to_year'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxINSURGENT_ORG_EXPL', {json.dumps(defaults['insurgent_expl'])}) ? ok('insurgent_expl') : miss('insurgent_expl'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    payload["filled"] = staged_filled + list(payload.get("filled") or [])
    payload["missing"] = staged_missing + list(payload.get("missing") or [])
    return VisibleControlResult(action="fill_work_education_additional_page", ok=not payload.get("missing"), payload=payload)


def fill_family_relatives_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("family_relatives")
    f = dossier.family_contacts
    father_surname, father_given = _split_name_first_surname(f.father_full_name)
    mother_surname, mother_given = _split_name_first_surname(f.mother_full_name)
    father_dob = _family_relative_dob("father", dossier) or ""
    mother_dob = _family_relative_dob("mother", dossier) or ""
    father_surname_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_SURNAME_UNK_IND', false) ? ok('father_surname_known') : miss('father_surname_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_SURNAME', {json.dumps(father_surname)}) ? ok('father_surname') : miss('father_surname'); "
        if father_surname else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_SURNAME_UNK_IND', true) ? ok('father_surname_unknown') : miss('father_surname_unknown'); "
    )
    father_given_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_GIVEN_NAME_UNK_IND', false) ? ok('father_given_known') : miss('father_given_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_GIVEN_NAME', {json.dumps(father_given)}) ? ok('father_given') : miss('father_given'); "
        if father_given else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_GIVEN_NAME_UNK_IND', true) ? ok('father_given_unknown') : miss('father_given_unknown'); "
    )
    father_dob_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_DOB_UNK_IND', false) ? ok('father_dob_known') : miss('father_dob_known'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlFathersDOBDay', {json.dumps(father_dob[8:10])}) ? ok('father_dob_day') : miss('father_dob_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlFathersDOBMonth', {json.dumps(_month_abbrev(father_dob[5:7]))}) ? ok('father_dob_month') : miss('father_dob_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxFathersDOBYear', {json.dumps(father_dob[0:4])}) ? ok('father_dob_year') : miss('father_dob_year'); "
        if father_dob else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_DOB_UNK_IND', true) ? ok('father_dob_unknown') : miss('father_dob_unknown'); "
    )
    mother_surname_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_SURNAME_UNK_IND', false) ? ok('mother_surname_known') : miss('mother_surname_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_SURNAME', {json.dumps(mother_surname)}) ? ok('mother_surname') : miss('mother_surname'); "
        if mother_surname else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_SURNAME_UNK_IND', true) ? ok('mother_surname_unknown') : miss('mother_surname_unknown'); "
    )
    mother_given_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_GIVEN_NAME_UNK_IND', false) ? ok('mother_given_known') : miss('mother_given_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_GIVEN_NAME', {json.dumps(mother_given)}) ? ok('mother_given') : miss('mother_given'); "
        if mother_given else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_GIVEN_NAME_UNK_IND', true) ? ok('mother_given_unknown') : miss('mother_given_unknown'); "
    )
    mother_dob_js = (
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_DOB_UNK_IND', false) ? ok('mother_dob_known') : miss('mother_dob_known'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlMothersDOBDay', {json.dumps(mother_dob[8:10])}) ? ok('mother_dob_day') : miss('mother_dob_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlMothersDOBMonth', {json.dumps(_month_abbrev(mother_dob[5:7]))}) ? ok('mother_dob_month') : miss('mother_dob_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxMothersDOBYear', {json.dumps(mother_dob[0:4])}) ? ok('mother_dob_year') : miss('mother_dob_year'); "
        if mother_dob else
        "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_DOB_UNK_IND', true) ? ok('mother_dob_unknown') : miss('mother_dob_unknown'); "
    )
    expression = (
        "(() => { "
        + _JS_HELPERS
        + father_surname_js
        + father_given_js
        + father_dob_js
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblFATHER_LIVE_IN_US_IND', 'N') ? ok('father_in_us_no') : miss('father_in_us_no'); "
        + mother_surname_js
        + mother_given_js
        + mother_dob_js
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblMOTHER_LIVE_IN_US_IND', 'N') ? ok('mother_in_us_no') : miss('mother_in_us_no'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblUS_IMMED_RELATIVE_IND', 'N') ? ok('immediate_relatives_no') : miss('immediate_relatives_no'); "
        + "setRadio('ctl00$SiteContentPlaceHolder$FormView1$rblUS_OTHER_RELATIVE_IND', 'N') ? ok('other_relatives_no') : miss('other_relatives_no'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(action="fill_family_relatives_page", ok=not payload.get("missing"), payload=payload)


def fill_family_spouse_page(dossier: ApplicantDossier) -> VisibleControlResult:
    ws_url = _find_page_ws_url("family_spouse")
    f = dossier.family_contacts
    spouse_surname, spouse_given = _split_name_first_surname(f.spouse_full_name)
    spouse = _family_spouse_defaults(dossier)
    expression = (
        "(() => { "
        + _JS_HELPERS
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxSpouseSurname', {json.dumps(spouse_surname)}) ? ok('spouse_surname') : miss('spouse_surname'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxSpouseGivenName', {json.dumps(spouse_given)}) ? ok('spouse_given') : miss('spouse_given'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBDay', {json.dumps(spouse['dob'][8:10])}) ? ok('spouse_dob_day') : miss('spouse_dob_day'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlDOBMonth', {json.dumps(_month_abbrev(spouse['dob'][5:7]))}) ? ok('spouse_dob_month') : miss('spouse_dob_month'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxDOBYear', {json.dumps(spouse['dob'][0:4])}) ? ok('spouse_dob_year') : miss('spouse_dob_year'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlSpouseNatDropDownList', {json.dumps(spouse['nationality'])}) ? ok('spouse_nationality') : miss('spouse_nationality'); "
        + "setCb('#ctl00_SiteContentPlaceHolder_FormView1_cbexSPOUSE_POB_CITY_NA', false) ? ok('spouse_birth_city_known') : miss('spouse_birth_city_known'); "
        + f"setText('#ctl00_SiteContentPlaceHolder_FormView1_tbxSpousePOBCity', {json.dumps(spouse['birth_city'])}) ? ok('spouse_birth_city') : miss('spouse_birth_city'); "
        + f"setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlSpousePOBCountry', {json.dumps(spouse['birth_country'])}) ? ok('spouse_birth_country') : miss('spouse_birth_country'); "
        + "setSelectText('#ctl00_SiteContentPlaceHolder_FormView1_ddlSpouseAddressType', 'Same as Home Address') ? ok('spouse_address_type') : miss('spouse_address_type'); "
        "return r; })()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(action="fill_family_spouse_page", ok=not payload.get("missing"), payload=payload)


def fill_security_part1_page(dossier: ApplicantDossier) -> VisibleControlResult:
    return _fill_security_questions(
        "security_part1",
        [
            ("communicable_disease", "ctl00$SiteContentPlaceHolder$FormView1$rblDisease", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDisease"),
            ("physical_or_mental_disorder", "ctl00$SiteContentPlaceHolder$FormView1$rblDisorder", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDisorder"),
            ("drug_abuser", "ctl00$SiteContentPlaceHolder$FormView1$rblDruguser", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDruguser"),
        ],
        dossier,
    )


def fill_security_part2_page(dossier: ApplicantDossier) -> VisibleControlResult:
    return _fill_security_questions(
        "security_part2",
        [
            ("arrested_or_convicted", "ctl00$SiteContentPlaceHolder$FormView1$rblArrested", "#ctl00_SiteContentPlaceHolder_FormView1$t bxArrested".replace(" ", "")),
            ("controlled_substances", "ctl00$SiteContentPlaceHolder$FormView1$rblControlledSubstances", "#ctl00_SiteContentPlaceHolder_FormView1_tbxControlledSubstances"),
            ("prostitution_or_vice", "ctl00$SiteContentPlaceHolder$FormView1$rblProstitution", "#ctl00_SiteContentPlaceHolder_FormView1_tbxProstitution"),
            ("money_laundering", "ctl00$SiteContentPlaceHolder$FormView1$rblMoneyLaundering", "#ctl00_SiteContentPlaceHolder_FormView1_tbxMoneyLaundering"),
            ("human_trafficking", "ctl00$SiteContentPlaceHolder$FormView1$rblHumanTrafficking", "#ctl00_SiteContentPlaceHolder_FormView1_tbxHumanTrafficking"),
            ("assisted_severe_trafficking", "ctl00$SiteContentPlaceHolder$FormView1$rblAssistedSevereTrafficking", "#ctl00_SiteContentPlaceHolder_FormView1_tbxAssistedSevereTrafficking"),
            ("human_trafficking_related", "ctl00$SiteContentPlaceHolder$FormView1$rblHumanTraffickingRelated", "#ctl00_SiteContentPlaceHolder_FormView1_tbxHumanTraffickingRelated"),
        ],
        dossier,
    )


def fill_security_part3_page(dossier: ApplicantDossier) -> VisibleControlResult:
    return _fill_security_questions(
        "security_part3",
        [
            ("illegal_activity", "ctl00$SiteContentPlaceHolder$FormView1$rblIllegalActivity", "#ctl00_SiteContentPlaceHolder_FormView1_tbxIllegalActivity"),
            ("terrorist_activity", "ctl00$SiteContentPlaceHolder$FormView1$rblTerroristActivity", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTerroristActivity"),
            ("terrorist_support", "ctl00$SiteContentPlaceHolder$FormView1$rblTerroristSupport", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTerroristSupport"),
            ("terrorist_org", "ctl00$SiteContentPlaceHolder$FormView1$rblTerroristOrg", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTerroristOrg"),
            ("terrorist_rel", "ctl00$SiteContentPlaceHolder$FormView1$rblTerroristRel", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTerroristRel"),
            ("genocide", "ctl00$SiteContentPlaceHolder$FormView1$rblGenocide", "#ctl00_SiteContentPlaceHolder_FormView1_tbxGenocide"),
            ("torture", "ctl00$SiteContentPlaceHolder$FormView1$rblTorture", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTorture"),
            ("extrajudicial_violence", "ctl00$SiteContentPlaceHolder$FormView1$rblExViolence", "#ctl00_SiteContentPlaceHolder_FormView1_tbxExViolence"),
            ("child_soldier", "ctl00$SiteContentPlaceHolder$FormView1$rblChildSoldier", "#ctl00_SiteContentPlaceHolder_FormView1_tbxChildSoldier"),
            ("religious_freedom", "ctl00$SiteContentPlaceHolder$FormView1$rblReligiousFreedom", "#ctl00_SiteContentPlaceHolder_FormView1_tbxReligiousFreedom"),
            ("population_controls", "ctl00$SiteContentPlaceHolder$FormView1$rblPopulationControls", "#ctl00_SiteContentPlaceHolder_FormView1_tbxPopulationControls"),
            ("transplant", "ctl00$SiteContentPlaceHolder$FormView1$rblTransplant", "#ctl00_SiteContentPlaceHolder_FormView1_tbxTransplant"),
        ],
        dossier,
    )


def fill_security_part4_page(dossier: ApplicantDossier) -> VisibleControlResult:
    return _fill_security_questions(
        "security_part4",
        [
            ("removal_hearing", "ctl00$SiteContentPlaceHolder$FormView1$rblRemovalHearing", "#ctl00_SiteContentPlaceHolder_FormView1_tbxRemovalHearing"),
            ("immigration_fraud", "ctl00$SiteContentPlaceHolder$FormView1$rblImmigrationFraud", "#ctl00_SiteContentPlaceHolder_FormView1_tbxImmigrationFraud"),
            ("fail_to_attend", "ctl00$SiteContentPlaceHolder$FormView1$rblFailToAttend", "#ctl00_SiteContentPlaceHolder_FormView1_tbxFailToAttend"),
            ("visa_violation", "ctl00$SiteContentPlaceHolder$FormView1$rblVisaViolation", "#ctl00_SiteContentPlaceHolder_FormView1_tbxVisaViolation"),
            ("deport", "ctl00$SiteContentPlaceHolder$FormView1$rblDeport", "#ctl00_SiteContentPlaceHolder_FormView1_tbxDeport_EXPL"),
        ],
        dossier,
    )


def fill_security_part5_page(dossier: ApplicantDossier) -> VisibleControlResult:
    return _fill_security_questions(
        "security_part5",
        [
            ("child_custody", "ctl00$SiteContentPlaceHolder$FormView1$rblChildCustody", "#ctl00_SiteContentPlaceHolder_FormView1_tbxChildCustody"),
            ("voting_violation", "ctl00$SiteContentPlaceHolder$FormView1$rblVotingViolation", "#ctl00_SiteContentPlaceHolder_FormView1_tbxVotingViolation"),
            ("renounce_exp", "ctl00$SiteContentPlaceHolder$FormView1$rblRenounceExp", "#ctl00_SiteContentPlaceHolder_FormView1_tbxRenounceExp"),
            ("attend_public_school_without_reimbursing", "ctl00$SiteContentPlaceHolder$FormView1$rblAttWoReimb", ""),
        ],
        dossier,
    )


def save_current_page() -> VisibleControlResult:
    ws_url = find_target_websocket_url("ceac.state.gov/GenNIV/General/complete/")
    expression = (
        "(() => { "
        "const btn = document.querySelector('#ctl00_SiteContentPlaceHolder_UpdateButton2'); "
        "if (!btn) return {status: 'SAVE_BUTTON_NOT_FOUND'}; "
        "btn.click(); "
        "return {status: 'SAVE_CLICKED', title: document.title, url: location.href}; "
        "})()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(
        action="save_current_page",
        ok=payload.get("status") == "SAVE_CLICKED",
        payload=payload,
    )


def extract_application_id() -> VisibleControlResult:
    ws_url = find_target_websocket_url("ceac.state.gov/GenNIV/General/complete/")
    expression = (
        "(() => { "
        "const text = document.body ? document.body.innerText : ''; "
        "const direct = text.match(/Application ID(?:\\s+is)?\\s*:?\\s*(AA[0-9A-Z]{8,})/i); "
        "const fallback = text.match(/\\b(AA[0-9A-Z]{8,})\\b/i); "
        "const application_id = direct ? direct[1].toUpperCase() : (fallback ? fallback[1].toUpperCase() : null); "
        "return {application_id, title: document.title, url: location.href}; "
        "})()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    return VisibleControlResult(
        action="extract_application_id",
        ok=bool(payload.get("application_id")),
        payload=payload,
    )


def detect_current_page() -> VisibleControlResult:
    ws_url = find_target_websocket_url("ceac.state.gov/GenNIV/General/complete/")
    expression = (
        "(() => {"
        "const text = document.body ? document.body.innerText : '';"
        "const direct = text.match(/Application ID(?:\\s+is)?\\s*:?\\s*(AA[0-9A-Z]{8,})/i);"
        "const fallback = text.match(/\\b(AA[0-9A-Z]{8,})\\b/i);"
        "return {"
        "title: document.title,"
        "url: location.href,"
        "application_id: direct ? direct[1].toUpperCase() : (fallback ? fallback[1].toUpperCase() : null)"
        "};"
        "})()"
    )
    result = _runtime_eval(ws_url, expression)
    payload = dict(result.get("value") or {})
    url = payload.get("url") or ""
    title = payload.get("title") or ""
    payload["page_key"] = _detect_page_key(url, title)
    return VisibleControlResult(action="detect_current_page", ok=True, payload=payload)


def click_next_and_wait(port: int = 9222, timeout_s: float = 30.0) -> VisibleControlResult:
    ws_url = find_target_websocket_url("ceac.state.gov/GenNIV/General/complete/")
    probe_expression = (
        "(() => ({ url: location.href, title: document.title }))()"
    )
    before = _runtime_eval(ws_url, probe_expression)
    before_url = dict(before.get("value") or {}).get("url") or ""

    click_expression = (
        "(() => { "
        "const visible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length); "
        "const label = (el) => [el.value, el.innerText, el.textContent, el.getAttribute('aria-label'), el.title, el.id, el.name].filter(Boolean).join(' ').trim(); "
        "const excluded = /\\b(save|back|previous|cancel|exit|sign\\s*out)\\b|continue\\s+application/i; "
        "const isNext = (text) => /^\\s*next\\b/i.test(text) || /\\bnext\\s*:/i.test(text) || /下一步/.test(text); "
        "const controls = [...document.querySelectorAll('input[type=\"submit\"], input[type=\"button\"], button, a')].filter(visible); "
        "let btn = controls.find((el) => { const text = label(el); return isNext(text) && !excluded.test(text); }); "
        "if (!btn) { "
        "  const selectors = ["
        "    '#ctl00_SiteContentPlaceHolder_UpdateButton3',"
        "    '#ctl00_SiteContentPlaceHolder_NextButton',"
        "    '#ctl00_SiteContentPlaceHolder_btnNext',"
        "    'input[name=\"ctl00$SiteContentPlaceHolder$UpdateButton3\"]'"
        "  ]; "
        "  btn = selectors.map((sel) => document.querySelector(sel)).find((el) => el && visible(el)); "
        "} "
        "if (!btn) return {status: 'NEXT_BUTTON_NOT_FOUND', controls: controls.map(label).slice(0, 20)}; "
        "const clicked = {id: btn.id || null, name: btn.name || null, label: label(btn)}; "
        "const suppressBeforeUnload = (ev) => { "
        "  try { ev.stopImmediatePropagation(); } catch (e) {} "
        "  try { ev.preventDefault(); } catch (e) {} "
        "  try { delete ev.returnValue; } catch (e) {} "
        "  try { ev.returnValue = undefined; } catch (e) {} "
        "}; "
        "window.addEventListener('beforeunload', suppressBeforeUnload, true); "
        "document.addEventListener('beforeunload', suppressBeforeUnload, true); "
        "if (typeof needToConfirm !== 'undefined') needToConfirm = false; "
        "if (document.body) document.body.onbeforeunload = null; "
        "window.onbeforeunload = null; "
        "btn.click(); "
        "return {status: 'NEXT_CLICKED', clicked, mode: 'click'}; "
        "})()"
    )
    click_result = _runtime_eval(ws_url, click_expression)
    click_payload = dict(click_result.get("value") or {})
    if click_payload.get("status") != "NEXT_CLICKED":
        return VisibleControlResult(
            action="click_next_and_wait",
            ok=False,
            payload={"status": click_payload.get("status"), "before_url": before_url},
        )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            new_ws_url = find_target_websocket_url("ceac.state.gov/GenNIV/General/complete/")
            _accept_javascript_dialog(new_ws_url)
            probe = _runtime_eval(new_ws_url, probe_expression)
            new_url = dict(probe.get("value") or {}).get("url") or ""
            if new_url and new_url != before_url:
                title = dict(probe.get("value") or {}).get("title") or ""
                new_page_key = _detect_page_key(new_url, title)
                return VisibleControlResult(
                    action="click_next_and_wait",
                    ok=True,
                    payload={
                        "before_url": before_url,
                        "new_url": new_url,
                        "new_page_key": new_page_key,
                    },
                )
        except RuntimeError:
            pass
        time.sleep(0.2)

    return VisibleControlResult(
        action="click_next_and_wait",
        ok=False,
        payload={"status": "TIMEOUT", "before_url": before_url},
    )


def _accept_javascript_dialog(ws_url: str) -> None:
    try:
        with CDPWebSocket(ws_url) as client:
            client.call("Page.handleJavaScriptDialog", {"accept": True})
    except Exception:
        pass


def fill_and_continue(
    page_key: str,
    dossier: ApplicantDossier,
    save_wait_s: float = 2.0,
) -> dict[str, object]:
    handler = _PAGE_FILL_HANDLERS.get(page_key)
    fill_result = None
    if handler:
        fill_result = handler(dossier)
    time.sleep(save_wait_s)
    next_result = click_next_and_wait()
    return {
        "page_key": page_key,
        "fill_ok": bool(fill_result and fill_result.ok),
        "fill_payload": fill_result.payload if fill_result else {},
        "next_ok": next_result.ok,
        "new_page_key": next_result.payload.get("new_page_key"),
        "application_id": detect_current_page().payload.get("application_id"),
    }


_PAGE_FILL_HANDLERS = {
    "personal1": fill_personal1_page,
    "personal2": fill_personal2_page,
    "passport": fill_passport_page,
    "travel": fill_travel_page,
    "travel_companions": fill_travel_companions_page,
    "previous_travel": fill_previous_travel_page,
    "address_phone": fill_address_phone_page,
    "us_contact": fill_us_contact_page,
    "work_education_present": fill_work_education_present_page,
    "work_education_previous": fill_work_education_previous_page,
    "work_education_additional": fill_work_education_additional_page,
    "family_relatives": fill_family_relatives_page,
    "family_spouse": fill_family_spouse_page,
    "security_part1": fill_security_part1_page,
    "security_part2": fill_security_part2_page,
    "security_part3": fill_security_part3_page,
    "security_part4": fill_security_part4_page,
    "security_part5": fill_security_part5_page,
}


def fill_current_supported_page(dossier: ApplicantDossier) -> VisibleControlResult:
    current = detect_current_page()
    page_key = current.payload.get("page_key", "unsupported")
    handler = _PAGE_FILL_HANDLERS.get(page_key)
    if handler:
        result = handler(dossier)
        return VisibleControlResult(
            action="fill_current_supported_page",
            ok=result.ok,
            payload={"page_key": page_key, **result.payload},
        )
    return VisibleControlResult(
        action="fill_current_supported_page",
        ok=False,
        payload={"page_key": page_key, "title": current.payload.get("title"), "url": current.payload.get("url")},
    )


def _month_abbrev(month: str) -> str:
    return {
        "01": "JAN",
        "02": "FEB",
        "03": "MAR",
        "04": "APR",
        "05": "MAY",
        "06": "JUN",
        "07": "JUL",
        "08": "AUG",
        "09": "SEP",
        "10": "OCT",
        "11": "NOV",
        "12": "DEC",
    }[month]


def _previous_travel_los_unit(unit: str | None) -> str:
    normalized = (unit or "").strip().upper()
    return {
        "DAY": "Day(s)",
        "DAYS": "Day(s)",
        "WEEK": "Week(s)",
        "WEEKS": "Week(s)",
        "MONTH": "Month(s)",
        "MONTHS": "Month(s)",
        "YEAR": "Year(s)",
        "YEARS": "Year(s)",
    }.get(normalized, "Day(s)")


def _travel_other_purpose_value(visa_class: str | None) -> str:
    normalized = (visa_class or "").strip().upper()
    return {
        "B1/B2": "B1-B2",
        "B1": "B1-CF",
        "B2": "B2-TM",
    }.get(normalized, "B1-B2")


def _find_page_ws_url(page_key: str) -> str:
    targets = list_debug_targets()
    for target in targets:
        url = target.get("url") or ""
        title = target.get("title") or ""
        if _matches_page(page_key, url, title):
            ws_url = target.get("webSocketDebuggerUrl")
            if ws_url:
                return str(ws_url)
    raise RuntimeError(f"No target found for page {page_key!r} using matchers {PAGE_MATCHERS[page_key]!r}")


def _wait_for_selector(page_key: str, selector: str, timeout_s: float = 5.0, interval_s: float = 0.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ws_url = _find_page_ws_url(page_key)
        probe = _runtime_eval(
            ws_url,
            f"(() => !!document.querySelector({json.dumps(selector)}))()",
        )
        if probe.get("value") is True:
            return True
        time.sleep(interval_s)
    return False


def _fill_security_questions(page_key: str, questions: list[tuple[str, str, str]], dossier: ApplicantDossier) -> VisibleControlResult:
    staged_filled: list[str] = []
    staged_missing: list[str] = []
    for answer_key, radio_name, textarea_sel in questions:
        yes = _security_yes(dossier, answer_key)
        label = "yes" if yes else "no"
        ws_url = _find_page_ws_url(page_key)
        radio_expression = (
            "(() => { "
            + _JS_HELPERS
            + f"setRadioClick({json.dumps(radio_name)}, {json.dumps('Y' if yes else 'N')}) ? ok({json.dumps(answer_key + '_' + label)}) : miss({json.dumps(answer_key + '_' + label)}); "
            "return r; })()"
        )
        radio_result = _runtime_eval(ws_url, radio_expression)
        radio_payload = dict(radio_result.get("value") or {})
        staged_filled.extend(radio_payload.get("filled") or [])
        staged_missing.extend(radio_payload.get("missing") or [])
        if yes and textarea_sel:
            time.sleep(1)
            _wait_for_selector(page_key, textarea_sel, timeout_s=5)
            ws_url = _find_page_ws_url(page_key)
            explain_expression = (
                "(() => { "
                + _JS_HELPERS
                + f"setText({json.dumps(textarea_sel)}, {json.dumps(_security_explanation(dossier, answer_key))}) ? ok({json.dumps(answer_key + '_explanation')}) : miss({json.dumps(answer_key + '_explanation')}); "
                "return r; })()"
            )
            explain_result = _runtime_eval(ws_url, explain_expression)
            explain_payload = dict(explain_result.get("value") or {})
            staged_filled.extend(explain_payload.get("filled") or [])
            staged_missing.extend(explain_payload.get("missing") or [])
    payload = {"filled": staged_filled, "missing": staged_missing}
    return VisibleControlResult(action=f"fill_{page_key}_page", ok=not payload.get("missing"), payload=payload)


def _address_phone_defaults(dossier: ApplicantDossier) -> dict[str, str] | None:
    c = dossier.personal_contact
    if c is None or not c.home_address_line1:
        return None
    return {
        "home_addr1": c.home_address_line1 or "",
        "home_addr2": c.home_address_line2 or "",
        "home_city": c.home_city or "",
        "home_state": c.home_state or "",
        "home_postal": c.home_postal_code or "",
        "home_country": c.home_country or dossier.identity.birth_country or "CHINA",
        "primary_phone": _normalize_phone_number(c.primary_phone or "", fallback=""),
        "work_phone": _normalize_phone_number(c.work_phone or "", fallback=""),
        "email": c.email or "",
    }


def _split_employer_address(address: str | None) -> tuple[str, str, str, str]:
    if not address:
        return "", "", "", ""
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 4:
        return parts[0], parts[1], parts[2], parts[3]
    if len(parts) == 3:
        return parts[0], parts[1], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], parts[1], ""
    return parts[0], "", "", ""


def _normalize_phone_number(phone: str | None, fallback: str = "862155558800") -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if 5 <= len(digits) <= 15:
        return digits
    return fallback


def _split_contact_name(full_name: str | None) -> tuple[str, str]:
    parts = [part for part in (full_name or "").split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[-1], " ".join(parts[:-1])


def _split_name_first_surname(full_name: str | None) -> tuple[str, str]:
    parts = [part for part in (full_name or "").split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _family_relative_dob(relative: str, dossier: ApplicantDossier) -> str | None:
    f = dossier.family_contacts
    if relative == "father":
        return f.father_date_of_birth
    return f.mother_date_of_birth


def _family_spouse_defaults(dossier: ApplicantDossier) -> dict[str, str] | None:
    f = dossier.family_contacts
    if not f.spouse_full_name:
        return None
    return {
        "dob": f.spouse_date_of_birth or "",
        "nationality": f.spouse_nationality or dossier.identity.nationality or "CHINA",
        "birth_city": f.spouse_birth_city or dossier.identity.birth_city or "",
        "birth_country": f.spouse_birth_country or dossier.identity.birth_country or "CHINA",
    }


def _work_education_present_defaults(dossier: ApplicantDossier) -> dict[str, str] | None:
    e = dossier.employment_education
    if not e.current_employer_name:
        return None
    return {
        "occupation": _present_occupation_label(e.primary_occupation),
        "addr1": e.current_employer_address or "",
        "addr2": e.current_employer_address_line2 or "",
        "city": e.employer_city or "",
        "state": e.employer_state or "",
        "postal": e.employer_postal_code or "",
        "country": e.employer_country or dossier.identity.birth_country or "CHINA",
        "phone": _normalize_phone_number(e.employer_phone or "", fallback=""),
        "start_date": e.current_employment_start_date or "",
        "duties": e.current_job_duties or "",
    }


def _work_education_previous_defaults(dossier: ApplicantDossier) -> dict[str, str] | None:
    e = dossier.employment_education
    has_prev = e.previous_employer_name
    has_educ = e.school_name
    if not has_prev and not has_educ:
        return None
    return {
        "prev_employer_name": _sanitize_ds160_name(e.previous_employer_name or ""),
        "prev_employer_addr1": e.previous_employer_address or "",
        "prev_employer_addr2": "",
        "prev_employer_city": e.previous_employer_city or "",
        "prev_employer_state": e.previous_employer_state or "",
        "prev_employer_postal": e.previous_employer_postal_code or "",
        "prev_employer_country": e.previous_employer_country or dossier.identity.birth_country or "CHINA",
        "prev_employer_phone": _normalize_phone_number(e.previous_employer_phone or "", fallback=""),
        "prev_job_title": _sanitize_ds160_name(e.previous_job_title or ""),
        "prev_supervisor_surname": _sanitize_ds160_name(e.previous_supervisor_surname or ""),
        "prev_supervisor_given": _sanitize_ds160_name(e.previous_supervisor_given_name or ""),
        "prev_emp_from": e.previous_employment_start_date or "",
        "prev_emp_to": e.previous_employment_end_date or "",
        "prev_emp_duties": e.previous_job_duties or "",
        "school_name": _sanitize_ds160_name(e.school_name or ""),
        "school_addr1": e.school_address_line1 or "",
        "school_addr2": "",
        "school_city": e.school_city or "",
        "school_state": e.school_state or "",
        "school_postal": e.school_postal_code or "",
        "school_country": e.school_country or dossier.identity.birth_country or "CHINA",
        "school_course": _sanitize_ds160_name(e.major_or_course_of_study or ""),
        "school_from": e.school_attendance_start_date or "",
        "school_to": e.school_attendance_end_date or "",
    }


def _work_education_additional_defaults(dossier: ApplicantDossier) -> dict[str, str]:
    e = dossier.employment_education
    return {
        "clan_name": e.clan_or_tribe_name or "",
        "language_name": e.languages or "",
        "country_visited": e.countries_visited or "",
        "organization_name": e.organization_memberships or "",
        "specialized_skills_expl": e.specialized_skills_description or "",
        "military_country": e.military_service_country or "",
        "military_branch": e.military_branch or "",
        "military_rank": e.military_rank or "",
        "military_specialty": e.military_specialty or "",
        "military_from": e.military_service_start_date or "",
        "military_to": e.military_service_end_date or "",
        "insurgent_expl": e.insurgent_organization_explanation or "",
    }


def _present_occupation_label(value: str | None) -> str:
    mapping = {
        "BUSINESSPERSON": "BUSINESS",
        "BUSINESS": "BUSINESS",
        "ENGINEER": "ENGINEERING",
        "ENGINEERING": "ENGINEERING",
        "STUDENT": "STUDENT",
        "NOT EMPLOYED": "NOT EMPLOYED",
    }
    return mapping.get((value or "").upper(), "BUSINESS")


def _security_yes(dossier: ApplicantDossier, key: str) -> bool:
    return bool(dossier.security_background.yes_no_answers.get(key, False))


def _security_explanation(dossier: ApplicantDossier, key: str) -> str:
    return dossier.security_background.explanations.get(
        key,
        "Explanation available upon request.",
    )


def _sanitize_ds160_name(value: str | None) -> str:
    raw = (value or "").upper()
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "'", "&", " "}) else " " for ch in raw)
    return " ".join(cleaned.split())


def _us_contact_relationship(travel_plan) -> str:
    if travel_plan.us_contact_organization:
        return "BUSINESS ASSOCIATE"
    return "OTHER"
