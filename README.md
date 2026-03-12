# Insurance Fact Extraction Backend

面向“保险集团年报事实抽取与校核平台”的 FastAPI 后端骨架（MVP）。

## 技术栈
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Celery（任务队列）
- pdfplumber（PDF 原生解析）
- pytesseract + pypdfium2（OCR fallback）

## 当前能力
- 内置前端工作台：
  - `/` 上传页面（保险公司、所属大类、上传并解析）
  - `/documents/{document_id}/viewer` 三栏对照页（表格列表、数据展示、PDF 对照）
- 文档上传与入库
- 文档解析主流程（parse -> canonicalize -> extract -> validate -> persist）
- 指标库构建：
  - 内置保险年报通用标准指标种子库
  - 从已抽取 fact 自动沉淀 document-specific alias
  - `metric_evidences` 记录指标与事实/页码/表格的证据链
  - learned metric 高置信度筛选
  - 历史模板支持：同公司同表格模板自动复用历史映射
  - 指标审核台：人工 merge / dismiss learned metric
- Fact 抽取增强：
  - 行列头语义解析（metric/period/scope）
  - 期间类型识别（年度/季度/半年度/月度）
  - 单位归一与倍率换算（元/千元/万元/百万元/亿元/%/股）
  - 币种识别（CNY/USD/HKD）
- 审核队列与审核动作（approve/correct/remap）
- 解析异步化：`/parse` 提交 Celery 任务，状态接口查询结果

## API
- `POST /api/v1/documents/upload`
- `GET /api/v1/documents`
- `POST /api/v1/documents/{document_id}/parse`（异步提交）
- `GET /api/v1/documents/parse-tasks/{task_id}`（任务状态）
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/file`
- `GET /api/v1/documents/{document_id}/tables`
- `GET /api/v1/documents/{document_id}/tables/{table_id}`
- `GET /api/v1/facts`
- `GET /api/v1/metrics`
- `GET /api/v1/metrics/{canonical_metric_id}`
- `POST /api/v1/metrics/bootstrap`
- `POST /api/v1/metrics/build-library?document_id=...`
- `GET /api/v1/metrics/review/queue`
- `POST /api/v1/metrics/review/{source_canonical_metric_id}/merge`
- `POST /api/v1/metrics/review/{source_canonical_metric_id}/dismiss`
- `GET /api/v1/review/queue`
- `POST /api/v1/review/facts/{fact_id}/approve`
- `POST /api/v1/review/facts/{fact_id}/correct`
- `POST /api/v1/review/facts/{fact_id}/remap-metric`

## 环境准备
```powershell
cd D:\Codex\insurance-fact-extraction-backend
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
```

## OCR 配置
- `TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe`
- `TESSDATA_PREFIX=D:/Codex/insurance-fact-extraction-backend/data/tessdata`
- `OCR_LANGUAGE=chi_sim+eng`

## Celery 配置
- 开发默认：`.env` 中 `CELERY_TASK_ALWAYS_EAGER=true`（便于本机调试）
- 真实异步：设为 `false`，并启动 Redis + Celery Worker

Worker 启动命令：
```powershell
cd D:\Codex\insurance-fact-extraction-backend
$env:PYTHONPATH="D:\Codex\insurance-fact-extraction-backend"
.\.venv\Scripts\celery.exe -A app.worker.celery_app worker -l info
```

## 数据库迁移
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

## 启动 API
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 打开前端
- 上传页：`http://127.0.0.1:8000/`
- 对照页：`http://127.0.0.1:8000/documents/{document_id}/viewer`
- 指标审核台：`http://127.0.0.1:8000/metrics/review`

## 上传接口字段
- `company_id`
- `business_line`：`group` / `life` / `pnc`
- `report_year`
- `report_type`：默认 `annual_report`
- `file`

## 指标库验证
```powershell
# 初始化标准指标库
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/bootstrap" -Method Post

# 为某份年报构建指标库证据链
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/build-library?document_id={document_id}" -Method Post

# 查看指标定义、别名、证据链
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/{canonical_metric_id}"

# 查看 learned metric 审核队列
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/review/queue?company_id=pingan-ui-test"

# 并入标准指标
$body = @{ reviewer='admin'; target_canonical_metric_id='metric_operating_revenue' } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/metrics/review/{source_metric_id}/merge" -Method Post -Body $body -ContentType "application/json"
```

## 异步解析示例
1. 提交任务
```powershell
$resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/documents/{document_id}/parse" -Method Post
$resp
```

2. 查询任务状态
```powershell
Invoke-RestMethod -Uri ("http://127.0.0.1:8000/api/v1/documents/parse-tasks/" + $resp.task_id)
```

3. 查询事实
```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/facts?document_id={document_id}"
```
