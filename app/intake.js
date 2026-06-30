const SERVER_BASE = "http://127.0.0.1:8765";
const OFFLINE_MODE_MESSAGE = "已切换到离线模式：本地服务未连接。";

const FALLBACK_SCHEMA_DOCUMENT = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://local.ds160/dossier.schema.json",
  title: "China B1/B2 Applicant Dossier",
  required: ["case_id", "identity", "travel_plan", "employment_education", "family_contacts", "security_background", "evidence_catalog"],
};

const REQUIRED_PATHS = [
  "case_id",
  "identity.surname",
  "identity.given_names",
  "identity.sex",
  "identity.marital_status",
  "identity.date_of_birth",
  "identity.birth_city",
  "identity.birth_country",
  "identity.nationality",
  "identity.passport_number",
  "identity.passport_issuance_country",
  "identity.passport_issue_date",
  "identity.passport_expiration_date",
  "identity.source_ids",
  "travel_plan.visa_class",
  "travel_plan.source_ids",
  "employment_education.source_ids",
  "family_contacts.source_ids",
  "security_background.yes_no_answers.communicable_disease",
  "security_background.yes_no_answers.arrested_or_convicted",
  "security_background.source_ids",
  "evidence_catalog",
];

const DATE_PATHS = [
  "identity.date_of_birth",
  "identity.passport_issue_date",
  "identity.passport_expiration_date",
  "travel_plan.intended_arrival_date",
  "family_contacts.father_date_of_birth",
  "family_contacts.mother_date_of_birth",
  "family_contacts.spouse_date_of_birth",
  "employment_education.current_employment_start_date",
  "employment_education.previous_employment_start_date",
  "employment_education.previous_employment_end_date",
  "employment_education.school_attendance_start_date",
  "employment_education.school_attendance_end_date",
  "employment_education.military_service_start_date",
  "employment_education.military_service_end_date",
  "previous_travel.last_arrival_date",
  "previous_travel.previous_visa_issue_date",
];

const EMAIL_PATHS = ["travel_plan.us_contact_email", "personal_contact.email"];
const ENUMS = {
  "identity.sex": ["MALE", "FEMALE"],
  "identity.marital_status": ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED"],
  "travel_plan.intended_length_of_stay_unit": ["DAYS", "WEEKS", "MONTHS"],
  "previous_travel.last_length_of_stay_unit": ["DAYS", "WEEKS", "MONTHS"],
  "employment_education.primary_occupation": ["BUSINESSPERSON", "STUDENT", "OTHER"],
};
const JSON_TEXTAREA_PATHS = ["security_background.explanations", "evidence_catalog"];
const ARRAY_INPUT_PATHS = [
  "identity.source_ids",
  "travel_plan.source_ids",
  "employment_education.source_ids",
  "family_contacts.source_ids",
  "personal_contact.source_ids",
  "previous_travel.source_ids",
  "security_background.source_ids",
];
const BOOLEAN_PATHS = [
  "identity.other_nationality",
  "identity.permanent_resident_other_country",
  "family_contacts.father_in_us",
  "family_contacts.mother_in_us",
  "family_contacts.has_us_immediate_relatives",
  "family_contacts.has_us_other_relatives",
  "personal_contact.mailing_same_as_home",
  "previous_travel.has_previous_us_travel",
  "previous_travel.has_previous_us_visa",
  "previous_travel.visa_ever_refused",
  "previous_travel.visa_ever_lost",
  "previous_travel.visa_ever_cancelled",
  "previous_travel.has_immigrant_petition",
  "previous_travel.has_us_driver_license",
  "previous_travel.ten_print_collected",
  "security_background.yes_no_answers.communicable_disease",
  "security_background.yes_no_answers.physical_or_mental_disorder",
  "security_background.yes_no_answers.drug_abuser",
  "security_background.yes_no_answers.arrested_or_convicted",
  "security_background.yes_no_answers.controlled_substances",
  "security_background.yes_no_answers.prostitution_or_vice",
  "security_background.yes_no_answers.money_laundering",
  "security_background.yes_no_answers.human_trafficking",
  "security_background.yes_no_answers.assisted_severe_trafficking",
  "security_background.yes_no_answers.human_trafficking_related",
  "security_background.yes_no_answers.illegal_activity",
  "security_background.yes_no_answers.terrorist_activity",
  "security_background.yes_no_answers.terrorist_support",
  "security_background.yes_no_answers.terrorist_org",
  "security_background.yes_no_answers.terrorist_rel",
  "security_background.yes_no_answers.genocide",
  "security_background.yes_no_answers.torture",
  "security_background.yes_no_answers.extrajudicial_violence",
  "security_background.yes_no_answers.child_soldier",
  "security_background.yes_no_answers.religious_freedom",
  "security_background.yes_no_answers.population_controls",
  "security_background.yes_no_answers.transplant",
  "security_background.yes_no_answers.removal_hearing",
  "security_background.yes_no_answers.immigration_fraud",
  "security_background.yes_no_answers.fail_to_attend",
  "security_background.yes_no_answers.visa_violation",
  "security_background.yes_no_answers.deport",
  "security_background.yes_no_answers.child_custody",
  "security_background.yes_no_answers.voting_violation",
  "security_background.yes_no_answers.renounce_exp",
  "security_background.yes_no_answers.attend_public_school_without_reimbursing",
];

const manualForm = document.getElementById("manual-form");
const submitStatus = document.getElementById("submit-status");
const jsonPreview = document.getElementById("json-preview");
const downloadButton = document.getElementById("download-json");
const downloadEncryptedButton = document.getElementById("download-encrypted");
const encryptPassphraseInput = document.getElementById("encrypt-passphrase");
const copyButton = document.getElementById("copy-json");
const missingFields = document.getElementById("missing-fields");
const warnings = document.getElementById("warnings");

const photoUpload = document.getElementById("photo-upload");
const photoPreview = document.getElementById("photo-preview");

const state = {
  latestJsonText: "",
  schema: null,
  offlineMode: false,
  photoDataUrl: null,
};


// ---------- localStorage draft save ----------

const DRAFT_KEY = "ds160_intake_draft";

function saveDraft() {
  var data = {};
  Array.from(manualForm.elements).forEach(function (el) {
    if (!el.name) return;
    if (el.type === "checkbox") { data[el.name] = el.checked; return; }
    data[el.name] = el.value || "";
  });
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(data)); } catch (_) {}
}

function loadDraft() {
  try {
    var raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return false;
    var data = JSON.parse(raw);
    Object.keys(data).forEach(function (name) {
      var el = manualForm.elements.namedItem(name);
      if (!el || el instanceof RadioNodeList) return;
      if (el.type === "checkbox") { el.checked = !!data[name]; return; }
      el.value = data[name] || "";
    });
    return true;
  } catch (_) { return false; }
}

function updateProgress() {
  var all = manualForm.querySelectorAll("input:not([type=checkbox]):not([type=file]), select, textarea");
  var filled = 0;
  all.forEach(function (el) { if (String(el.value || "").trim()) filled += 1; });
  var pct = all.length ? Math.round((filled / all.length) * 100) : 0;
  var bar = document.getElementById("form-progress-bar");
  var txt = document.getElementById("form-progress-text");
  if (bar) bar.style.width = pct + "%";
  if (txt) txt.textContent = "已填写: " + pct + "%";
}

// Auto-save every 3s and on input
var _draftTimer = null;
manualForm.addEventListener("input", function () {
  updateProgress();
  if (_draftTimer) clearTimeout(_draftTimer);
  _draftTimer = setTimeout(saveDraft, 1500);
});
manualForm.addEventListener("change", function () {
  updateProgress();
  if (_draftTimer) clearTimeout(_draftTimer);
  _draftTimer = setTimeout(saveDraft, 1500);
});

// Load draft on startup
if (loadDraft()) {
  submitStatus.textContent = "已恢复上次填写的草稿。";
  setTimeout(updateProgress, 100);
}


function activateOfflineMode() {
  state.offlineMode = true;
  submitStatus.textContent = OFFLINE_MODE_MESSAGE;
}


function normalizedOptional(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const text = String(value).trim();
  return text ? text : null;
}


function parseJsonText(value, fallback) {
  const text = String(value || "").trim();
  if (!text) {
    return fallback;
  }
  return JSON.parse(text);
}


function parseStringArray(value) {
  const text = String(value || "").trim();
  if (!text) {
    return [];
  }
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}


function setNestedValue(target, path, value) {
  const parts = path.split(".");
  let cursor = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    const key = parts[index];
    if (!cursor[key] || typeof cursor[key] !== "object" || Array.isArray(cursor[key])) {
      cursor[key] = {};
    }
    cursor = cursor[key];
  }
  cursor[parts[parts.length - 1]] = value;
}


function getNestedValue(target, path) {
  return path.split(".").reduce((value, part) => (value && typeof value === "object" ? value[part] : undefined), target);
}


function manualFormFieldNames() {
  return Array.from(manualForm.elements)
    .map((field) => field.name)
    .filter(Boolean);
}


function issueCard(value) {
  return `<article class="item-card"><strong>${value}</strong></article>`;
}


function warningCard(value) {
  return `<article class="item-card"><strong>${value}</strong></article>`;
}


function renderItems(element, items, emptyText, formatter) {
  if (!items.length) {
    element.className = "item-list empty";
    element.textContent = emptyText;
    return;
  }
  element.className = "item-list";
  element.innerHTML = items.map(formatter).join("");
}


function setFieldHint(fieldName, message) {
  const hint = manualForm.querySelector(`[data-hint-for="${fieldName}"]`);
  if (hint) {
    hint.textContent = message || "";
  }
}


function clearFieldHighlight(fieldName) {
  const field = manualForm.elements.namedItem(fieldName);
  if (!field || field instanceof RadioNodeList) {
    return;
  }
  field.classList.remove("missing-field");
  const wrapper = field.closest("label");
  if (wrapper) {
    wrapper.classList.remove("is-missing");
  }
  setFieldHint(fieldName, "");
}


function clearMissingHighlights() {
  manualForm.querySelectorAll(".missing-field").forEach((field) => field.classList.remove("missing-field"));
  manualForm.querySelectorAll(".is-missing").forEach((field) => field.classList.remove("is-missing"));
  manualForm.querySelectorAll("[data-hint-for]").forEach((hint) => {
    hint.textContent = "";
  });
}


function highlightMissingFields(fields, scrollToFirst = true) {
  clearMissingHighlights();
  let firstTarget = null;
  for (const fieldName of fields || []) {
    const field = manualForm.elements.namedItem(fieldName);
    setFieldHint(fieldName, "这里还需要补充。");
    if (!field || field instanceof RadioNodeList) {
      continue;
    }
    field.classList.add("missing-field");
    const wrapper = field.closest("label");
    if (wrapper) {
      wrapper.classList.add("is-missing");
      if (!firstTarget) {
        firstTarget = wrapper;
      }
    } else if (!firstTarget) {
      firstTarget = field;
    }
  }
  if (firstTarget && scrollToFirst) {
    firstTarget.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}


function fieldHasValue(fieldName) {
  const field = manualForm.elements.namedItem(fieldName);
  if (!field || field instanceof RadioNodeList) {
    return false;
  }
  if (field.type === "checkbox") {
    return true;
  }
  return String(field.value || "").trim() !== "";
}


function validateDossierPayload(payload) {
  const missing = REQUIRED_PATHS.filter((path) => {
    const value = getNestedValue(payload, path);
    if (typeof value === "boolean") {
      return false;
    }
    if (Array.isArray(value)) {
      return value.length === 0;
    }
    return value === null || value === undefined || value === "";
  });

  const invalids = {};
  for (const path of DATE_PATHS) {
    const value = getNestedValue(payload, path);
    if (value && !/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
      invalids[path] = "请使用年-月-日格式。";
    }
  }
  for (const path of EMAIL_PATHS) {
    const value = getNestedValue(payload, path);
    if (value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value))) {
      invalids[path] = "请输入有效邮箱。";
    }
  }
  for (const [path, values] of Object.entries(ENUMS)) {
    const value = getNestedValue(payload, path);
    if (value && !values.includes(value)) {
      invalids[path] = "请按当前选项填写。";
    }
  }
  if (!Array.isArray(payload.evidence_catalog)) {
    invalids["evidence_catalog"] = "必须是 JSON 数组。";
  }
  if (payload.evidence_catalog && Array.isArray(payload.evidence_catalog)) {
    payload.evidence_catalog.forEach((item, index) => {
      if (!item || typeof item !== "object" || !item.id || !item.kind || !item.description) {
        invalids[`evidence_catalog`] = `第 ${index + 1} 条证据缺少 id/kind/description。`;
      }
    });
  }
  if (!payload.security_background?.explanations || typeof payload.security_background.explanations !== "object" || Array.isArray(payload.security_background.explanations)) {
    invalids["security_background.explanations"] = "必须是 JSON 对象。";
  }

  return { missing, invalids };
}


function refreshManualValidation(scrollToFirst = false) {
  let payload;
  try {
    payload = manualPayload();
  } catch (error) {
    renderItems(missingFields, [], "没有缺失字段。", issueCard);
    renderItems(warnings, [error.message || "JSON 字段格式错误。"], "没有额外提醒。", warningCard);
    return { missing: [], invalids: { json: error.message || "JSON 字段格式错误。" } };
  }
  const { missing, invalids } = validateDossierPayload(payload);
  const problemFields = [...new Set([...missing, ...Object.keys(invalids)])];
  if (problemFields.length) {
    highlightMissingFields(problemFields, scrollToFirst);
    Object.entries(invalids).forEach(([fieldName, message]) => setFieldHint(fieldName, message));
  } else {
    clearMissingHighlights();
  }
  renderItems(missingFields, problemFields, "没有缺失字段。", issueCard);
  renderItems(warnings, Object.values(invalids), "没有额外提醒。", warningCard);
  return { missing, invalids };
}


function checkbox(name) {
  const el = manualForm.elements.namedItem(name);
  return el ? el.checked : false;
}

function field(name) {
  return normalizedOptional(manualForm.elements.namedItem(name)?.value || "");
}

function manualPayload() {
  var f = field;
  var s = function (n) { return parseStringArray(manualForm.elements.namedItem(n)?.value || ""); };

  var payload = {
    case_id: f("case_id"),
    identity: {
      surname: f("identity.surname"),
      given_names: f("identity.given_names"),
      native_full_name: f("identity.native_full_name"),
      sex: f("identity.sex"),
      marital_status: f("identity.marital_status"),
      date_of_birth: f("identity.date_of_birth"),
      birth_city: f("identity.birth_city"),
      birth_province: f("identity.birth_province"),
      birth_country: f("identity.birth_country"),
      nationality: f("identity.nationality"),
      passport_number: f("identity.passport_number"),
      passport_issuance_country: f("identity.passport_issuance_country"),
      passport_issue_date: f("identity.passport_issue_date"),
      passport_expiration_date: f("identity.passport_expiration_date"),
      passport_book_number: f("identity.passport_book_number"),
      other_nationality: checkbox("identity.other_nationality"),
      permanent_resident_other_country: checkbox("identity.permanent_resident_other_country"),
      national_id_number: f("identity.national_id_number"),
      us_social_security_number: f("identity.us_social_security_number"),
      us_taxpayer_id_number: f("identity.us_taxpayer_id_number"),
      source_ids: s("identity.source_ids"),
    },
    travel_plan: {
      visa_class: f("travel_plan.visa_class"),
      purpose_notes: f("travel_plan.purpose_notes"),
      intended_arrival_date: f("travel_plan.intended_arrival_date"),
      intended_length_of_stay_value: f("travel_plan.intended_length_of_stay_value"),
      intended_length_of_stay_unit: f("travel_plan.intended_length_of_stay_unit"),
      payer_name: f("travel_plan.payer_name"),
      us_contact_name: f("travel_plan.us_contact_name"),
      us_contact_organization: f("travel_plan.us_contact_organization"),
      us_contact_address_line1: f("travel_plan.us_contact_address_line1"),
      us_contact_city: f("travel_plan.us_contact_city"),
      us_contact_state: f("travel_plan.us_contact_state"),
      us_contact_postal_code: f("travel_plan.us_contact_postal_code"),
      us_contact_phone: f("travel_plan.us_contact_phone"),
      us_contact_email: f("travel_plan.us_contact_email"),
      source_ids: s("travel_plan.source_ids"),
    },
    employment_education: {
      primary_occupation: f("employment_education.primary_occupation"),
      current_employer_name: f("employment_education.current_employer_name"),
      current_employer_address: f("employment_education.current_employer_address"),
      current_employer_address_line2: f("employment_education.current_employer_address_line2"),
      employer_city: f("employment_education.employer_city"),
      employer_state: f("employment_education.employer_state"),
      employer_postal_code: f("employment_education.employer_postal_code"),
      employer_country: f("employment_education.employer_country"),
      employer_phone: f("employment_education.employer_phone"),
      current_employment_start_date: f("employment_education.current_employment_start_date"),
      current_job_title: f("employment_education.current_job_title"),
      current_job_duties: f("employment_education.current_job_duties"),
      current_supervisor_surname: f("employment_education.current_supervisor_surname"),
      current_supervisor_given_name: f("employment_education.current_supervisor_given_name"),
      previous_employer_name: f("employment_education.previous_employer_name"),
      previous_employer_address: f("employment_education.previous_employer_address"),
      previous_employer_city: f("employment_education.previous_employer_city"),
      previous_employer_state: f("employment_education.previous_employer_state"),
      previous_employer_postal_code: f("employment_education.previous_employer_postal_code"),
      previous_employer_country: f("employment_education.previous_employer_country"),
      previous_employer_phone: f("employment_education.previous_employer_phone"),
      previous_job_title: f("employment_education.previous_job_title"),
      previous_supervisor_surname: f("employment_education.previous_supervisor_surname"),
      previous_supervisor_given_name: f("employment_education.previous_supervisor_given_name"),
      previous_employment_start_date: f("employment_education.previous_employment_start_date"),
      previous_employment_end_date: f("employment_education.previous_employment_end_date"),
      previous_job_duties: f("employment_education.previous_job_duties"),
      school_name: f("employment_education.school_name"),
      school_address_line1: f("employment_education.school_address_line1"),
      school_city: f("employment_education.school_city"),
      school_state: f("employment_education.school_state"),
      school_postal_code: f("employment_education.school_postal_code"),
      school_country: f("employment_education.school_country"),
      major_or_course_of_study: f("employment_education.major_or_course_of_study"),
      school_attendance_start_date: f("employment_education.school_attendance_start_date"),
      school_attendance_end_date: f("employment_education.school_attendance_end_date"),
      languages: f("employment_education.languages"),
      countries_visited: f("employment_education.countries_visited"),
      clan_or_tribe_name: f("employment_education.clan_or_tribe_name"),
      organization_memberships: f("employment_education.organization_memberships"),
      specialized_skills_description: f("employment_education.specialized_skills_description"),
      military_service_country: f("employment_education.military_service_country"),
      military_branch: f("employment_education.military_branch"),
      military_rank: f("employment_education.military_rank"),
      military_specialty: f("employment_education.military_specialty"),
      military_service_start_date: f("employment_education.military_service_start_date"),
      military_service_end_date: f("employment_education.military_service_end_date"),
      insurgent_organization_explanation: f("employment_education.insurgent_organization_explanation"),
      monthly_income_local: f("employment_education.monthly_income_local"),
      source_ids: s("employment_education.source_ids"),
    },
    family_contacts: {
      father_full_name: f("family_contacts.father_full_name"),
      father_date_of_birth: f("family_contacts.father_date_of_birth"),
      father_in_us: checkbox("family_contacts.father_in_us"),
      mother_full_name: f("family_contacts.mother_full_name"),
      mother_date_of_birth: f("family_contacts.mother_date_of_birth"),
      mother_in_us: checkbox("family_contacts.mother_in_us"),
      spouse_full_name: f("family_contacts.spouse_full_name"),
      spouse_date_of_birth: f("family_contacts.spouse_date_of_birth"),
      spouse_nationality: f("family_contacts.spouse_nationality"),
      spouse_birth_city: f("family_contacts.spouse_birth_city"),
      spouse_birth_country: f("family_contacts.spouse_birth_country"),
      has_us_immediate_relatives: checkbox("family_contacts.has_us_immediate_relatives"),
      has_us_other_relatives: checkbox("family_contacts.has_us_other_relatives"),
      us_relative_name: f("family_contacts.us_relative_name"),
      us_relative_status: f("family_contacts.us_relative_status"),
      source_ids: s("family_contacts.source_ids"),
    },
    personal_contact: {
      home_address_line1: f("personal_contact.home_address_line1"),
      home_address_line2: f("personal_contact.home_address_line2"),
      home_city: f("personal_contact.home_city"),
      home_state: f("personal_contact.home_state"),
      home_postal_code: f("personal_contact.home_postal_code"),
      home_country: f("personal_contact.home_country"),
      primary_phone: f("personal_contact.primary_phone"),
      secondary_phone: f("personal_contact.secondary_phone"),
      work_phone: f("personal_contact.work_phone"),
      email: f("personal_contact.email"),
      social_media_platform: f("personal_contact.social_media_platform"),
      social_media_handle: f("personal_contact.social_media_handle"),
      mailing_same_as_home: checkbox("personal_contact.mailing_same_as_home"),
      source_ids: s("personal_contact.source_ids"),
    },
    previous_travel: {
      has_previous_us_travel: checkbox("previous_travel.has_previous_us_travel"),
      last_arrival_date: f("previous_travel.last_arrival_date"),
      last_length_of_stay_value: f("previous_travel.last_length_of_stay_value"),
      last_length_of_stay_unit: f("previous_travel.last_length_of_stay_unit"),
      has_previous_us_visa: checkbox("previous_travel.has_previous_us_visa"),
      previous_visa_number: f("previous_travel.previous_visa_number"),
      previous_visa_issue_date: f("previous_travel.previous_visa_issue_date"),
      visa_ever_refused: checkbox("previous_travel.visa_ever_refused"),
      visa_ever_lost: checkbox("previous_travel.visa_ever_lost"),
      visa_ever_cancelled: checkbox("previous_travel.visa_ever_cancelled"),
      has_immigrant_petition: checkbox("previous_travel.has_immigrant_petition"),
      has_us_driver_license: checkbox("previous_travel.has_us_driver_license"),
      ten_print_collected: checkbox("previous_travel.ten_print_collected"),
      source_ids: s("previous_travel.source_ids"),
    },
    security_background: {
      yes_no_answers: {
        // Part 1: Medical
        communicable_disease: checkbox("security_background.yes_no_answers.communicable_disease"),
        physical_or_mental_disorder: checkbox("security_background.yes_no_answers.physical_or_mental_disorder"),
        drug_abuser: checkbox("security_background.yes_no_answers.drug_abuser"),
        // Part 2: Criminal
        arrested_or_convicted: checkbox("security_background.yes_no_answers.arrested_or_convicted"),
        controlled_substances: checkbox("security_background.yes_no_answers.controlled_substances"),
        prostitution_or_vice: checkbox("security_background.yes_no_answers.prostitution_or_vice"),
        money_laundering: checkbox("security_background.yes_no_answers.money_laundering"),
        human_trafficking: checkbox("security_background.yes_no_answers.human_trafficking"),
        assisted_severe_trafficking: checkbox("security_background.yes_no_answers.assisted_severe_trafficking"),
        human_trafficking_related: checkbox("security_background.yes_no_answers.human_trafficking_related"),
        // Part 3: Terror/Violence/Human rights
        illegal_activity: checkbox("security_background.yes_no_answers.illegal_activity"),
        terrorist_activity: checkbox("security_background.yes_no_answers.terrorist_activity"),
        terrorist_support: checkbox("security_background.yes_no_answers.terrorist_support"),
        terrorist_org: checkbox("security_background.yes_no_answers.terrorist_org"),
        terrorist_rel: checkbox("security_background.yes_no_answers.terrorist_rel"),
        genocide: checkbox("security_background.yes_no_answers.genocide"),
        torture: checkbox("security_background.yes_no_answers.torture"),
        extrajudicial_violence: checkbox("security_background.yes_no_answers.extrajudicial_violence"),
        child_soldier: checkbox("security_background.yes_no_answers.child_soldier"),
        religious_freedom: checkbox("security_background.yes_no_answers.religious_freedom"),
        population_controls: checkbox("security_background.yes_no_answers.population_controls"),
        transplant: checkbox("security_background.yes_no_answers.transplant"),
        // Part 4: Immigration violations
        removal_hearing: checkbox("security_background.yes_no_answers.removal_hearing"),
        immigration_fraud: checkbox("security_background.yes_no_answers.immigration_fraud"),
        fail_to_attend: checkbox("security_background.yes_no_answers.fail_to_attend"),
        visa_violation: checkbox("security_background.yes_no_answers.visa_violation"),
        deport: checkbox("security_background.yes_no_answers.deport"),
        // Part 5: Miscellaneous
        child_custody: checkbox("security_background.yes_no_answers.child_custody"),
        voting_violation: checkbox("security_background.yes_no_answers.voting_violation"),
        renounce_exp: checkbox("security_background.yes_no_answers.renounce_exp"),
        attend_public_school_without_reimbursing: checkbox("security_background.yes_no_answers.attend_public_school_without_reimbursing"),
      },
      explanations: parseJsonText(manualForm.elements.namedItem("security_background.explanations")?.value || "", {}),
      source_ids: s("security_background.source_ids"),
    },
    evidence_catalog: parseJsonText(manualForm.elements.namedItem("evidence_catalog")?.value || "", []),
  };
  return payload;
}


async function buildExportDocument(payload) {
  try {
    const res = await fetch(`${SERVER_BASE}/dossier/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "无法生成 dossier");
    }
    return data.dossier;
  } catch {
    activateOfflineMode();
    return payload;
  }
}


async function loadSchema() {
  try {
    const res = await fetch(`${SERVER_BASE}/dossier-schema`);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "无法读取 dossier schema");
    }
    state.schema = data.schema_document;
  } catch {
    state.schema = FALLBACK_SCHEMA_DOCUMENT;
    activateOfflineMode();
  }
}


function copyTextToClipboard(text) {
  if (!text) {
    throw new Error("没有可复制的内容");
  }
  if (navigator.clipboard?.writeText) {
    try {
      return navigator.clipboard.writeText(text);
    } catch {
      // Fall back for file:// pages or browsers without clipboard permission.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error("当前页面无法直接复制，请手动复制。");
  }
}


function flashButtonSuccess(button, successText, defaultText) {
  if (button.dataset.resetTimer) {
    window.clearTimeout(Number(button.dataset.resetTimer));
  }
  button.textContent = successText;
  const timerId = window.setTimeout(() => {
    button.textContent = defaultText;
    delete button.dataset.resetTimer;
  }, 1800);
  button.dataset.resetTimer = String(timerId);
}


function downloadJson() {
  if (!state.latestJsonText) {
    return;
  }
  const blob = new Blob([state.latestJsonText], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "china-b1b2-dossier.json";
  link.click();
  URL.revokeObjectURL(url);
}


async function downloadEncryptedJson() {
  if (!state.latestJsonText) {
    submitStatus.textContent = "请先生成资料。";
    return;
  }
  const passphrase = (encryptPassphraseInput.value || "").trim();
  if (passphrase.length < 8) {
    submitStatus.textContent = "加密密码至少需要8位字符。";
    return;
  }
  downloadEncryptedButton.disabled = true;
  downloadEncryptedButton.textContent = "加密中…";
  try {
    if (!state.offlineMode) {
      const res = await fetch(`${SERVER_BASE}/dossier-document/encrypt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passphrase: passphrase, payload: JSON.parse(state.latestJsonText) }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        const encryptedJson = JSON.stringify(data.encrypted_payload, null, 2);
        const blob = new Blob([encryptedJson], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "china-b1b2-dossier.enc.json";
        link.click();
        URL.revokeObjectURL(url);
        submitStatus.textContent = "已下载加密文件。请妥善保管密码。";
        return;
      }
      throw new Error(data.detail || "服务端加密失败");
    }
    // Offline: encrypt client-side via Web Crypto
    const enc = new TextEncoder();
    const plaintext = enc.encode(state.latestJsonText);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const keyMaterial = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" },
      keyMaterial,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt"]
    );
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, plaintext);
    const payload = {
      format: "ds160-encrypted-v1",
      salt_b64: btoa(String.fromCharCode(...salt)),
      nonce_b64: btoa(String.fromCharCode(...nonce)),
      ciphertext_b64: btoa(String.fromCharCode(...new Uint8Array(ciphertext))),
    };
    const encryptedJson = JSON.stringify(payload, null, 2);
    const blob = new Blob([encryptedJson], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "china-b1b2-dossier.enc.json";
    link.click();
    URL.revokeObjectURL(url);
    submitStatus.textContent = "已下载加密文件（离线模式）。请妥善保管密码。";
  } catch (error) {
    submitStatus.textContent = (error && error.message) ? error.message : "加密导出失败";
  } finally {
    downloadEncryptedButton.disabled = false;
    downloadEncryptedButton.textContent = "下载加密文件";
  }
}


async function copyJson() {
  if (!state.latestJsonText) {
    return;
  }
  try {
    await copyTextToClipboard(state.latestJsonText);
    flashButtonSuccess(copyButton, "已复制", "复制资料内容");
    submitStatus.textContent = "已复制资料内容。下一步去执行页导入即可。";
  } catch {
    submitStatus.textContent = "复制失败，请直接下载资料文件。";
  }
}


if (photoUpload) {
  photoUpload.addEventListener("change", function () {
    const file = photoUpload.files?.[0];
    if (!file) {
      state.photoDataUrl = null;
      photoPreview.style.display = "none";
      return;
    }
    if (!file.type.startsWith("image/")) {
      submitStatus.textContent = "照片必须是 JPEG 或 PNG 格式。";
      photoUpload.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = function (e) {
      const img = new Image();
      img.onload = function () {
        if (img.width < 600 || img.height < 600) {
          submitStatus.textContent = `照片尺寸 ${img.width}x${img.height}，需要至少 600x600 像素（2x2英寸）。`;
          state.photoDataUrl = null;
          photoPreview.style.display = "none";
          return;
        }
        state.photoDataUrl = e.target.result;
        photoPreview.src = e.target.result;
        photoPreview.style.display = "";
        submitStatus.textContent = `照片已就绪：${img.width}x${img.height} 像素`;
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}


function enrichPayloadWithPhoto(payload) {
  if (state.photoDataUrl) {
    if (!Array.isArray(payload.evidence_catalog)) {
      payload.evidence_catalog = [];
    }
    const existing = payload.evidence_catalog.find((e) => e.kind === "photo");
    if (!existing) {
      payload.evidence_catalog.push({
        id: "visa_photo",
        kind: "photo",
        description: "Visa application photo (digital)",
      });
    }
  }
  return payload;
}


manualForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  let payload;
  try {
    payload = manualPayload();
  } catch (error) {
    submitStatus.textContent = error.message || "JSON 字段格式错误。";
    refreshManualValidation(true);
    return;
  }
  const { missing, invalids } = validateDossierPayload(payload);
  if (missing.length || Object.keys(invalids).length) {
    refreshManualValidation(true);
    submitStatus.textContent = "还有未填写或格式不对的信息，请先补齐高亮位置。";
    return;
  }

  clearMissingHighlights();
  payload = enrichPayloadWithPhoto(payload);
  const exportDocument = await buildExportDocument(payload);
  state.latestJsonText = JSON.stringify(exportDocument, null, 2);
  jsonPreview.textContent = state.latestJsonText;
  renderItems(missingFields, [], "当前表单已补齐。", issueCard);
  renderItems(warnings, [], "没有额外提醒。", warningCard);
  downloadButton.disabled = false;
  downloadEncryptedButton.disabled = false;
  copyButton.disabled = false;
  submitStatus.textContent = "整理完成，当前导出的是可直接导入执行页的完整 dossier JSON 对象。";
});

Array.from(manualForm.elements).forEach((field) => {
  if (!field.name) {
    return;
  }
  const eventName = field.type === "checkbox" || field.tagName === "SELECT" ? "change" : "input";
  field.addEventListener(eventName, () => {
    if (fieldHasValue(field.name)) {
      clearFieldHighlight(field.name);
    }
    refreshManualValidation(false);
  });
});

downloadButton.addEventListener("click", downloadJson);
downloadEncryptedButton.addEventListener("click", downloadEncryptedJson);
copyButton.addEventListener("click", copyJson);
downloadButton.disabled = true;
downloadEncryptedButton.disabled = true;
copyButton.disabled = true;

loadSchema().catch((error) => {
  submitStatus.textContent = error.message || "页面初始化失败，请确认服务已启动。";
});
