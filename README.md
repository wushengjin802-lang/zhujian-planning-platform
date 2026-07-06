# 住建项目策划与工程咨询辅助编制平台

## v1.2 工作台功能继续完善（2026-07-06）

本版本在工作台边界补齐版基础上继续完善协同闭环，版本号升级为 `v1.2.0`。

新增能力：

- 工作项事件流：领取、转交、完成、取消、评论均写入 `workbench_events`；
- 审核任务协同：支持分配审核人、追加审核意见、会签、通过/退回留痕；
- 通知处理：支持单条已读、归档、批量已读；
- 任务治理：新增 `task_events` 阶段日志，任务提交、取消、重试均留痕；
- Celery 取消增强：后台任务取消时尝试执行 Celery revoke，并保留业务侧取消状态；
- 前端工作台：新增意见、取消、分配、会签、通知归档、任务阶段日志展开和审计/事件切换。

新增迁移：

```text
apps/api-py/alembic/versions/20260706_0005_workbench_v12_events.py
```

更新后的 Checklist 已随代码包放入：

```text
docs/00_project/住建平台_PDDv1.2第5章_功能完成度Checklist_v1.2_20260706.xlsx
```


第一阶段开发工程。当前目标是按 PDD 技术栈打通 MVP 主链路：

资料上传与解析 -> 事实确认 -> 报告编制 -> 质量审核 -> 成果输出与归档。

## 工程结构

```text
apps/web-vue    PDD 主线前端：Vue3 + Vite + TypeScript + Element Plus + Pinia + Vue Router
apps/api-py     PDD 主线后端：FastAPI + SQLAlchemy + Pydantic + Alembic
apps/worker     Celery 队列说明，任务实现位于 apps/api-py/app/worker
archive/react-express-prototype 早期 React + Express 原型归档，仅供参考
packages/shared 共享类型、演示数据和阶段常量
docs            项目、产品、架构、API、测试、部署文档
infra           数据库、部署和运维脚本
templates       报告、Excel、提示词和质量规则模板
samples         演示项目资料
```

## 本地启动

```bash
npm install
python -m pip install -r apps/api-py/requirements.txt
npm run api:migrate
npm run dev
```

默认地址：

- 前端：http://localhost:5173
- API：http://localhost:8787
- MinIO 控制台：http://localhost:9001

Redis 与 MinIO 可通过以下命令启动：

```bash
docker compose -f infra/docker/docker-compose.pdd.yml up -d
```

## 本次工作台增强

工作台已从静态指标页升级为后端数据聚合驱动的可操作页面：

- 支持“当前项目 / 全部项目”范围切换；
- 聚合项目进度、待办、待审核、严重问题、后台任务和成果数量；
- 展示资料解析、事实确认、章节审核、质量问题和成果生成进度；
- 根据现有业务状态动态生成待办事项和待审核队列；
- 汇总资料解析、质量检查、成果导出等异步任务状态；
- 展示风险提醒、快捷操作、近期审计活动和跨项目组合概览；
- 新增认证接口 `GET /api/dashboard?projectId=<项目ID>`。

工作台待办和通知当前由业务数据实时派生，尚未替代后续正式的 `work_item`、`notification` 和 `review_task` 持久化模型。

## 技术栈主线

当前正式主线已回到 PDD 要求：

- 前端：`apps/web-vue`，Vue3 + Element Plus + Pinia + Vue Router；
- 后端：`apps/api-py`，FastAPI + SQLAlchemy + Pydantic；
- 迁移：Alembic，目标数据库 `zhujian`、schema `public`；
- 异步任务：Celery + Redis，队列按 `parse/ai/export/calc` 分流；
- 对象存储：MinIO/S3 接入，开发环境支持本地兜底；
- 成果导出：Python Office 工具链生成 Word、Excel 和归档包。
- LibreOffice：配置 `LIBREOFFICE_PATH` 或安装 `soffice` 后，归档包会附带 PDF 转换结果；
- 模型网关：配置 `MODEL_GATEWAY_URL` 后章节生成优先走网关，不可用时自动降级到本地可审计 fallback；
- 平台能力状态：系统管理页和 `/api/platform/status` 可查看 Redis、MinIO、PostGIS、pgvector、LibreOffice、模型网关状态。

原 React + Express 实现已移至 `archive/react-express-prototype`，不再作为正式第一阶段主线扩展。

## 环境注意

远端 PostgreSQL 当前可连接并已完成 Alembic 业务表迁移。`zhujian.public` 已启用 `PostGIS 3.4.4` 与 `pgvector 0.8.1`，`document_chunks.embedding vector(1536)` 和 ivfflat 向量索引已创建。

## 第一阶段验收

```bash
npm run api:migrate
python scripts/phase1_acceptance.py
npm run typecheck
npm run build
```

## 第一阶段边界

本阶段聚焦正式咨询成果编制闭环。方案决策、冻结后变更和效果图任务书保留产品入口与数据结构，完整能力放入第三阶段。


## 2026-07-06 工作台边界能力完善

在上一版工作台增强基础上，新增持久化 `work_items`、`review_tasks`、`notifications`，并补充工作项领取/完成/转交、审核通过/退回、通知已读、异步任务取消/重试、疑似卡住检测和项目成员可见性过滤。

新增接口：

```text
POST /api/work-items/{item_id}/claim
POST /api/work-items/{item_id}/complete
POST /api/work-items/{item_id}/transfer
POST /api/review-tasks/{task_id}/approve
POST /api/review-tasks/{task_id}/reject
POST /api/notifications/{notification_id}/read
POST /api/tasks/{task_id}/cancel
POST /api/tasks/{task_id}/retry
```

新增迁移：

```text
apps/api-py/alembic/versions/20260706_0004_workbench_boundary_models.py
```

详见：`docs/00_project/工作台边界能力完善说明_20260706.md`。


## v1.2 工作台边界内继续完善（2026-07-06）

本次继续限定在工作台功能边界内，补齐前端转交入口、工作项/审核记录查看、动作级权限校验和审核事件留痕修正，不扩展到报告、GIS、投资测算或方案比选等其他业务模块。

更新后的功能完成度 Checklist 已放入：

```text
docs/00_project/住建平台功能完成度Checklist_v1.4_20260706.xlsx
```


## v1.3 / v1.4 工作台版本号说明（2026-07-06）

根据后续版本顺延要求，上一轮“工作台边界内继续完善”按 v1.3 归档；本轮继续开发版本号调整为 v1.4。

v1.4 仍严格限定在工作台边界内，新增工作项/审核任务 SLA 提示、行级动作权限返回、前端按权限展示操作按钮、疑似卡住任务后端留痕，并更新代码包及 Checklist 命名。

最新 Checklist 已放入：

```text
docs/00_project/住建平台功能完成度Checklist_v1.4_20260706.xlsx
```

详见：`docs/00_project/工作台功能v1.4边界内完善说明_20260706.md`。


## v1.5 工作台边界内继续完善（2026-07-06）

本轮继续严格限定在工作台功能边界内，在 v1.4 基础上补充 SLA 提醒持久化、工作项/审核任务 SLA 详细字段、行级动作原因、任务心跳状态、疑似卡住分钟数以及工作台健康状态汇总。

版本号已顺延为 `1.5.0`，上一版 v1.4 保持归档。

最新 Checklist 已放入：

```text
docs/00_project/住建平台功能完成度Checklist_v1.5_20260706.xlsx
```

详见：`docs/00_project/工作台功能v1.5边界内完善说明_20260706.md`。

## v1.6 工作台剩余功能收口（2026-07-06）

本版本继续严格限定在工作台功能边界内，重点关闭 v1.5 之后仍未完成的协同闭环能力：

- SLA 到期提醒进一步升级为自动升级/催办留痕：逾期或即将到期的工作项、审核任务会生成工作台事件和站内提醒；
- P0/P1 审核任务加入会签门禁：未满足会签数量时不允许直接通过，工作台返回会签进度和不可通过原因；
- 通知中心 API 补齐：支持通知列表、状态筛选、项目筛选，以及通知订阅偏好读取和更新；
- 异步任务取消支持 `force` 强制终止参数，疑似卡住任务可从工作台发起强制终止请求并写入阶段日志；
- 工作台后端增加卡片级容错辅助：非关键卡片查询失败时记录 `cardErrors` 并在 `cardHealth` 中降级展示。

版本号已更新为 `1.6.0`。

Checklist 已随代码包放入：

```text
docs/00_project/住建平台功能完成度Checklist_v1.6_20260706.xlsx
```

详见：`docs/00_project/工作台功能v1.6剩余功能收口说明_20260706.md`。
