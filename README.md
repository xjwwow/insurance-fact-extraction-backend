# Insurance Fact Extraction Backend

面向“保险年报/半年报/季报/月报事实抽取、指标映射、人工校对”的 FastAPI 项目。

## 先看这里
- 如果你是在新电脑上用 Codex 接手这个项目，先读：
  - [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md)
- 这份文档会告诉你：
  - 项目目标
  - 之前做过哪些迭代
  - 当前页面和 API 到了什么状态
  - 哪些问题已经修过，哪些问题还没修完
  - 建议从哪里继续推进

## 项目历史摘要
- 阶段 1：FastAPI + SQLAlchemy + Alembic + PostgreSQL 基础脚手架
- 阶段 2：本地 PostgreSQL、迁移、健康检查与运行环境打通
- 阶段 3：PDF 解析主流程打通，形成 `document -> table -> fact -> validation`
- 阶段 4：接入 `pdfplumber + OCR fallback`
- 阶段 5：增加上传页、viewer、指标库、校对台等前端工作台
- 阶段 6：重构指标库为“正式指标 + 候选指标 + 证据链”
- 阶段 7：增加表格 QA、指标值页、指标体系层级与公式依赖建模
- 当前建议继续优化：
  - 多层列头重复拼接
  - `Word-layout numeric table` 泛标题压缩
  - 合并单元格/换行续行解析准确率

## 当前技术栈
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Celery
- pdfplumber
- pytesseract + pypdfium2
- 原生静态前端（HTML/CSS/JS）

## 当前主要页面
- `/`
  - 上传页
- `/documents/{document_id}/viewer`
  - 年报查看页
- `/documents/{document_id}/qa`
  - 表格质检页
- `/metrics/library`
  - 指标库页
- `/metrics/values`
  - 指标值台账页
- `/metrics/review`
  - 候选指标审核台
- `/qa/workbench`
  - 事实校对台

## 当前主要能力
- 文档上传与入库
- PDF 文本解析、表格解析、OCR fallback
- 表格 canonical 化
- fact 抽取、单位归一、期间识别
- 正式指标库、候选指标、别名、证据链
- 指标值查询与状态分层
- 表格 QA 列表与 Excel 导出
- 人工审核：approve / correct / remap

## 关键 API
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/{document_id}/parse`
- `GET /api/v1/documents/parse-tasks/{task_id}`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/tables`
- `GET /api/v1/documents/{document_id}/outline`
- `GET /api/v1/documents/{document_id}/qa`
- `GET /api/v1/documents/{document_id}/qa/export`
- `GET /api/v1/facts`
- `GET /api/v1/metrics`
- `GET /api/v1/metrics/tree`
- `GET /api/v1/metrics/values`
- `GET /api/v1/metrics/{canonical_metric_id}`
- `GET /api/v1/metrics/review/queue`
- `POST /api/v1/metrics/import/preview`
- `POST /api/v1/metrics/import`
- `POST /api/v1/review/facts/{fact_id}/approve`
- `POST /api/v1/review/facts/{fact_id}/correct`
- `POST /api/v1/review/facts/{fact_id}/remap-metric`

## 本地运行
```powershell
cd D:\Codex\insurance-fact-extraction-backend
```

### 1. 安装依赖
```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Copy-Item .env.example .env
```

### 2. 启动 PostgreSQL
```powershell
.\.local\pgsql\bin\pg_ctl.exe -D .\.local\pgdata start
```

### 3. 执行迁移
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. 启动 API
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. 健康检查
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

## OCR 配置
`.env` 中常用项：

```env
OCR_ENABLED=true
OCR_LANGUAGE=chi_sim+eng
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
TESSDATA_PREFIX=D:/Codex/insurance-fact-extraction-backend/data/tessdata
```

## 当前建议测试文档
- 标准公司编码版本平安 2024：
  - `doc_20260310150636_c7be2c64d422`
- 历史旧 viewer 文档：
  - `doc_20260308060911_514737d67ead`

## 当前 QA 导出文件
- `data/exports/table_qa/doc_20260310150636_c7be2c64d422_table_qa.xlsx`
- `data/exports/table_qa/doc_20260308060911_514737d67ead_table_qa.xlsx`

## GitHub 仓库
- [https://github.com/xjwwow/insurance-fact-extraction-backend](https://github.com/xjwwow/insurance-fact-extraction-backend)

## 说明
- 运行产物默认不提交：
  - `data/uploads/`
  - `data/previews/`
  - `data/exports/`
  - `data/tessdata/`
  - `.env`
  - `.venv`
  - `.local`
- 如果后续要继续开发，优先参考 [docs/PROJECT_HISTORY.md](D:/Codex/insurance-fact-extraction-backend/docs/PROJECT_HISTORY.md)。
- 如果后续要继续开发，优先参考 [`docs/PROJECT_HISTORY.md`](docs/PROJECT_HISTORY.md)。
