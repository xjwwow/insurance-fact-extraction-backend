const apiBase = "/api/v1";
const initialParams = new URLSearchParams(window.location.search);
const valueMetricId = document.getElementById("value-metric-id");
const valueCompany = document.getElementById("value-company");
const valueReportType = document.getElementById("value-report-type");
const valueBusinessLine = document.getElementById("value-business-line");
const valueReportYear = document.getElementById("value-report-year");
const valuePeriodType = document.getElementById("value-period-type");
const valueStatus = document.getElementById("value-status");
const valueRefresh = document.getElementById("value-refresh");
const valueSummaryCards = document.getElementById("value-summary-cards");
const valueCount = document.getElementById("value-count");
const valueBody = document.getElementById("value-body");

valueMetricId.value = initialParams.get("canonical_metric_id") || "";

async function apiFetch(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function buildParams() {
  const params = new URLSearchParams({ limit: "2000" });
  if (valueMetricId.value.trim()) params.set("canonical_metric_id", valueMetricId.value.trim());
  if (valueCompany.value) params.set("company_id", valueCompany.value);
  if (valueReportType.value) params.set("report_type", valueReportType.value);
  if (valueBusinessLine.value) params.set("business_line", valueBusinessLine.value);
  if (valueReportYear.value.trim()) params.set("report_year", valueReportYear.value.trim());
  if (valuePeriodType.value) params.set("period_type", valuePeriodType.value);
  if (valueStatus.value) params.set("availability_status", valueStatus.value);
  return params;
}

function renderSummary(values) {
  const autoReady = values.filter((item) => item.availability_status === "AUTO_READY").length;
  const pending = values.filter((item) => item.availability_status === "PENDING_REVIEW").length;
  const manual = values.filter((item) => item.availability_status === "MANUAL_CONFIRMED").length;
  const recheck = values.filter((item) => item.availability_status === "NEEDS_RECHECK").length;
  valueSummaryCards.innerHTML = [
    ["总值", values.length],
    ["自动可用", autoReady],
    ["待审核", pending],
    ["人工确认", manual],
    ["待复核", recheck],
  ].map(([label, value]) => `<article class="summary-card"><div class="metric-label">${label}</div><strong>${value}</strong></article>`).join("");
}

function renderValues(values) {
  valueCount.textContent = `${values.length} 条`;
  if (!values.length) {
    valueBody.innerHTML = '<tr><td colspan="9"><div class="empty-state">当前筛选条件下没有指标值。</div></td></tr>';
    return;
  }
  valueBody.innerHTML = values.map((item) => {
    const viewerUrl = item.viewer_url.includes("?") ? `${item.viewer_url}&origin=metrics-values` : `${item.viewer_url}?origin=metrics-values`;
    return `
      <tr>
        <td>${item.metric_name || "-"}<div class="recent-meta">${item.metric_code || "-"}</div></td>
        <td>${item.company_label}</td>
        <td>${item.document_label}<div class="recent-meta">${item.report_type_label} / ${item.business_line_label}</div></td>
        <td>${item.period_label || item.period_type || "-"}</td>
        <td>${item.value_raw || "-"}</td>
        <td>${item.value_numeric || "-"}</td>
        <td>${item.unit_std || item.unit_raw || "-"}</td>
        <td>${item.availability_label}<div class="recent-meta">${item.review_status}</div></td>
        <td><a class="table-link" href="${viewerUrl}" target="_blank" rel="noreferrer">P.${item.source_page_no || "-"} / ${item.table_title}</a></td>
      </tr>
    `;
  }).join("");
}

async function loadValues() {
  const values = await apiFetch(`${apiBase}/metrics/values?${buildParams().toString()}`);
  renderSummary(values);
  renderValues(values);
}

valueRefresh.addEventListener("click", () => loadValues().catch((error) => { valueBody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${error.message}</div></td></tr>`; }));
loadValues().catch((error) => {
  valueBody.innerHTML = `<tr><td colspan="9"><div class="empty-state">${error.message}</div></td></tr>`;
});
