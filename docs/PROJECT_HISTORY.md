# Project History And Handover

这份文档用于新电脑、新会话、或新的 Codex 实例快速接手项目。

目标不是替代 README，而是记录：
- 项目目标
- 迭代历史
- 当前页面/API/数据模型状态
- 已知问题
- 建议下一步

## 1. 项目目标

项目目标是建设一个“保险公司年报事实抽取与指标校对平台”，核心流程是：

1. 用户上传 PDF 年报/半年报/季报/月报
2. 系统自动解析 PDF 和表格
3. 系统从表格中抽取结构化 fact
4. 系统把 fact 映射到正式指标库或候选指标
5. 系统给出自动可用 / 待审核 / 人工确认等状态
6. 用户在工作台中对照 PDF、表格、指标值进行人工确认

当前系统的核心概念已经基本稳定：

- `document`
  - 一份上传的报告
- `canonical_table`
  - 从 PDF 页面中提取出来的结构化表格
- `fact`
  - 从表格中抽取出的单条结构化事实，包含值、单位、期间、来源页码、来源表格、来源单元格
- `metric_definition`
  - 正式指标定义
- `metric_alias`
  - 指标别名
- `metric_evidence`
  - 指标与 fact 之间的证据链
- `candidate metric`
  - 未命中正式指标库时形成的候选指标

## 2. 已完成的迭代历程

### 阶段 A：后端脚手架

最早建立的是基础 FastAPI 工程，包含：
- FastAPI 入口
- SQLAlchemy / Alembic / PostgreSQL
- 健康检查
- `.env` 配置

这一阶段的目标是先把项目跑起来，验证本地数据库、迁移、服务可启动。

### 阶段 B：本地 PostgreSQL 与 Alembic

后续在项目目录内放置了本地 PostgreSQL 运行目录，完成：
- 本地数据库初始化
- Alembic 迁移跑通
- 健康检查联通数据库

这一阶段的价值是：不依赖公司外部数据库，也可以在本机快速复现实验环境。

### 阶段 C：文档解析主流程打通

后来补了完整的解析主链路：

`document -> page_layout -> canonical_table -> fact -> validation`

初期主要是规则化 MVP，目的是先让链路完整可跑，不追求高精度。

### 阶段 D：真实 PDF 解析器接入

接入了：
- `pdfplumber`
- `pypdfium2`
- `pytesseract`

形成了：
- 原生 PDF 解析优先
- OCR fallback

这一步使系统能处理：
- 普通文本型 PDF
- 一部分扫描型 PDF

### 阶段 E：前端工作台初版

增加了：
- 上传页
- 三栏 viewer（左：导航，中：表格+facts，右：PDF）

这一阶段也暴露了很多问题：
- 导航状态丢失
- PDF 高亮偏移
- 表格标题泛化
- 多层表头处理不足

### 阶段 F：指标库与候选指标机制

最初做过“扫描后自动学习 learned metric”的方案，后来发现不稳定，造成大量：
- `metric_17`
- `metric_24`
- 各种低质量名称进入库

后来重构成：
- 正式指标库
- 候选指标队列
- 人工 merge / dismiss

现在正式指标与候选指标是分层的，低质量扫描结果不会直接进入正式库。

### 阶段 G：指标值页、表格 QA、指标体系建模

后续完成了：
- 表格 QA 列表与 Excel 导出
- 指标值台账页
- 指标层级、排序、父子关系、公式依赖模型

这一步是为了让项目从“解析 demo”转向“可运营的数据平台”。

## 3. 当前页面与职责

### 上传页 `/`
- 上传报告
- 选择保险公司
- 选择业务条线
- 选择报告类型
- 发起解析

### 年报查看页 `/documents/{document_id}/viewer`
- 左侧：目录与表格导航
- 中间：结构化表格与 fact
- 右侧：PDF 页面对照

当前已经支持：
- 拖拽调整三栏宽度
- 导航展开状态持久化
- 事实点击后 PDF 高亮
- 放大模式下更精确的高亮

### 表格质检页 `/documents/{document_id}/qa`
- 一张表一行展示 QA 结果
- 自动预警
- 人工备注
- Excel 导出

### 指标库页 `/metrics/library`
- 左侧：指标体系导航（大类 / 小类）
- 右侧：查询结果、定义详情、公式依赖、证据链
- 支持下载核心指标导入模板，方便按系统要求整理导入文件

### 指标值页 `/metrics/values`
- 查看某指标在什么公司、什么报告、什么期间下的值
- 按状态区分：
  - 自动可用
  - 待审核
  - 人工确认可用
  - 待复核
  - 已驳回

### 候选指标审核台 `/metrics/review`
- 审核候选指标
- merge 到正式指标
- dismiss 噪音指标

### 事实校对台 `/qa/workbench`
- approve
- correct
- remap metric

## 4. 当前后端能力状态

### 已有
- 文档上传与入库
- 异步 parse 任务
- PDF / OCR fallback
- 表格 canonical 化
- fact 抽取
- 单位归一
- 期间类型识别
- 指标值查询
- 表格 QA
- 指标体系父子层级 / 排序 / 公式依赖

### 已经固定下来的状态语义

fact 现在有三层状态相关语义：

1. `validation_status`
- `PASS`
- `REVIEW`
- `FAIL`

2. `review_status`
- `PENDING`
- `APPROVED`
- `CORRECTED`
- `REMAPPED`
- `REJECTED`

3. 面向页面展示的 `availability_status`
- `AUTO_READY`
- `PENDING_REVIEW`
- `MANUAL_CONFIRMED`
- `NEEDS_RECHECK`
- `REJECTED`

页面应该优先使用 `availability_status / availability_label`，不要直接把 `validation_status` 暴露给业务用户。

## 5. 当前推荐测试文档

建议优先用这份新文档继续测试：

- `doc_20260310150636_c7be2c64d422`
  - 公司：`pingan`
  - 年份：`2024`
  - 状态：重跑过、适合继续做回归测试

旧 viewer 文档：

- `doc_20260308060911_514737d67ead`
  - 是历史测试过程中长期使用的文档
  - 目前也重新跑过，但不建议继续作为唯一基准

## 6. 当前已知问题

这些问题是当前还没完全解决的，接手时应优先关注：

### 6.1 多层列头重复拼接

现象：
- 类似 `2023年 12月31日 2023年`
- 或 `较年初变动 (%)` 的重复/不优雅拼接

说明：
- 现在已经保留了分层 `col_path`
- 但“展示用合并标签”的归一策略还不够干净

这是后续重点优化项之一。

### 6.2 `Word-layout numeric table` 泛标题仍然存在

虽然已经下降，但还没有被完全压掉。

现象：
- 某些表仍然出现：
  - `Word-layout numeric table`
  - `Auto-detected numeric table`
  - `OCR-detected numeric table`

这些在 QA 页中已经会被标红或标记为问题，但还需要继续压缩。

### 6.3 多层表头 / 合并单元格 / 续行处理仍然不稳定

当前最主要的解析问题仍集中在：
- 多层列头展开
- 合并单元格继承
- 行标题换行错位
- 表格标题捕获不完整

表格 QA Excel 的意义就是帮助系统性标出这些问题。

### 6.4 PowerShell 中文显示乱码

如果在 PowerShell 中直接看 JSON，中文可能会出现 mojibake。

这不是数据库错误，通常只是终端编码问题。
浏览器页面中的中文显示更可信。

## 7. 这次最近一次大更新做了什么

最近一次较大的集中改造包括：

- viewer：
  - 三栏拖拽宽度
  - 展开状态持久化
  - 目录按页码排序
  - 高亮层跟随图像尺寸
  - 来源页回跳

- 指标库：
  - 左树右主工作区
  - 指标体系树
  - 公式依赖展示
  - 导入模板下载接口与页面入口

- 指标值：
  - 新增 `/metrics/values`
  - 明确可用状态

- 表格 QA：
  - 新增 `/documents/{document_id}/qa`
  - 新增 Excel 导出
  - 支持人工保存备注

- 数据模型：
  - `metric_definitions` 增加：
    - `parent_canonical_metric_id`
    - `hierarchy_depth`
    - `sort_order`
  - 新增 `metric_dependencies`
  - 新增 `table_qa_reviews`

## 8. 当前可用的 QA 导出文件

当前项目里已经生成过两份表格 QA Excel：

- `data/exports/table_qa/doc_20260310150636_c7be2c64d422_table_qa.xlsx`
- `data/exports/table_qa/doc_20260308060911_514737d67ead_table_qa.xlsx`

这两份文件是继续优化解析器时的重要基线。

## 9. 在新电脑 / 新 Codex 会话里如何继续

建议接手流程：

1. 先读 `README.md`
2. 再读本文件 `docs/PROJECT_HISTORY.md`
3. 启动本地数据库和 API
4. 打开：
   - 上传页
   - 新平安 viewer
   - 表格质检页
   - 指标库
   - 指标值页
5. 优先检查：
   - 多层列头重复拼接
   - 泛标题
   - 高亮准确性
   - 指标值状态划分

如果是让 Codex 接着做，建议直接给它这样的任务描述：

> 请先阅读 README 和 docs/PROJECT_HISTORY.md，理解当前项目状态。然后优先继续优化多层列头重复拼接和 `Word-layout numeric table` 泛标题问题，并对 `doc_20260310150636_c7be2c64d422` 做回归测试。

## 10. Git 与仓库说明

当前 GitHub 仓库：

- [https://github.com/xjwwow/insurance-fact-extraction-backend](https://github.com/xjwwow/insurance-fact-extraction-backend)

当前仓库已经配置忽略：
- `data/uploads/`
- `data/previews/`
- `data/exports/`
- `data/tessdata/`
- `.env`
- `.venv`
- `.local`

如果后续要公开展示仓库，建议继续清理：
- 不必要的 sample PDF
- 临时测试 CSV
- 过时的实验性脚本或文档

## 11. 推荐下一步

如果继续推进，推荐优先级如下：

1. 优化多层列头展示标签，消除重复拼接
2. 压缩 `Word-layout numeric table` 泛标题
3. 提升多层表头与合并单元格解析
4. 用 QA Excel 逐页回归修表格解析器
5. 扩充正式指标库覆盖率，减少 candidate 数量

这几项做完后，系统的“可测性”和“可用性”会明显提升。

## 12. 2026-03-13 补充更新

本次补充更新主要是为了让“核心指标库导入”更容易被业务用户正确使用：

- 新增模板下载接口：
  - `GET /api/v1/metrics/import/template`
- 指标库页面新增“下载模板”按钮
- 模板输出为 `metric_import_template.xlsx`
- 模板包含两个工作表：
  - `metrics_template`
  - `instructions`

这次更新的目的不是改变导入逻辑，而是降低导入格式出错率，让用户先按模板整理字段后再走 preview / import。
