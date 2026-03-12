const apiBase = "/api/v1";
const listNode = document.getElementById("metric-review-list");
const queueCount = document.getElementById("queue-count");
const companyFilter = document.getElementById("company-filter");
const reviewerInput = document.getElementById("reviewer");
const refreshButton = document.getElementById("refresh-button");

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function renderQueue(items) {
  queueCount.textContent = `${items.length} 项`;
  if (!items.length) {
    listNode.innerHTML = '<div class="empty-state">当前没有待处理的候选指标。</div>';
    return;
  }

  listNode.innerHTML = items.map((item) => {
    const suggestions = item.suggested_targets.map((target) => `
      <option value="${target.canonical_metric_id}">
        ${target.metric_name} (${target.metric_code || "-"}) / score ${target.score}
      </option>
    `).join("");

    return `
      <article class="review-card">
        <div class="review-card-header">
          <div>
            <strong>${item.metric_name}</strong>
            <div class="recent-meta">${item.canonical_metric_id}</div>
          </div>
          <span class="panel-tag">${item.confidence_score}</span>
        </div>
        <div class="review-card-body">
          <div class="recent-meta">company=${item.company_id || "-"} / evidence=${item.evidence_count} / aliases=${item.alias_count} / facts=${item.fact_count}</div>
          <div class="recent-meta">pages=${item.pages.join(", ") || "-"}</div>
          <div class="recent-meta">aliases=${item.sample_aliases.join(" | ") || "-"}</div>
          <label class="field compact">
            <span>并入标准指标</span>
            <select data-target-select="${item.canonical_metric_id}">
              <option value="">请选择目标标准指标</option>
              ${suggestions}
            </select>
          </label>
        </div>
        <div class="form-actions top-gap">
          <button class="button-primary" type="button" data-merge="${item.canonical_metric_id}">并入</button>
          <button class="button-secondary" type="button" data-dismiss="${item.canonical_metric_id}">驳回</button>
        </div>
      </article>
    `;
  }).join("");
}

async function loadQueue() {
  listNode.innerHTML = '<div class="empty-state">加载中...</div>';
  const params = new URLSearchParams({ limit: "100" });
  if (companyFilter.value.trim()) {
    params.set("company_id", companyFilter.value.trim());
  }
  const items = await apiFetch(`${apiBase}/metrics/review/queue?${params.toString()}`);
  renderQueue(items);
}

async function mergeMetric(sourceId) {
  const reviewer = reviewerInput.value.trim();
  if (!reviewer) {
    throw new Error("请填写审核人");
  }
  const select = document.querySelector(`[data-target-select="${sourceId}"]`);
  const targetId = select?.value?.trim();
  if (!targetId) {
    throw new Error("请选择目标标准指标");
  }
  await apiFetch(`${apiBase}/metrics/review/${sourceId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer, target_canonical_metric_id: targetId }),
  });
  await loadQueue();
}

async function dismissMetric(sourceId) {
  const reviewer = reviewerInput.value.trim();
  if (!reviewer) {
    throw new Error("请填写审核人");
  }
  await apiFetch(`${apiBase}/metrics/review/${sourceId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer }),
  });
  await loadQueue();
}

refreshButton.addEventListener("click", () => {
  loadQueue().catch((error) => {
    listNode.innerHTML = `<div class="empty-state">${error.message}</div>`;
  });
});

listNode.addEventListener("click", async (event) => {
  const mergeButton = event.target.closest("button[data-merge]");
  const dismissButton = event.target.closest("button[data-dismiss]");
  try {
    if (mergeButton) {
      await mergeMetric(mergeButton.dataset.merge);
    }
    if (dismissButton) {
      await dismissMetric(dismissButton.dataset.dismiss);
    }
  } catch (error) {
    alert(error.message);
  }
});

loadQueue().catch((error) => {
  listNode.innerHTML = `<div class="empty-state">${error.message}</div>`;
});
