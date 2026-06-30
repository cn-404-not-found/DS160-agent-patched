const SERVER_BASE = "http://127.0.0.1:8765";

const state = {
  bundle: null,
  currentPageId: null,
  completed: {},
  serverConnected: false,
  dossierLoaded: false,
  applicationId: localStorage.getItem("ds160_application_id") || null,
  logs: [],
  cancelFillAll: false,
  fillAllAbortController: null,
  fillAllDelayId: null,
  fillAllDelayResolve: null,
};

const fillKeyToPageId = {
  personal1: "personal_page_1",
  personal2: "personal_page_2",
  passport: "passport_page",
  travel: "travel_page",
  travel_companions: "travel_companions_page",
  previous_travel: "previous_us_travel_page",
  address_phone: "address_phone_page",
  us_contact: "us_contact_page",
  work_education_present: "work_education_present_page",
  work_education_previous: "work_education_previous_page",
  work_education_additional: "work_education_additional_page",
  family_relatives: "family_relatives_page",
  family_spouse: "family_spouse_page",
  security_part1: "security_part1_page",
  security_part2: "security_part2_page",
  security_part3: "security_part3_page",
  security_part4: "security_part4_page",
  security_part5: "security_part5_page",
};

const pageNav = document.getElementById("page-nav");
const summary = document.getElementById("summary");
const pageTitle = document.getElementById("page-title");
const metricFill = document.getElementById("metric-fill");
const metricReview = document.getElementById("metric-review");
const metricBlocked = document.getElementById("metric-blocked");
const serverStatus = document.getElementById("server-status");
const applicationIdEl = document.getElementById("application-id");
const fillResult = document.getElementById("fill-result");
const fillButton = document.getElementById("fill-page");
const fillContinueButton = document.getElementById("fill-continue");
const fillAllButton = document.getElementById("fill-all");
const cancelFillAllButton = document.getElementById("cancel-fill-all");
const progressBarContainer = document.getElementById("progress-bar-container");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");
const intakeFile = document.getElementById("intake-file");
const intakePassphrase = document.getElementById("intake-passphrase");
const intakePassphraseField = document.getElementById("encrypt-passphrase-field");
const loadIntakeButton = document.getElementById("load-intake");
const intakeDocStatus = document.getElementById("intake-doc-status");


function currentBundle() {
  return state.bundle;
}


function getPage(pageId) {
  return currentBundle()?.pages.find((page) => page.page_id === pageId);
}


function pushLog(level, title, detail) {
  const timestamp = new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  state.logs.unshift({ level, title, detail, timestamp });
  state.logs = state.logs.slice(0, 12);
  renderLogs();
}


function setApplicationId(applicationId) {
  if (!applicationId) return;
  state.applicationId = applicationId;
  localStorage.setItem("ds160_application_id", applicationId);
  if (applicationIdEl) {
    applicationIdEl.textContent = applicationId;
  }
}


function selectDetectedPage(pageKey, silent = false) {
  const pageId = fillKeyToPageId[pageKey] || pageKey;
  if (!pageId || !getPage(pageId)) {
    return false;
  }
  if (state.currentPageId !== pageId) {
    state.currentPageId = pageId;
    render();
    if (!silent) {
      pushLog("info", "当前页", `浏览器当前页已切换为 ${pageId}`);
    }
  }
  return true;
}


async function syncCurrentBrowserPage(options = {}) {
  const { silent = false } = options;
  const res = await fetch(`${SERVER_BASE}/detect-page`, { signal: AbortSignal.timeout(3000) });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "无法读取浏览器当前页");
  }
  setApplicationId(data.application_id);
  if (!selectDetectedPage(data.page_key, silent) && !silent) {
    pushLog("warn", "当前页", `暂不支持 ${data.page_key || "unknown"}`);
  }
  return data;
}


function renderLogs() {
  fillResult.innerHTML = state.logs.length
    ? state.logs
        .map(
          (item) => `
            <article class="terminal-line ${item.level}">
              <header>
                <strong>${item.title}</strong>
                <span>${item.timestamp}</span>
              </header>
              <div class="terminal-detail">${item.detail || "无附加信息"}</div>
            </article>
          `
        )
        .join("")
    : `<article class="terminal-line idle"><header><strong>空</strong><span>--:--:--</span></header><div class="terminal-detail">--</div></article>`;
}


function renderEmptyState() {
  summary.innerHTML = `
    <div class="summary-card">
      <span class="eyebrow">状态</span>
      <strong>未导入</strong>
    </div>
  `;
  pageNav.innerHTML = `
    <section class="flow-section">
      <div class="flow-section-title">页面</div>
      <div class="summary-card">--</div>
    </section>
  `;
  pageTitle.textContent = "--";
  metricFill.textContent = "0";
  metricReview.textContent = "0";
  metricBlocked.textContent = "0";
  if (applicationIdEl) {
    applicationIdEl.textContent = state.applicationId || "--";
  }
  renderLogs();
}


function renderSummary() {
  const bundle = currentBundle();
  const { status_counts: counts, page_count: pages, hard_stops: hardStops } = bundle.summary;
  summary.innerHTML = `
    <div class="summary-card">
      <span class="eyebrow">申请</span>
      <strong>${bundle.case_id}</strong>
    </div>
    <div class="summary-card">
      <span class="eyebrow">可填 / 待确认 / 缺失</span>
      <strong>${counts.ready} / ${counts.needs_review} / ${counts.blocked}</strong>
    </div>
    <div class="summary-card">
      <span class="eyebrow">页面数 / 停止点</span>
      <strong>${pages} / ${hardStops.length}</strong>
    </div>
  `;
}


function renderNav() {
  const bundle = currentBundle();
  pageNav.innerHTML = bundle.navigation
    .map((section) => {
      const buttons = section.pages
        .map((page) => {
          const active = page.page_id === state.currentPageId ? "active" : "";
          const done = state.completed[page.page_id] ? "done" : "";
          const planned = page.status === "planned" ? "planned" : "";
          const reference = page.status === "reference" ? "reference" : "";
          return `
            <button class="page-button ${active} ${done} ${planned} ${reference}" data-page-id="${page.page_id}">
              <div>${page.label}</div>
              <div class="page-meta">${page.status === "implemented" ? "已建模" : page.status === "reference" ? "参考页" : "待补充"}</div>
            </button>
          `;
        })
        .join("");
      return `
        <section class="flow-section">
          <div class="flow-section-title">${section.label}</div>
          ${buttons}
        </section>
      `;
    })
    .join("");

  pageNav.querySelectorAll("[data-page-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.currentPageId = button.dataset.pageId;
      render();
    });
  });
}


function renderMetrics(page) {
  metricFill.textContent = page.autofill_count;
  metricReview.textContent = page.review_count;
  metricBlocked.textContent = page.blocked_count;
}


function render() {
  if (!currentBundle()) {
    renderEmptyState();
    return;
  }
  const page = getPage(state.currentPageId);
  if (!page) return;
  pageTitle.textContent = `${page.label}${state.completed[page.page_id] ? " · 已完成预填" : ""}`;
  renderSummary();
  renderNav();
  renderMetrics(page);
  if (applicationIdEl) {
    applicationIdEl.textContent = state.applicationId || "--";
  }
  renderLogs();
}


async function fetchBundle() {
  const res = await fetch(`${SERVER_BASE}/draft-bundle`, { signal: AbortSignal.timeout(3000) });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "无法构建 draft bundle");
  }
  state.bundle = data.bundle;
  state.currentPageId = data.bundle.pages[0]?.page_id || null;
  state.completed = {};
  pushLog("info", "Bundle", `${data.bundle.pages.length} pages`);
  render();
}


async function checkServerStatus() {
  try {
    const res = await fetch(`${SERVER_BASE}/status`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    state.serverConnected = data.connected;
    state.dossierLoaded = Boolean(data.dossier_document_loaded);
    setApplicationId(data.application_id);
    if (!data.connected) {
      serverStatus.textContent = "未连接浏览器";
      serverStatus.style.color = "var(--c-warn, #f5a623)";
    } else if (!data.ceac_tab_found) {
      serverStatus.textContent = "已连接 (无DS-160标签)";
      serverStatus.style.color = "var(--c-warn, #f5a623)";
    } else {
      serverStatus.textContent = "已连接 ✓";
      serverStatus.style.color = "var(--c-ok, #6fcf97)";
    }
    if (data.dossier_document_loaded) {
      intakeDocStatus.textContent = "已导入";
      if (!currentBundle()) {
        await fetchBundle();
      }
    }
  } catch {
    state.serverConnected = false;
    serverStatus.textContent = "服务未启动";
    serverStatus.style.color = "var(--c-err, #eb5757)";
  }
}


function isEncryptedPayload(payload) {
  return payload && payload.format === "ds160-encrypted-v1";
}


async function loadIntakeDocument() {
  const file = intakeFile.files?.[0];
  if (!file) {
    pushLog("error", "文件", "未选择");
    return;
  }
  loadIntakeButton.disabled = true;
  loadIntakeButton.textContent = "导入中…";
  intakeDocStatus.textContent = "导入中";
  try {
    const text = await file.text();
    const payload = JSON.parse(text);
    const encrypted = isEncryptedPayload(payload);
    if (encrypted) {
      intakePassphraseField.style.display = "";
    }
    let endpoint, body;
    if (encrypted) {
      const passphrase = (intakePassphrase.value || "").trim();
      if (!passphrase) {
        throw new Error("此文件已加密，请输入密码。");
      }
      endpoint = `${SERVER_BASE}/dossier-document/decrypt`;
      body = JSON.stringify({ encrypted_payload: payload, passphrase });
    } else {
      endpoint = `${SERVER_BASE}/dossier-document`;
      body = JSON.stringify(payload);
    }
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "导入资料文档失败");
    }
    intakeDocStatus.textContent = "已导入";
    if (encrypted) {
      intakePassphraseField.style.display = "none";
      intakePassphrase.value = "";
    }
    await fetchBundle();
    pushLog("success", "导入", file.name + (encrypted ? " (已解密)" : ""));
  } catch (error) {
    pushLog("error", "导入失败", error.message || "失败");
    intakeDocStatus.textContent = "导入失败";
  } finally {
    loadIntakeButton.disabled = false;
    loadIntakeButton.textContent = "导入 JSON";
    checkServerStatus();
  }
}


intakeFile.addEventListener("change", function () {
  const file = intakeFile.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function (e) {
    try {
      const payload = JSON.parse(e.target.result);
      if (isEncryptedPayload(payload)) {
        intakePassphraseField.style.display = "";
        intakeDocStatus.textContent = "已加密 - 需要密码";
      } else {
        intakePassphraseField.style.display = "none";
        intakePassphrase.value = "";
        intakeDocStatus.textContent = "未导入";
      }
    } catch {
      intakePassphraseField.style.display = "none";
      intakeDocStatus.textContent = "未导入";
    }
  };
  reader.readAsText(file);
});


loadIntakeButton.addEventListener("click", loadIntakeDocument);

fillButton.addEventListener("click", async () => {
  if (!currentBundle()) {
    pushLog("error", "填入", "未导入");
    return;
  }
  fillButton.disabled = true;
  fillButton.textContent = "填入中…";
  try {
    await syncCurrentBrowserPage({ silent: true });
    const filledPageId = state.currentPageId;
    const res = await fetch(`${SERVER_BASE}/fill-page`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page_id: null }),
    });
    const data = await res.json();
    setApplicationId(data.application_id);
    if (res.ok && data.ok) {
      state.completed[filledPageId] = true;
      render();
      pushLog(
        "success",
        `填入成功 (${data.page_key})`,
        `已填: ${data.filled.join(", ") || "无"} | 缺失: ${data.missing.join(", ") || "无"}`
      );
    } else {
      const msg = data.detail || data.message || "填入失败";
      pushLog("error", "填入失败", msg);
    }
  } catch {
    pushLog("error", "网络错误", "服务未启动");
  } finally {
    fillButton.disabled = false;
    fillButton.textContent = "一键填入";
    checkServerStatus();
  }
});


function disableFillButtons() {
  fillButton.disabled = true;
  fillContinueButton.disabled = true;
  fillAllButton.disabled = true;
}

function enableFillButtons() {
  fillButton.disabled = false;
  fillContinueButton.disabled = false;
  fillAllButton.disabled = false;
  fillButton.textContent = "一键填入";
  fillContinueButton.textContent = "填完并翻页";
  fillAllButton.textContent = "一键填完全部";
}


fillContinueButton.addEventListener("click", async () => {
  if (!currentBundle() || !state.currentPageId) {
    pushLog("error", "翻页", "未导入或未选中页面");
    return;
  }
  disableFillButtons();
  fillContinueButton.textContent = "填入翻页中…";
  try {
    await syncCurrentBrowserPage({ silent: true });
    const filledPageId = state.currentPageId;
    const res = await fetch(`${SERVER_BASE}/fill-and-continue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page_id: null }),
    });
    const data = await res.json();
    setApplicationId(data.application_id);
    if (res.ok && data.ok) {
      state.completed[filledPageId] = true;
      if (data.new_page_key) {
        state.currentPageId = data.new_page_key;
      }
      render();
      pushLog(
        "success",
        `填完并翻页 (${data.page_key} → ${data.new_page_key || "?"})`,
        `已填: ${data.filled.join(", ") || "无"} | 缺失: ${data.missing.join(", ") || "无"}`
      );
    } else {
      const msg = data.detail || data.message || "填完翻页失败";
      pushLog("error", "翻页失败", msg);
    }
  } catch {
    pushLog("error", "网络错误", "服务未启动");
  } finally {
    enableFillButtons();
    checkServerStatus();
  }
});


cancelFillAllButton.addEventListener("click", () => {
  state.cancelFillAll = true;
  if (state.fillAllAbortController) {
    state.fillAllAbortController.abort();
  }
  if (state.fillAllDelayId) {
    clearTimeout(state.fillAllDelayId);
    state.fillAllDelayId = null;
  }
  if (state.fillAllDelayResolve) {
    state.fillAllDelayResolve();
    state.fillAllDelayResolve = null;
  }
  pushLog("warn", "取消", "正在停止批量填入…");
});

fillAllButton.addEventListener("click", async () => {
  if (!currentBundle()) {
    pushLog("error", "全部填入", "未导入");
    return;
  }
  const implementePages = currentBundle().pages.filter(
    (page) => page.status === "implemented"
  );
  if (!implementePages.length) {
    pushLog("error", "全部填入", "没有可填入的页面");
    return;
  }
  try {
    await syncCurrentBrowserPage({ silent: false });
  } catch (error) {
    pushLog("warn", "当前页", error.message || "无法读取浏览器当前页，使用左侧选中页");
  }
  const startIndex = Math.max(0, implementePages.findIndex((page) => page.page_id === state.currentPageId));

  disableFillButtons();
  state.cancelFillAll = false;
  progressBarContainer.style.display = "block";
  fillAllButton.textContent = "全部填入中…";
  pushLog("info", "全部填入", `从第 ${startIndex + 1}/${implementePages.length} 页开始`);

  let stopped = false;
  for (let index = startIndex; index < implementePages.length; index += 1) {
    if (state.cancelFillAll) {
      pushLog("warn", "已取消", `停在 ${implementePages[index]?.label || "?"}`);
      stopped = true;
      break;
    }
    const page = implementePages[index];
    state.currentPageId = page.page_id;
    render();

    const current = index + 1;
    const total = implementePages.length;
    const pct = Math.round((current / total) * 100);
    progressBar.style.width = `${pct}%`;
    progressText.textContent = `${current} / ${total}`;
    fillAllButton.textContent = `填入中 ${current}/${total}…`;

    try {
      state.fillAllAbortController = new AbortController();
      const res = await fetch(`${SERVER_BASE}/fill-and-continue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: null }),
        signal: state.fillAllAbortController.signal,
      });
      state.fillAllAbortController = null;
      const data = await res.json();
      setApplicationId(data.application_id);
      if (state.cancelFillAll) {
        pushLog("warn", "已取消", `停在 ${page.label}`);
        stopped = true;
        break;
      }
      if (res.ok && data.ok) {
        state.completed[page.page_id] = true;
        if (data.new_page_key) {
          state.currentPageId = data.new_page_key;
        }
        render();
        const vr = data.validations || {};
        const mmCount = (vr.mismatches || []).length;
        pushLog(
          "success",
          `${current}/${total} (${data.page_key})`,
          `已填: ${data.filled.length} | 校验不匹配: ${mmCount} | 翻到: ${data.new_page_key || "?"}`
        );
      } else {
        const msg = data.detail || data.message || "填入失败";
        pushLog("error", `停在 ${page.label}`, msg);
        stopped = true;
        break;
      }
    } catch (error) {
      state.fillAllAbortController = null;
      if (state.cancelFillAll || error.name === "AbortError") {
        pushLog("warn", "已取消", `停在 ${page.label}`);
        stopped = true;
        break;
      }
      pushLog("error", "网络错误", `停在 ${page.label}`);
      stopped = true;
      break;
    }
    if (!state.cancelFillAll) {
      await new Promise((resolve) => {
        state.fillAllDelayResolve = resolve;
        state.fillAllDelayId = setTimeout(() => {
          state.fillAllDelayId = null;
          state.fillAllDelayResolve = null;
          resolve();
        }, 2000);
      });
    }
  }

  progressBarContainer.style.display = "none";
  progressBar.style.width = "0%";
  state.fillAllAbortController = null;
  if (state.fillAllDelayId) {
    clearTimeout(state.fillAllDelayId);
    state.fillAllDelayId = null;
  }
  state.fillAllDelayResolve = null;
  if (!stopped) {
    pushLog("success", "全部完成", `${implementePages.length} 页已顺序填入`);
  }
  enableFillButtons();
  checkServerStatus();
});


async function checkCheckpoint() {
  try {
    const res = await fetch(`${SERVER_BASE}/fill/checkpoint`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return;
    const data = await res.json();
    if (data.checkpoint && data.checkpoint.completed_pages?.length) {
      const cp = data.checkpoint;
      setApplicationId(cp.application_id);
      pushLog("info", "断点续填", `上次完成 ${cp.completed_pages.length} 页，停在 ${cp.current_page_key || '?'}`);
      state.completed = {};
      cp.completed_pages.forEach((pageId) => { state.completed[pageId] = true; });
      if (cp.current_page_key) {
        state.currentPageId = cp.current_page_key;
      }
      render();
    }
  } catch {
    // checkpoint is best-effort
  }
}


async function clearCheckpoint() {
  try {
    await fetch(`${SERVER_BASE}/fill/checkpoint`, {
      method: "DELETE",
      signal: AbortSignal.timeout(2000),
    });
    state.completed = {};
    pushLog("info", "清除", "断点已清除");
    render();
  } catch {
    // best effort
  }
}


checkServerStatus();
checkCheckpoint();
setInterval(checkServerStatus, 5000);
render();
