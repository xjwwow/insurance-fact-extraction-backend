const apiBase = "/api/v1";

const qaCompany = document.getElementById("qa-company");
const qaYear = document.getElementById("qa-year");
const qaDocument = document.getElementById("qa-document");
const qaReviewer = document.getElementById("qa-reviewer");
const qaRefresh = document.getElementById("qa-refresh");
const qaList = document.getElementById("qa-list");
const qaCount = document.getElementById("qa-count");
const qaDetail = document.getElementById("qa-detail");
const qaDetailMeta = document.getElementById("qa-detail-meta");
const qaApprove = document.getElementById("qa-approve");
const qaCorrectValue = document.getElementById("qa-correct-value");
const qaCorrect = document.getElementById("qa-correct");
const qaRemapTarget = document.getElementById("qa-remap-target");
const qaRemap = document.getElementById("qa-remap");
const qaPageLabel = document.getElementById("qa-page-label");
const qaPagePreview = document.getElementById("qa-page-preview");
const qaOpenViewer = document.getElementById("qa-open-viewer");

let queueItems = [];
let metrics = [];
let selectedFact = null;

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function buildParams() {
  const params = new URLSearchParams({ limit: "200" });
  if (qaCompany.value.trim()) params.set("company_id", qaCompany.value.trim());
  if (qaYear.value.trim()) params.set("report_year", qaYear.value.trim());
  return params;
}

function renderQueue() {
  qaCount.textContent = `${queueItems.length} items`;
  if (!queueItems.length) {
    qaList.innerHTML = '<div class="empty-state">当前没有待审核事实。</div>';
    return;
  }
  qaList.innerHTML = queueItems.map((fact) => `
    <button class="list-item ${selectedFact?.fact_id === fact.fact_id ? "active" : ""}" type="button" data-fact-id="${fact.fact_id}">
      <strong>${fact.metric_name_std || fact.fact_id}</strong>
      <span>P.${fact.source_page_no || "-"} / ${fact.value_raw || "-"}</span>
      <span>${fact.document_id}</span>
    </button>
  `).join("");
}

function renderMetricOptions() {
  qaRemapTarget.innerHTML = metrics.length
    ? metrics.map((metric) => `<option value="${metric.canonical_metric_id}">${metric.metric_name} (${metric.metric_code || "-"})</option>`).join("")
    : '<option value="">暂无可选指标</option>';
}

function renderDetail(fact) {
  selectedFact = fact;
  renderQueue();
  qaDetailMeta.textContent = `${fact.document_id} / P.${fact.source_page_no || "-"}`;
  qaDetail.className = "detail-shell";
  qaDetail.innerHTML = `
    <div class="detail-section">
      <h4>${fact.metric_name_std || fact.fact_id}</h4>
      <p>${fact.source_text_snippet || "暂无来源片段"}</p>
    </div>
    <div class="detail-grid two-column">
      <div>
        <div class="metric-label">原值</div>
        <strong>${fact.value_raw || "-"}</strong>
      </div>
      <div>
        <div class="metric-label">归一值</div>
        <strong>${fact.value_numeric || "-"}</strong>
      </div>
      <div>
        <div class="metric-label">验证状态</div>
        <strong>${fact.validation_status}</strong>
      </div>
      <div>
        <div class="metric-label">审核状态</div>
        <strong>${fact.review_status}</strong>
      </div>
      <div>
        <div class="metric-label">可用状态</div>
        <strong>${fact.availability_label || fact.availability_status || "-"}</strong>
      </div>
    </div>
  `;

  qaCorrectValue.value = fact.value_raw || "";
  qaPageLabel.textContent = `Page ${fact.source_page_no || "-"}`;
  qaPagePreview.src = `${apiBase}/documents/${fact.document_id}/pages/${fact.source_page_no || 1}/preview?t=${Date.now()}`;
  qaOpenViewer.href = `/documents/${fact.document_id}/viewer?page=${fact.source_page_no || 1}&table_id=${fact.source_table_id || ""}&fact_id=${fact.fact_id}&origin=qa-workbench`;
}

async function loadMetrics() {
  const params = new URLSearchParams({ limit: "300" });
  if (qaCompany.value.trim()) params.set("company_id", qaCompany.value.trim());
  metrics = await apiFetch(`${apiBase}/metrics?${params.toString()}`);
  renderMetricOptions();
}

async function loadQueue() {
  qaList.innerHTML = '<div class="empty-state">加载中...</div>';
  const params = buildParams();
  const [reviewQueue, pendingFacts] = await Promise.all([
    apiFetch(`${apiBase}/review/queue?${params.toString()}`).catch(() => []),
    qaDocument.value.trim()
      ? apiFetch(`${apiBase}/facts?document_id=${encodeURIComponent(qaDocument.value.trim())}&review_status=PENDING&limit=200`)
      : Promise.resolve(null),
  ]);

  queueItems = Array.isArray(pendingFacts) ? pendingFacts : reviewQueue;
  renderQueue();
  if (queueItems.length) {
    renderDetail(queueItems[0]);
  } else {
    selectedFact = null;
    qaDetail.className = "detail-shell empty-state";
    qaDetail.textContent = "当前没有待审核事实。";
  }
}

async function reviewAction(path, payload) {
  if (!selectedFact) {
    throw new Error("请先选择一个事实");
  }
  await apiFetch(`${apiBase}/review/facts/${selectedFact.fact_id}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadQueue();
}

qaRefresh.addEventListener("click", async () => {
  try {
    await Promise.all([loadMetrics(), loadQueue()]);
  } catch (error) {
    qaList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
});

qaList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-fact-id]");
  if (!button) {
    return;
  }
  const fact = queueItems.find((item) => item.fact_id === button.dataset.factId);
  if (fact) {
    renderDetail(fact);
  }
});

qaApprove.addEventListener("click", async () => {
  try {
    await reviewAction("approve", { reviewer: qaReviewer.value.trim() || "admin" });
  } catch (error) {
    alert(error.message);
  }
});

qaCorrect.addEventListener("click", async () => {
  try {
    await reviewAction("correct", {
      reviewer: qaReviewer.value.trim() || "admin",
      new_value: qaCorrectValue.value.trim(),
    });
  } catch (error) {
    alert(error.message);
  }
});

qaRemap.addEventListener("click", async () => {
  try {
    const metric = metrics.find((item) => item.canonical_metric_id === qaRemapTarget.value);
    await reviewAction("remap-metric", {
      reviewer: qaReviewer.value.trim() || "admin",
      canonical_metric_id: qaRemapTarget.value,
      metric_name_std: metric?.metric_name,
    });
  } catch (error) {
    alert(error.message);
  }
});

Promise.all([loadMetrics(), loadQueue()]).catch((error) => {
  qaList.innerHTML = `<div class="empty-state">${error.message}</div>`;
});
