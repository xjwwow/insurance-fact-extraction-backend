const apiBase = "/api/v1";
const documentId = window.location.pathname.split("/")[2];
const qaPageTitle = document.getElementById("qa-page-title");
const qaPageSubtitle = document.getElementById("qa-page-subtitle");
const qaBackViewer = document.getElementById("qa-back-viewer");
const qaRefresh = document.getElementById("qa-refresh");
const qaExport = document.getElementById("qa-export");
const qaSummaryCards = document.getElementById("qa-summary-cards");
const qaRowCount = document.getElementById("qa-row-count");
const qaResultBody = document.getElementById("qa-result-body");
const qaDetailShell = document.getElementById("qa-detail-shell");
const qaManualStatus = document.getElementById("qa-manual-status");
const qaManualNote = document.getElementById("qa-manual-note");
const qaReviewer = document.getElementById("qa-reviewer");
const qaSaveReview = document.getElementById("qa-save-review");
const qaOpenViewerLink = document.getElementById("qa-open-viewer-link");

let qaRows = [];
let selectedRow = null;

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function renderSummary() {
  const passCount = qaRows.filter((row) => row.overall_status === "PASS").length;
  const reviewCount = qaRows.filter((row) => row.overall_status === "REVIEW").length;
  const failCount = qaRows.filter((row) => row.overall_status === "FAIL").length;
  const manualCount = qaRows.filter((row) => row.manual_status).length;
  qaSummaryCards.innerHTML = [
    ["总表格", qaRows.length],
    ["自动通过", passCount],
    ["自动待复核", reviewCount],
    ["自动失败", failCount],
    ["已人工标注", manualCount],
  ].map(([label, value]) => `<article class="summary-card"><div class="metric-label">${label}</div><strong>${value}</strong></article>`).join("");
}

function renderRows() {
  qaRowCount.textContent = `${qaRows.length} 张表`;
  if (!qaRows.length) {
    qaResultBody.innerHTML = '<tr><td colspan="8"><div class="empty-state">当前文档没有表格质检记录。</div></td></tr>';
    return;
  }
  qaResultBody.innerHTML = qaRows.map((row) => `
    <tr class="row-clickable ${selectedRow?.table_id === row.table_id ? "active-row" : ""}" data-table-id="${row.table_id}">
      <td>${row.section_path}</td>
      <td>P.${row.page_start}</td>
      <td>${row.table_title}</td>
      <td>${row.parse_engine}</td>
      <td>${row.header_levels}</td>
      <td>${row.bbox_quality}</td>
      <td>${row.overall_status}</td>
      <td>${row.manual_status || "-"}</td>
    </tr>
  `).join("");
}

function renderDetail(row) {
  selectedRow = row;
  renderRows();
  qaManualStatus.value = row.manual_status || "";
  qaManualNote.value = row.manual_note || "";
  qaOpenViewerLink.href = `${row.viewer_url}&origin=document-qa`;
  qaDetailShell.className = "detail-shell";
  qaDetailShell.innerHTML = `
    <div class="detail-section">
      <h4>${row.table_title}</h4>
      <p>${row.section_path} / P.${row.page_start}${row.page_end !== row.page_start ? `-P.${row.page_end}` : ""}</p>
    </div>
    <div class="detail-grid two-column top-gap">
      <div><div class="metric-label">解析引擎</div><strong>${row.parse_engine}</strong></div>
      <div><div class="metric-label">表头层级</div><strong>${row.header_levels}</strong></div>
      <div><div class="metric-label">BBox 质量</div><strong>${row.bbox_quality}</strong></div>
      <div><div class="metric-label">自动状态</div><strong>${row.overall_status}</strong></div>
    </div>
    <div class="detail-section top-gap">
      <div class="metric-label">自动预警</div>
      <div class="chip-row">${row.auto_flags.length ? row.auto_flags.map((flag) => `<span class="chip">${flag}</span>`).join("") : '<span class="empty-inline">无</span>'}</div>
    </div>
  `;
}

async function loadRows() {
  qaRows = await apiFetch(`${apiBase}/documents/${documentId}/qa`);
  renderSummary();
  renderRows();
  if (qaRows.length) renderDetail(qaRows[0]);
}

async function saveReview() {
  if (!selectedRow) throw new Error("请先选择一张表");
  const payload = {
    manual_status: qaManualStatus.value || null,
    manual_note: qaManualNote.value.trim() || null,
    reviewer: qaReviewer.value.trim() || null,
  };
  await apiFetch(`${apiBase}/documents/${documentId}/qa/reviews/${selectedRow.table_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadRows();
  const refreshed = qaRows.find((row) => row.table_id === selectedRow.table_id);
  if (refreshed) renderDetail(refreshed);
}

qaRefresh.addEventListener("click", () => loadRows().catch((error) => { qaResultBody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${error.message}</div></td></tr>`; }));
qaSaveReview.addEventListener("click", () => saveReview().catch((error) => { qaDetailShell.className = "detail-shell empty-state"; qaDetailShell.textContent = error.message; }));
qaResultBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-table-id]");
  if (!row) return;
  const item = qaRows.find((value) => value.table_id === row.dataset.tableId);
  if (item) renderDetail(item);
});

qaBackViewer.href = `/documents/${documentId}/viewer`;
qaExport.href = `${apiBase}/documents/${documentId}/qa/export`;
qaPageTitle.textContent = `文档表格质检`;
qaPageSubtitle.textContent = `文档 ${documentId} 的自动质检结果与人工标注。`;
loadRows().catch((error) => {
  qaResultBody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${error.message}</div></td></tr>`;
});
