const apiBase = "/api/v1";
const metricCompanyFilter = document.getElementById("metric-company-filter");
const metricSearch = document.getElementById("metric-search");
const metricRefresh = document.getElementById("metric-refresh");
const metricBootstrap = document.getElementById("metric-bootstrap");
const metricsCount = document.getElementById("metrics-count");
const metricTree = document.getElementById("metric-tree");
const metricSummaryCards = document.getElementById("metric-summary-cards");
const metricResultBody = document.getElementById("metric-result-body");
const metricDetail = document.getElementById("metric-detail");
const metricDetailMeta = document.getElementById("metric-detail-meta");
const metricOpenValues = document.getElementById("metric-open-values");
const metricEvidenceBody = document.getElementById("metric-evidence-body");
const metricEvidenceMeta = document.getElementById("metric-evidence-meta");
const metricImportFile = document.getElementById("metric-import-file");
const metricImportPreview = document.getElementById("metric-import-preview");
const metricImportSubmit = document.getElementById("metric-import-submit");
const metricImportResult = document.getElementById("metric-import-result");

let metrics = [];
let metricTreeData = [];
let selectedMetricId = null;
let selectedCategory = null;
let selectedSubcategory = null;

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function visibleMetrics() {
  const keyword = metricSearch.value.trim().toLowerCase();
  return metrics.filter((metric) => {
    if (selectedCategory && (metric.category || "未分类") !== selectedCategory) return false;
    if (selectedSubcategory && (metric.subcategory || "未分组") !== selectedSubcategory) return false;
    if (!keyword) return true;
    return [metric.metric_name, metric.metric_code, metric.category, metric.subcategory].filter(Boolean).join(" ").toLowerCase().includes(keyword);
  });
}

function renderSummaryCards() {
  const items = visibleMetrics();
  const activeCategory = selectedSubcategory ? `${selectedCategory} / ${selectedSubcategory}` : (selectedCategory || "全部分类");
  metricSummaryCards.innerHTML = [
    ["正式指标", metrics.length],
    ["当前结果", items.length],
    ["当前分组", activeCategory],
    ["公司过滤", metricCompanyFilter.value || "全部"],
  ].map(([label, value]) => `<article class="summary-card"><div class="metric-label">${label}</div><strong>${value}</strong></article>`).join("");
}

function renderTree() {
  metricTree.innerHTML = metricTreeData.map((category) => `
    <details class="outline-node" ${selectedCategory === category.title ? "open" : ""}>
      <summary><span class="outline-summary-main">${category.title}</span><span class="outline-summary-meta"><span class="outline-stat">${category.count} 个</span></span></summary>
      <div class="outline-children">
        <button class="outline-table ${selectedCategory === category.title && !selectedSubcategory ? "active" : ""}" type="button" data-category="${category.title}" data-subcategory="">全部</button>
        ${(category.children || []).map((child) => `<button class="outline-table ${selectedCategory === category.title && selectedSubcategory === child.title ? "active" : ""}" type="button" data-category="${category.title}" data-subcategory="${child.title}"><span class="outline-table-title">${child.title}</span><span class="outline-page">${child.count}</span></button>`).join("")}
      </div>
    </details>
  `).join("");
}

function renderResults() {
  const items = visibleMetrics();
  metricsCount.textContent = `${items.length} 个指标`;
  if (!items.length) {
    metricResultBody.innerHTML = '<tr><td colspan="6"><div class="empty-state">没有匹配的正式指标。</div></td></tr>';
    return;
  }
  metricResultBody.innerHTML = items.map((metric) => `
    <tr class="row-clickable ${selectedMetricId === metric.canonical_metric_id ? "active-row" : ""}" data-metric-id="${metric.canonical_metric_id}">
      <td>${metric.metric_code || "-"}</td>
      <td>${metric.metric_name}</td>
      <td>${metric.category || "未分类"}</td>
      <td>${metric.subcategory || "未分组"}</td>
      <td>${metric.lifecycle_status}</td>
      <td><a class="table-link" href="/metrics/values?canonical_metric_id=${metric.canonical_metric_id}">查看值</a></td>
    </tr>
  `).join("");
}

function renderMetricDetail(metric) {
  selectedMetricId = metric.canonical_metric_id;
  renderResults();
  metricDetailMeta.textContent = `${metric.metric_code || "-"} / ${metric.category || "未分类"} / ${metric.lifecycle_status}`;
  metricOpenValues.href = `/metrics/values?canonical_metric_id=${metric.canonical_metric_id}`;
  metricOpenValues.classList.remove("hidden");
  const dependencies = metric.dependencies || [];
  const aliases = metric.aliases || [];
  metricDetail.className = "detail-shell";
  metricDetail.innerHTML = `
    <div class="detail-section"><h4>${metric.metric_name}</h4><p>${metric.definition || "暂无定义"}</p></div>
    <div class="detail-grid two-column top-gap">
      <div><div class="metric-label">标准编号</div><strong>${metric.metric_code || "-"}</strong></div>
      <div><div class="metric-label">父级指标</div><strong>${metric.parent_canonical_metric_id || "-"}</strong></div>
      <div><div class="metric-label">层级深度</div><strong>${metric.hierarchy_depth}</strong></div>
      <div><div class="metric-label">排序</div><strong>${metric.sort_order}</strong></div>
      <div><div class="metric-label">默认单位</div><strong>${metric.default_unit || "-"}</strong></div>
      <div><div class="metric-label">值类型</div><strong>${metric.value_type || "-"}</strong></div>
    </div>
    <div class="detail-section top-gap"><div class="metric-label">公式表达式</div><div>${metric.formula_expression || "暂无公式"}</div></div>
    <div class="detail-section top-gap"><div class="metric-label">公式依赖</div><div class="chip-row">${dependencies.length ? dependencies.map((item) => `<span class="chip">${item.depends_on_metric_code || item.depends_on_metric_id} / ${item.depends_on_metric_name || "-"}</span>`).join("") : '<span class="empty-inline">暂无依赖</span>'}</div></div>
    <div class="detail-section top-gap"><div class="metric-label">别名</div><div class="chip-row">${aliases.length ? aliases.map((alias) => `<span class="chip">${alias.alias_text}</span>`).join("") : '<span class="empty-inline">暂无别名</span>'}</div></div>
  `;

  const evidences = metric.evidences || [];
  metricEvidenceMeta.textContent = `${evidences.length} 条`;
  metricEvidenceBody.innerHTML = evidences.length ? evidences.map((evidence) => `
    <tr class="row-clickable evidence-row" data-viewer-url="${evidence.viewer_url || ""}">
      <td>${evidence.source_page_no || "-"}</td>
      <td>${evidence.raw_metric_text || "-"}</td>
      <td>${evidence.period_type || "-"}</td>
      <td>${evidence.unit_std || "-"}</td>
      <td>${evidence.document_label || "-"}</td>
      <td>${evidence.table_label || evidence.table_title || "未命名表格"}</td>
    </tr>
  `).join("") : '<tr><td colspan="6"><div class="empty-state">暂无证据链。</div></td></tr>';
}

async function loadMetricDetail(metricId) {
  const metric = await apiFetch(`${apiBase}/metrics/${metricId}`);
  renderMetricDetail(metric);
}

async function loadData() {
  const params = new URLSearchParams({ limit: "1000" });
  if (metricCompanyFilter.value) params.set("company_id", metricCompanyFilter.value);
  const [metricItems, treeItems] = await Promise.all([
    apiFetch(`${apiBase}/metrics?${params.toString()}`),
    apiFetch(`${apiBase}/metrics/tree${metricCompanyFilter.value ? `?company_id=${metricCompanyFilter.value}` : ""}`),
  ]);
  metrics = metricItems;
  metricTreeData = treeItems;
  renderTree();
  renderSummaryCards();
  renderResults();
  if (visibleMetrics().length) await loadMetricDetail(visibleMetrics()[0].canonical_metric_id);
  else {
    metricDetail.className = "detail-shell empty-state";
    metricDetail.textContent = "没有可展示的正式指标。";
    metricEvidenceBody.innerHTML = '<tr><td colspan="6"><div class="empty-state">暂无证据链。</div></td></tr>';
    metricEvidenceMeta.textContent = "0 条";
    metricOpenValues.classList.add("hidden");
  }
}

async function handleMetricImport(endpoint) {
  const file = metricImportFile.files?.[0];
  if (!file) throw new Error("请先选择指标模板文件");
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch(`${apiBase}${endpoint}`, { method: "POST", body: formData });
}

function renderImportPayload(result, kind) {
  const errors = result.errors || [];
  metricImportResult.className = "detail-shell";
  metricImportResult.innerHTML = kind === "preview" ? `
    <div class="detail-grid two-column"><div><div class="metric-label">总行数</div><strong>${result.total_rows}</strong></div><div><div class="metric-label">有效行</div><strong>${result.valid_rows}</strong></div></div>
    <div class="detail-section top-gap"><div class="metric-label">预览</div><div class="chip-row">${(result.preview_items || []).length ? result.preview_items.slice(0, 10).map((item) => `<span class="chip">${item.metric_code} / ${item.metric_name}</span>`).join("") : '<span class="empty-inline">暂无可导入行</span>'}</div></div>
    <div class="detail-section top-gap">${errors.length ? `<div class="empty-state">${errors.join("<br>")}</div>` : '<div class="empty-inline">未发现错误</div>'}</div>
  ` : `
    <div class="detail-grid two-column"><div><div class="metric-label">新增指标</div><strong>${result.metrics_created}</strong></div><div><div class="metric-label">更新指标</div><strong>${result.metrics_updated}</strong></div><div><div class="metric-label">新增别名</div><strong>${result.aliases_created}</strong></div><div><div class="metric-label">更新别名</div><strong>${result.aliases_updated}</strong></div></div>
    <div class="detail-section top-gap">${errors.length ? `<div class="empty-state">${errors.join("<br>")}</div>` : '<div class="empty-inline">导入完成，无错误。</div>'}</div>
  `;
}

metricRefresh.addEventListener("click", () => loadData().catch((error) => { metricResultBody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${error.message}</div></td></tr>`; }));
metricBootstrap.addEventListener("click", async () => {
  metricBootstrap.disabled = true;
  try { await apiFetch(`${apiBase}/metrics/bootstrap`, { method: "POST" }); await loadData(); }
  catch (error) { metricDetail.className = "detail-shell empty-state"; metricDetail.textContent = error.message; }
  finally { metricBootstrap.disabled = false; }
});
metricImportPreview.addEventListener("click", async () => { try { renderImportPayload(await handleMetricImport("/metrics/import/preview"), "preview"); } catch (error) { metricImportResult.className = "empty-state"; metricImportResult.textContent = error.message; } });
metricImportSubmit.addEventListener("click", async () => { try { renderImportPayload(await handleMetricImport("/metrics/import"), "import"); await loadData(); } catch (error) { metricImportResult.className = "empty-state"; metricImportResult.textContent = error.message; } });
metricCompanyFilter.addEventListener("change", () => loadData().catch((error) => { metricResultBody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${error.message}</div></td></tr>`; }));
metricSearch.addEventListener("input", () => { renderSummaryCards(); renderResults(); });
metricTree.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-category]");
  if (!button) return;
  selectedCategory = button.dataset.category || null;
  selectedSubcategory = button.dataset.subcategory || null;
  renderTree();
  renderSummaryCards();
  renderResults();
});
metricResultBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-metric-id]");
  if (!row) return;
  loadMetricDetail(row.dataset.metricId).catch((error) => { metricDetail.className = "detail-shell empty-state"; metricDetail.textContent = error.message; });
});
metricEvidenceBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-viewer-url]");
  if (!row?.dataset?.viewerUrl) return;
  const url = row.dataset.viewerUrl.includes("?") ? `${row.dataset.viewerUrl}&origin=metrics-library` : `${row.dataset.viewerUrl}?origin=metrics-library`;
  window.open(url, "_blank", "noopener,noreferrer");
});

loadData().catch((error) => {
  metricResultBody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${error.message}</div></td></tr>`;
});
