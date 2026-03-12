
const apiRoot = "/api/v1";
const documentId = window.location.pathname.split("/")[2];
const initialQuery = new URLSearchParams(window.location.search);
const outlineStateKey = `viewer:outline:${documentId}`;
const layoutStateKey = `viewer:layout:${documentId}`;
const originMap = {
  "metrics-library": { href: "/metrics/library", label: "返回指标库" },
  "metrics-values": { href: "/metrics/values", label: "返回指标值页" },
  "qa-workbench": { href: "/qa/workbench", label: "返回校对台" },
  "document-qa": { href: `/documents/${documentId}/qa`, label: "返回表格质检" },
};

const viewerTitle = document.getElementById("viewer-title");
const viewerSubtitle = document.getElementById("viewer-subtitle");
const viewerBackLink = document.getElementById("viewer-back-link");
const viewerQaLink = document.getElementById("viewer-qa-link");
const viewerLayout = document.getElementById("viewer-layout");
const tableList = document.getElementById("table-list");
const tableSearch = document.getElementById("table-search");
const navCount = document.getElementById("nav-count");
const expandOutlineButton = document.getElementById("expand-outline");
const collapseOutlineButton = document.getElementById("collapse-outline");
const selectedTablePreview = document.getElementById("selected-table-preview");
const selectedTableMeta = document.getElementById("selected-table-meta");
const factsTableBody = document.getElementById("facts-table-body");
const factsMeta = document.getElementById("facts-meta");
const factBadge = document.getElementById("fact-badge");
const summaryCards = document.getElementById("summary-cards");
const openPdfLink = document.getElementById("open-pdf-link");
const pdfPageLabel = document.getElementById("pdf-page-label");
const previewStatus = document.getElementById("preview-status");
const pagePreviewImage = document.getElementById("page-preview-image");
const pagePreviewCanvas = document.getElementById("page-preview-canvas");
const pagePreviewOverlay = document.getElementById("page-preview-overlay");
const pagePreviewPdf = document.getElementById("page-preview-pdf");
const previewPrev = document.getElementById("preview-prev");
const previewNext = document.getElementById("preview-next");
const previewModeImage = document.getElementById("preview-mode-image");
const previewModePdf = document.getElementById("preview-mode-pdf");
const previewOpenModal = document.getElementById("preview-open-modal");
const previewModal = document.getElementById("preview-modal");
const modalPageLabel = document.getElementById("modal-page-label");
const modalStatus = document.getElementById("modal-status");
const modalPreviewImage = document.getElementById("modal-preview-image");
const modalPreviewCanvas = document.getElementById("modal-preview-canvas");
const modalPreviewOverlay = document.getElementById("modal-preview-overlay");
const modalZoomLayer = document.getElementById("modal-zoom-layer");
const modalZoomIn = document.getElementById("modal-zoom-in");
const modalZoomOut = document.getElementById("modal-zoom-out");
const modalReset = document.getElementById("modal-reset");
const modalPrev = document.getElementById("modal-prev");
const modalNext = document.getElementById("modal-next");
const modalClose = document.getElementById("modal-close");

let documentInfo = null;
let outline = [];
let tables = [];
let facts = [];
let tablesById = new Map();
let factsById = new Map();
let selectedTableId = initialQuery.get("table_id") || null;
let selectedFactId = initialQuery.get("fact_id") || null;
let currentPreviewPage = Number(initialQuery.get("page")) || 1;
let previewMode = "image";
let currentTable = null;
let currentHighlight = null;
let modalScale = 1;
let outlineState = loadOutlineState();
let layoutState = loadLayoutState();

async function apiFetch(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function normalizeText(value, fallback = "无内容") {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function loadOutlineState() {
  try {
    const raw = localStorage.getItem(outlineStateKey);
    if (!raw) return { openNodeIds: [], scrollTop: 0 };
    const parsed = JSON.parse(raw);
    return { openNodeIds: Array.isArray(parsed.openNodeIds) ? parsed.openNodeIds : [], scrollTop: Number(parsed.scrollTop) || 0 };
  } catch {
    return { openNodeIds: [], scrollTop: 0 };
  }
}

function saveOutlineState(partial = {}) {
  outlineState = { ...outlineState, ...partial };
  localStorage.setItem(outlineStateKey, JSON.stringify(outlineState));
}

function loadLayoutState() {
  try {
    const raw = localStorage.getItem(layoutStateKey);
    if (!raw) return { navWidth: 320, pdfWidth: 380 };
    const parsed = JSON.parse(raw);
    return { navWidth: Number(parsed.navWidth) || 320, pdfWidth: Number(parsed.pdfWidth) || 380 };
  } catch {
    return { navWidth: 320, pdfWidth: 380 };
  }
}

function saveLayoutState() {
  localStorage.setItem(layoutStateKey, JSON.stringify(layoutState));
}

function applyLayoutState() {
  viewerLayout.style.setProperty("--viewer-nav-width", `${layoutState.navWidth}px`);
  viewerLayout.style.setProperty("--viewer-pdf-width", `${layoutState.pdfWidth}px`);
}

function tableTitleFromRaw(raw, pageStart = null) {
  const direct = [raw?.title, raw?.table_title_raw, raw?.table_title_norm].find((item) => typeof item === "string" && item.trim());
  if (direct) return direct.trim();
  if (Number.isFinite(Number(pageStart))) return `第 ${Number(pageStart)} 页表格`;
  return "未命名表格";
}

function normalizeTable(raw) {
  const tableJson = raw && typeof raw.table_json === "object" && raw.table_json ? raw.table_json : {};
  const cells = Array.isArray(tableJson.cells) ? tableJson.cells : [];
  const parseTrace = raw && typeof raw.parse_trace_json === "object" && raw.parse_trace_json ? raw.parse_trace_json : {};
  const pageStart = Number(raw?.page_start) || 1;
  const pageEnd = Number(raw?.page_end) || pageStart;
  return {
    ...raw,
    table_id: normalizeText(raw?.table_id, ""),
    page_start: pageStart,
    page_end: pageEnd,
    title: tableTitleFromRaw(raw, pageStart),
    table_json: { ...tableJson, cells, col_headers: Array.isArray(tableJson.col_headers) ? tableJson.col_headers : [] },
    parse_trace_json: parseTrace,
    parse_engine: typeof raw?.parse_engine === "string" ? raw.parse_engine : "unknown",
    cell_count: cells.length,
  };
}

function normalizeFact(raw) {
  const rowPath = Array.isArray(raw?.source_row_path?.path) ? raw.source_row_path.path : [];
  const colPath = Array.isArray(raw?.source_col_path?.path) ? raw.source_col_path.path : [];
  const bbox = Array.isArray(raw?.source_cell_bbox?.bbox) ? raw.source_cell_bbox.bbox : [];
  return {
    ...raw,
    source_page_no: Number(raw?.source_page_no) || 1,
    source_table_id: typeof raw?.source_table_id === "string" ? raw.source_table_id : null,
    source_row_path: rowPath,
    source_col_path: colPath,
    source_cell_bbox: bbox,
    metric_display: normalizeText(raw?.metric_name_std || raw?.metric_alias_raw, "无内容"),
    period_label: normalizeText(raw?.period_label || raw?.dimensions_json?.period_label || colPath.join(" / "), "-"),
    availability_label: normalizeText(raw?.availability_label, "待审核"),
  };
}

function normalizeOutlineNode(raw) {
  const children = Array.isArray(raw?.children) ? raw.children.map(normalizeOutlineNode).filter(Boolean) : [];
  const tableItems = Array.isArray(raw?.tables) ? raw.tables.map((table) => normalizeTable(table)).filter((table) => table.table_id) : [];
  return {
    node_id: normalizeText(raw?.node_id, `node_${Math.random().toString(36).slice(2, 10)}`),
    kind: typeof raw?.kind === "string" ? raw.kind : "section",
    title: normalizeText(raw?.title, "无内容"),
    page_start: raw?.page_start != null ? Number(raw.page_start) : null,
    page_end: raw?.page_end != null ? Number(raw.page_end) : null,
    level: Number(raw?.level) || 1,
    children,
    tables: tableItems,
  };
}

function buildFallbackOutline(tableItems) {
  if (!tableItems.length) return [];
  const groups = new Map();
  for (const table of tableItems) {
    const pageKey = table.page_start;
    if (!groups.has(pageKey)) {
      groups.set(pageKey, { node_id: `page_${pageKey}`, kind: "item", title: `第 ${pageKey} 页`, page_start: pageKey, page_end: pageKey, level: 2, children: [], tables: [] });
    }
    groups.get(pageKey).tables.push(table);
  }
  return [{ node_id: "fallback_all_tables", kind: "section", title: "按页查看", page_start: tableItems[0].page_start, page_end: tableItems[tableItems.length - 1].page_end, level: 1, children: [...groups.values()].sort((a, b) => a.page_start - b.page_start), tables: [] }];
}

function flattenTables(nodes) {
  const result = [];
  for (const node of nodes) {
    result.push(...(node.tables || []));
    result.push(...flattenTables(node.children || []));
  }
  return result;
}

function countOutlineTables(nodes) {
  return flattenTables(nodes).length;
}

function hydrateTables(tableItems) {
  tables = tableItems.map(normalizeTable);
  tablesById = new Map(tables.map((table) => [table.table_id, table]));
}

function hydrateFacts(factItems) {
  facts = factItems.map(normalizeFact);
  factsById = new Map(facts.map((fact) => [fact.fact_id, fact]));
}

function pathKey(path) {
  return Array.isArray(path) ? path.join(" / ") : "";
}

function updateQuery(params) {
  const query = new URLSearchParams(window.location.search);
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") query.delete(key);
    else query.set(key, String(value));
  });
  const next = `${window.location.pathname}${query.toString() ? `?${query.toString()}` : ""}`;
  window.history.replaceState({}, "", next);
}

function renderSummary(document, tableCount, factCount) {
  const cards = [
    ["保险公司", document.company_label || document.company_id],
    ["所属大类", document.business_line_label || document.business_line || "-"],
    ["报告类型", document.report_type_label || document.report_type],
    ["报告年份", document.report_year],
    ["表格数量", tableCount],
    ["事实数量", factCount],
  ];
  summaryCards.innerHTML = cards.map(([label, value]) => `<article class="summary-card"><div class="metric-label">${label}</div><strong>${value}</strong></article>`).join("");
}
function buildGridRows(tableJson) {
  const cells = Array.isArray(tableJson.cells) ? tableJson.cells : [];
  const colHeaders = Array.isArray(tableJson.col_headers) && tableJson.col_headers.length
    ? tableJson.col_headers.map((item) => normalizeText(item, "无内容"))
    : [...new Set(cells.map((cell) => pathKey(cell.col_path || ["value"])))].filter(Boolean);

  const rowsByKey = new Map();
  for (const cell of cells) {
    const rowKey = pathKey(cell.row_path || ["row"]);
    const colKey = pathKey(cell.col_path || ["value"]);
    if (!rowsByKey.has(rowKey)) rowsByKey.set(rowKey, { rowLabel: rowKey || "无内容", values: {} });
    rowsByKey.get(rowKey).values[colKey] = cell.value_raw ?? "";
  }
  return { colHeaders, rows: [...rowsByKey.values()] };
}

function renderTablePreview(table) {
  currentTable = table;
  currentHighlight = null;
  const tableJson = table.table_json || {};
  const { colHeaders, rows } = buildGridRows(tableJson);
  const sourceLabel = table.parse_trace_json?.source_label || table.parse_trace_json?.fallback_reason || "结构化解析";
  const headerLevels = Number(table.parse_trace_json?.header_levels || Math.max(...(tableJson.cells || []).map((cell) => (cell.col_path || []).length), 1));
  selectedTableMeta.textContent = `${table.title} / 第 ${table.page_start} 页 / ${table.cell_count} 个单元格 / ${table.parse_engine || "unknown"}`;

  const metaGrid = `
    <div class="detail-grid two-column top-gap">
      <div><div class="metric-label">表格名称</div><strong>${table.title}</strong></div>
      <div><div class="metric-label">页码</div><strong>P.${table.page_start}${table.page_end !== table.page_start ? ` - P.${table.page_end}` : ""}</strong></div>
      <div><div class="metric-label">解析引擎</div><strong>${table.parse_engine || "unknown"}</strong></div>
      <div><div class="metric-label">识别单元格</div><strong>${table.cell_count}</strong></div>
      <div><div class="metric-label">表头层级</div><strong>${headerLevels}</strong></div>
      <div><div class="metric-label">来源说明</div><strong>${normalizeText(sourceLabel, "结构化解析")}</strong></div>
    </div>
  `;

  if (!rows.length) {
    selectedTablePreview.className = "table-preview";
    selectedTablePreview.innerHTML = `${metaGrid}<div class="empty-state top-gap">当前表格暂无结构化内容。</div>`;
    syncPreviewHighlight();
    return;
  }

  selectedTablePreview.className = "table-preview";
  selectedTablePreview.innerHTML = `
    ${metaGrid}
    <div class="table-scroll top-gap">
      <table class="preview-grid">
        <thead><tr><th>指标</th>${colHeaders.map((header) => `<th>${normalizeText(header, "无内容")}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows.map((row) => `<tr><td>${normalizeText(row.rowLabel, "无内容")}</td>${colHeaders.map((header) => `<td>${row.values[header] || ""}</td>`).join("")}</tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
  syncPreviewHighlight();
}

function renderFacts() {
  const currentFacts = facts.slice(0, 400);
  factBadge.textContent = `${currentFacts.length} 条事实`;
  factsMeta.textContent = selectedTableId ? "已按当前表格加载" : "请选择表格后加载事实";

  if (!currentFacts.length) {
    factsTableBody.innerHTML = `<tr><td colspan="8"><div class="empty-state">当前筛选结果没有事实数据。</div></td></tr>`;
    return;
  }

  factsTableBody.innerHTML = currentFacts.map((fact) => `
    <tr class="row-clickable ${selectedFactId === fact.fact_id ? "active-row" : ""}" data-fact-id="${fact.fact_id}">
      <td>${fact.source_page_no || "-"}</td>
      <td>${fact.metric_display}</td>
      <td>${fact.period_label || "-"}</td>
      <td>${fact.value_raw || "-"}</td>
      <td>${fact.value_numeric || "-"}</td>
      <td>${fact.unit_std || fact.unit_raw || "-"}</td>
      <td>${fact.availability_label}</td>
      <td>${fact.review_status}</td>
    </tr>
  `).join("");
}

function tableMatches(table, keyword) {
  return `${table.title} ${table.page_start}`.toLowerCase().includes(keyword);
}

function nodeMatches(node, keyword) {
  const values = [node.title, node.page_start].filter(Boolean).join(" ").toLowerCase();
  if (values.includes(keyword)) return true;
  if ((node.tables || []).some((table) => tableMatches(table, keyword))) return true;
  return (node.children || []).some((child) => nodeMatches(child, keyword));
}

function nodeStats(node) {
  const childSections = node.children?.length || 0;
  const directTables = node.tables?.length || 0;
  const nestedTables = flattenTables(node.children || []).length;
  return { childSections, tableCount: directTables + nestedTables };
}

function filterOutline(nodes, keyword) {
  return nodes.flatMap((node) => {
    const filteredChildren = filterOutline(node.children || [], keyword);
    const filteredTables = (node.tables || []).filter((table) => tableMatches(table, keyword));
    const matchedSelf = nodeMatches(node, keyword);
    if (!matchedSelf && !filteredChildren.length && !filteredTables.length) return [];
    return [{ ...node, children: filteredChildren, tables: filteredTables }];
  });
}

function nodeContainsSelectedTable(node, tableId) {
  if ((node.tables || []).some((table) => table.table_id === tableId)) return true;
  return (node.children || []).some((child) => nodeContainsSelectedTable(child, tableId));
}

function isNodeOpen(node) {
  return outlineState.openNodeIds.includes(node.node_id) || (!!selectedTableId && nodeContainsSelectedTable(node, selectedTableId));
}

function renderOutlineNodes(nodes, level = 1) {
  return nodes.map((node) => {
    const hasChildren = (node.children?.length || 0) > 0 || (node.tables?.length || 0) > 0;
    if (!hasChildren) return "";
    const stats = nodeStats(node);
    const pageText = node.page_start ? `<span class="outline-page">P.${node.page_start}</span>` : "";
    const statText = `<span class="outline-stat">${stats.childSections} 节 / ${stats.tableCount} 表</span>`;
    const childMarkup = node.children?.length ? renderOutlineNodes(node.children, level + 1) : "";
    const tableMarkup = (node.tables || []).map((table) => `
      <button class="outline-table ${table.table_id === selectedTableId ? "active" : ""}" type="button" data-table-id="${table.table_id}" data-page="${table.page_start}">
        <span class="outline-table-title">${normalizeText(table.title, "未命名表格")}</span>
        <span class="outline-page">P.${table.page_start}</span>
      </button>
    `).join("");
    return `
      <details class="outline-node level-${level}" data-node-id="${node.node_id}" ${isNodeOpen(node) ? "open" : ""}>
        <summary><span class="outline-summary-main">${normalizeText(node.title, "无内容")}</span><span class="outline-summary-meta">${statText}${pageText}</span></summary>
        <div class="outline-children">${childMarkup}${tableMarkup}</div>
      </details>
    `;
  }).join("");
}

function renderTableList(options = {}) {
  const preserveScroll = options.preserveScroll !== false;
  const previousScroll = preserveScroll ? tableList.scrollTop : 0;
  const keyword = tableSearch.value.trim().toLowerCase();
  const filteredOutline = keyword ? filterOutline(outline, keyword) : outline;
  const tableCount = countOutlineTables(filteredOutline);
  navCount.textContent = `${tableCount} 张表`;

  if (!tables.length) {
    tableList.innerHTML = '<div class="empty-state">当前文档未识别到可展示表格。</div>';
    return;
  }
  if (!filteredOutline.length || !tableCount) {
    tableList.innerHTML = '<div class="empty-state">没有匹配的章节或表格。</div>';
    return;
  }

  tableList.innerHTML = renderOutlineNodes(filteredOutline);
  if (preserveScroll) tableList.scrollTop = previousScroll || outlineState.scrollTop || 0;
}

function persistOutlineOpenState() {
  const openNodeIds = [...tableList.querySelectorAll("details[data-node-id]")].filter((node) => node.open).map((node) => node.dataset.nodeId);
  saveOutlineState({ openNodeIds, scrollTop: tableList.scrollTop });
}
function setPreviewMode(mode) {
  previewMode = mode;
  previewModeImage.classList.toggle("active", mode === "image");
  previewModePdf.classList.toggle("active", mode === "pdf");
  pagePreviewCanvas.classList.toggle("hidden", mode !== "image");
  pagePreviewPdf.classList.toggle("hidden", mode !== "pdf");
  setPreviewPage(currentPreviewPage, { preserveQuery: true });
}

function syncCanvasSize(canvas, image) {
  if (!image || !canvas || image.clientWidth <= 0 || image.clientHeight <= 0) return;
  canvas.style.width = `${image.clientWidth}px`;
  canvas.style.height = `${image.clientHeight}px`;
}

function renderOverlay(container, boxes = [], pageWidth = 0, pageHeight = 0) {
  if (!pageWidth || !pageHeight) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = boxes.map((item) => {
    const [x0, y0, x1, y1] = item.bbox;
    const left = (x0 / pageWidth) * 100;
    const top = (y0 / pageHeight) * 100;
    const width = ((x1 - x0) / pageWidth) * 100;
    const height = ((y1 - y0) / pageHeight) * 100;
    return `<div class="page-highlight ${item.kind}" style="left:${left}%;top:${top}%;width:${width}%;height:${height}%"></div>`;
  }).join("");
}

function highlightFromFact(rowKey, colKey, bbox) {
  if (!currentTable?.table_json?.cells) return null;
  const cells = currentTable.table_json.cells;
  const rowBoxes = cells.filter((cell) => pathKey(cell.row_path) === rowKey).map((cell) => ({ bbox: cell.bbox, kind: "row" }));
  const colBoxes = cells.filter((cell) => pathKey(cell.col_path) === colKey).map((cell) => ({ bbox: cell.bbox, kind: "col" }));
  const result = [...rowBoxes, ...colBoxes].filter((item) => Array.isArray(item.bbox) && item.bbox.length === 4);
  if (bbox.length === 4) result.push({ bbox, kind: "cell" });
  return result.length ? result : null;
}

function syncPreviewHighlight() {
  syncCanvasSize(pagePreviewCanvas, pagePreviewImage);
  syncCanvasSize(modalPreviewCanvas, modalPreviewImage);
  const pageWidth = Number(currentTable?.parse_trace_json?.page_width || 0);
  const pageHeight = Number(currentTable?.parse_trace_json?.page_height || 0);
  if (!currentTable || currentPreviewPage < currentTable.page_start || currentPreviewPage > currentTable.page_end) {
    pagePreviewOverlay.innerHTML = "";
    modalPreviewOverlay.innerHTML = "";
    return;
  }

  if (currentHighlight) {
    const boxes = Array.isArray(currentHighlight) ? currentHighlight : [currentHighlight];
    renderOverlay(pagePreviewOverlay, boxes, pageWidth, pageHeight);
    renderOverlay(modalPreviewOverlay, boxes, pageWidth, pageHeight);
    return;
  }

  const bbox = currentTable.parse_trace_json?.bbox;
  if (Array.isArray(bbox) && bbox.length === 4) {
    renderOverlay(pagePreviewOverlay, [{ bbox, kind: "table" }], pageWidth, pageHeight);
    renderOverlay(modalPreviewOverlay, [{ bbox, kind: "table" }], pageWidth, pageHeight);
  } else {
    pagePreviewOverlay.innerHTML = "";
    modalPreviewOverlay.innerHTML = "";
  }
}

function setPreviewPage(pageNumber = 1, options = {}) {
  currentPreviewPage = Math.max(1, Number(pageNumber) || 1);
  pdfPageLabel.textContent = `P.${currentPreviewPage}`;
  modalPageLabel.textContent = `P.${currentPreviewPage}`;
  const imageUrl = `${apiRoot}/documents/${documentId}/pages/${currentPreviewPage}/preview?t=${Date.now()}`;
  const pdfUrl = `${apiRoot}/documents/${documentId}/file#page=${currentPreviewPage}`;
  pagePreviewImage.src = imageUrl;
  modalPreviewImage.src = imageUrl;
  pagePreviewPdf.data = pdfUrl;
  openPdfLink.href = pdfUrl;
  if (options.preserveQuery !== false) updateQuery({ page: currentPreviewPage });
}

function setPreviewStatus(message) {
  previewStatus.textContent = message;
  modalStatus.textContent = message;
}

function setModalScale(scale) {
  modalScale = Math.max(1, Math.min(4, Number(scale) || 1));
  modalZoomLayer.style.transform = `scale(${modalScale})`;
}

function openModal() {
  previewModal.classList.remove("hidden");
  previewModal.setAttribute("aria-hidden", "false");
  syncPreviewHighlight();
}

function closeModal() {
  previewModal.classList.add("hidden");
  previewModal.setAttribute("aria-hidden", "true");
}

async function loadFactsForTable(tableId) {
  if (!tableId) {
    hydrateFacts([]);
    renderFacts();
    return;
  }
  factsMeta.textContent = "正在加载当前表格事实...";
  const factItems = await apiFetch(`${apiRoot}/facts?document_id=${documentId}&source_table_id=${tableId}&limit=2000`);
  hydrateFacts(factItems);
  renderFacts();
  if (documentInfo) renderSummary(documentInfo, tables.length, facts.length);
}

async function selectTable(tableId, page = null, options = {}) {
  if (!tableId) return;
  persistOutlineOpenState();
  selectedTableId = tableId;
  renderTableList({ preserveScroll: true });

  let table = tablesById.get(tableId);
  if (!table?.table_json || !Array.isArray(table.table_json.cells) || !table.table_json.cells.length) {
    table = normalizeTable(await apiFetch(`${apiRoot}/documents/${documentId}/tables/${tableId}`));
    tablesById.set(tableId, table);
  }

  currentTable = table;
  renderTablePreview(table);
  setPreviewPage(page || table.page_start || 1);
  updateQuery({ table_id: table.table_id, page: page || table.page_start || 1 });
  await loadFactsForTable(table.table_id);

  if (!options.skipFactSelection && selectedFactId) {
    const fact = factsById.get(selectedFactId);
    if (fact && fact.source_table_id === table.table_id) focusFact(fact);
  }
}

function focusFact(fact) {
  selectedFactId = fact.fact_id;
  const rowKey = pathKey(fact.source_row_path);
  const colKey = pathKey(fact.source_col_path);
  const bbox = fact.source_cell_bbox || [];
  currentHighlight = highlightFromFact(rowKey, colKey, bbox);
  if (currentHighlight) {
    setPreviewStatus("已定位并高亮对应单元格、整行与整列。点击右侧放大查看可细看。");
  } else if (currentTable?.parse_trace_json?.bbox) {
    currentHighlight = { bbox: currentTable.parse_trace_json.bbox, kind: "table" };
    setPreviewStatus("当前页仅支持表级高亮，已定位到对应表格区域。");
  } else {
    setPreviewStatus("该事实暂无可高亮区域。右侧仍会跳转到对应页。");
  }
  setPreviewPage(fact.source_page_no || currentPreviewPage);
  updateQuery({ fact_id: fact.fact_id, table_id: fact.source_table_id, page: fact.source_page_no || currentPreviewPage });
  renderFacts();
  requestAnimationFrame(() => {
    const activeRow = factsTableBody.querySelector(`tr[data-fact-id="${fact.fact_id}"]`);
    activeRow?.scrollIntoView({ block: "nearest" });
  });
}

async function selectFactById(factId) {
  let fact = factsById.get(factId);
  if (!fact && selectedTableId) {
    await loadFactsForTable(selectedTableId);
    fact = factsById.get(factId);
  }
  if (!fact) return;
  if (fact.source_table_id && fact.source_table_id !== selectedTableId) {
    await selectTable(fact.source_table_id, fact.source_page_no, { skipFactSelection: true });
  }
  focusFact(fact);
}

async function applyInitialSelection() {
  const requestedTableId = initialQuery.get("table_id");
  const requestedPage = Number(initialQuery.get("page")) || 1;
  const requestedFactId = initialQuery.get("fact_id");
  if (!tables.length) {
    renderFacts();
    setPreviewPage(requestedPage || 1);
    return;
  }

  let targetTable = requestedTableId ? tablesById.get(requestedTableId) || null : null;
  if (!targetTable && requestedPage) targetTable = tables.find((table) => table.page_start === requestedPage) || null;
  if (!targetTable) targetTable = tables[0];

  await selectTable(targetTable.table_id, requestedPage || targetTable.page_start, { skipFactSelection: true });
  if (requestedFactId) await selectFactById(requestedFactId);
}
function initOriginLink() {
  const origin = initialQuery.get("origin");
  const originConfig = origin ? originMap[origin] : null;
  if (!originConfig) {
    viewerBackLink.classList.add("hidden");
    return;
  }
  viewerBackLink.href = originConfig.href;
  viewerBackLink.textContent = originConfig.label;
  viewerBackLink.classList.remove("hidden");
}

function attachResizers() {
  const centerMin = 520;
  viewerLayout.querySelectorAll(".layout-resizer").forEach((resizer) => {
    resizer.addEventListener("pointerdown", (event) => {
      if (window.innerWidth <= 1200) return;
      event.preventDefault();
      const mode = resizer.dataset.resize;
      const rect = viewerLayout.getBoundingClientRect();
      const separatorTotal = 20;
      const startPdf = layoutState.pdfWidth;

      function onMove(moveEvent) {
        if (mode === "nav") {
          const maxNav = Math.max(280, rect.width - startPdf - centerMin - separatorTotal);
          layoutState.navWidth = Math.max(260, Math.min(520, Math.min(maxNav, moveEvent.clientX - rect.left)));
        } else {
          const maxPdf = Math.max(320, rect.width - layoutState.navWidth - centerMin - separatorTotal);
          layoutState.pdfWidth = Math.max(320, Math.min(560, Math.min(maxPdf, rect.right - moveEvent.clientX)));
        }
        applyLayoutState();
        syncPreviewHighlight();
      }

      function onUp() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        saveLayoutState();
      }

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    });
  });
}

async function bootstrap() {
  if (!documentId) throw new Error("Missing document id");
  applyLayoutState();
  initOriginLink();
  viewerQaLink.href = `/documents/${documentId}/qa`;

  const [document, outlineItems, tableItems] = await Promise.all([
    apiFetch(`${apiRoot}/documents/${documentId}`),
    apiFetch(`${apiRoot}/documents/${documentId}/outline`).catch(() => []),
    apiFetch(`${apiRoot}/documents/${documentId}/tables`).catch(() => []),
  ]);

  documentInfo = document;
  hydrateFacts([]);
  hydrateTables(tableItems);
  outline = Array.isArray(outlineItems) ? outlineItems.map(normalizeOutlineNode) : [];
  if (!countOutlineTables(outline)) outline = buildFallbackOutline(tables);

  viewerTitle.textContent = document.document_label || `${document.company_label || document.company_id} ${document.report_year}`;
  viewerSubtitle.textContent = `${document.business_line_label || document.business_line || "-"} / ${document.report_type_label || document.report_type} / ${document.parse_status}`;
  renderSummary(document, tables.length, "-");
  renderTableList({ preserveScroll: false });
  setPreviewStatus("点击事实行可定位并高亮对应单元格。若当前页无结构化框选，将提示表级高亮。");
  attachResizers();
  await applyInitialSelection();
}

tableSearch.addEventListener("input", () => renderTableList({ preserveScroll: false }));
tableList.addEventListener("scroll", () => saveOutlineState({ scrollTop: tableList.scrollTop }));
tableList.addEventListener("toggle", (event) => {
  if (event.target instanceof HTMLDetailsElement && event.target.dataset.nodeId) persistOutlineOpenState();
}, true);
tableList.addEventListener("click", (event) => {
  const tableButton = event.target.closest("button[data-table-id]");
  if (!tableButton) return;
  selectTable(tableButton.dataset.tableId, Number(tableButton.dataset.page)).catch((error) => {
    tableList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  });
});

factsTableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-fact-id]");
  if (!row) return;
  selectFactById(row.dataset.factId).catch((error) => setPreviewStatus(error.message));
});

previewPrev.addEventListener("click", () => setPreviewPage(Math.max(1, currentPreviewPage - 1)));
previewNext.addEventListener("click", () => {
  const maxPage = Math.max(1, Number(documentInfo?.total_pages || currentPreviewPage + 1));
  setPreviewPage(Math.min(maxPage, currentPreviewPage + 1));
});
previewModeImage.addEventListener("click", () => setPreviewMode("image"));
previewModePdf.addEventListener("click", () => setPreviewMode("pdf"));
expandOutlineButton.addEventListener("click", () => {
  const openNodeIds = [...tableList.querySelectorAll("details[data-node-id]")].map((node) => node.dataset.nodeId);
  saveOutlineState({ openNodeIds });
  renderTableList({ preserveScroll: true });
});
collapseOutlineButton.addEventListener("click", () => {
  const openNodeIds = [];
  for (const node of outline) {
    if (selectedTableId && nodeContainsSelectedTable(node, selectedTableId)) openNodeIds.push(node.node_id);
  }
  saveOutlineState({ openNodeIds });
  renderTableList({ preserveScroll: true });
});
previewOpenModal.addEventListener("click", openModal);
pagePreviewImage.addEventListener("click", openModal);
modalClose.addEventListener("click", closeModal);
previewModal.addEventListener("click", (event) => {
  if (event.target?.dataset?.closeModal === "true") closeModal();
});
modalZoomIn.addEventListener("click", () => setModalScale(modalScale + 0.25));
modalZoomOut.addEventListener("click", () => setModalScale(modalScale - 0.25));
modalReset.addEventListener("click", () => setModalScale(1));
modalPrev.addEventListener("click", () => setPreviewPage(Math.max(1, currentPreviewPage - 1)));
modalNext.addEventListener("click", () => {
  const maxPage = Math.max(1, Number(documentInfo?.total_pages || currentPreviewPage + 1));
  setPreviewPage(Math.min(maxPage, currentPreviewPage + 1));
});
pagePreviewImage.addEventListener("load", syncPreviewHighlight);
modalPreviewImage.addEventListener("load", syncPreviewHighlight);
window.addEventListener("resize", syncPreviewHighlight);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !previewModal.classList.contains("hidden")) closeModal();
});

bootstrap().catch((error) => {
  viewerSubtitle.textContent = error.message;
  tableList.innerHTML = `<div class="empty-state">${error.message}</div>`;
});
