const apiBase = "/api/v1";

const timeline = document.getElementById("status-timeline");
const resultCard = document.getElementById("result-card");
const submitButton = document.getElementById("submit-button");
const uploadForm = document.getElementById("upload-form");
const recentDocuments = document.getElementById("recent-documents");

function addTimelineItem(title, message, state = "active") {
  const li = document.createElement("li");
  li.className = `timeline-item ${state}`;
  li.innerHTML = `
    <span class="timeline-step">${timeline.children.length + 1}</span>
    <div>
      <strong>${title}</strong>
      <p>${message}</p>
    </div>
  `;
  timeline.appendChild(li);
}

function setResult(parseResult) {
  resultCard.classList.remove("hidden");
  document.getElementById("result-document-id").textContent = parseResult.document_id;
  document.getElementById("result-pages").textContent = parseResult.pages_parsed ?? "-";
  document.getElementById("result-tables").textContent = parseResult.tables_detected ?? "-";
  document.getElementById("result-facts").textContent = parseResult.facts_extracted ?? "-";
  document.getElementById("viewer-link").href = `/documents/${parseResult.document_id}/viewer`;
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function pollTask(taskId) {
  while (true) {
    const status = await apiFetch(`${apiBase}/documents/parse-tasks/${taskId}`);
    addTimelineItem("轮询任务状态", `当前状态: ${status.task_state}`);

    if (status.ready && status.successful) {
      return status.parse_result;
    }
    if (status.ready && status.failed) {
      throw new Error(status.error || "Parse task failed");
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

function renderRecentDocuments(documents) {
  if (!documents.length) {
    recentDocuments.innerHTML = '<div class="empty-state">暂无已上传文档。</div>';
    return;
  }

  recentDocuments.innerHTML = documents.map((document) => `
    <article class="recent-item">
      <a href="/documents/${document.document_id}/viewer">
        <strong>${document.document_label || document.company_label || document.company_id}</strong>
        <div class="recent-meta">${document.business_line_label || document.business_line || "-"} / ${document.parse_status}</div>
        <div class="recent-meta">${document.document_id}</div>
      </a>
    </article>
  `).join("");
}

async function loadRecentDocuments() {
  const documents = await apiFetch(`${apiBase}/documents?limit=8`);
  renderRecentDocuments(documents);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  resultCard.classList.add("hidden");
  submitButton.disabled = true;
  timeline.innerHTML = "";

  const formData = new FormData(uploadForm);

  try {
    addTimelineItem("上传文件", "正在发送 PDF 与元信息到后端。");
    const uploadResult = await apiFetch(`${apiBase}/documents/upload`, {
      method: "POST",
      body: formData,
    });

    addTimelineItem("上传完成", `文档已入库: ${uploadResult.document_id}`, "success");
    addTimelineItem("提交解析", "正在创建解析任务。");

    const parseTask = await apiFetch(`${apiBase}/documents/${uploadResult.document_id}/parse`, {
      method: "POST",
    });

    addTimelineItem("任务已提交", `Task ID: ${parseTask.task_id}`, "success");

    const parseResult = await pollTask(parseTask.task_id);
    addTimelineItem("解析完成", "结果已生成，可以进入对照页。", "success");
    setResult(parseResult);
    await loadRecentDocuments();
  } catch (error) {
    addTimelineItem("执行失败", error.message, "error");
  } finally {
    submitButton.disabled = false;
  }
});

loadRecentDocuments().catch((error) => {
  recentDocuments.innerHTML = `<div class="empty-state">最近文档加载失败: ${error.message}</div>`;
});
