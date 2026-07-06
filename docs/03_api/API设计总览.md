# API 设计总览

## 当前已提供接口

当前接口已由 FastAPI 主线提供，并从 PostgreSQL 读取业务数据。前端启动数据由 `/api/bootstrap` 聚合返回。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/api/bootstrap` | 前端启动所需的项目、资料、事实、章节、质量和成果数据 |
| POST | `/api/auth/login` | 登录并创建会话 token |
| GET | `/api/auth/me` | 获取当前登录用户 |
| POST | `/api/auth/logout` | 退出登录 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 新建项目 |
| GET | `/api/projects/:id` | 项目详情 |
| GET | `/api/projects/:id/documents` | 项目资料清单 |
| POST | `/api/projects/:id/documents` | 登记项目资料 |
| POST | `/api/projects/:id/documents/upload` | 上传项目资料文件并登记元数据 |
| GET | `/api/projects/:id/facts` | 项目事实与指标 |
| PATCH | `/api/facts/:id` | 更新事实值、状态、来源或责任人 |
| GET | `/api/projects/:id/chapters` | 项目报告章节 |
| PATCH | `/api/chapters/:id` | 更新章节状态或内容 |
| POST | `/api/chapters/:id/generate` | 根据已确认事实生成章节初稿 |
| GET | `/api/projects/:id/quality-issues` | 项目质量问题 |
| PATCH | `/api/quality-issues/:id` | 更新质量问题状态 |
| GET | `/api/projects/:id/artifacts` | 项目成果清单 |
| POST | `/api/artifacts/:id/export` | 请求生成成果，受阻断问题门禁控制 |
| GET | `/api/artifacts/:id/download` | 下载已生成成果文件 |
| POST | `/api/documents/parse-jobs` | 创建资料解析任务 |
| POST | `/api/documents/:id/parse` | 执行 MVP 资料解析并更新资料状态 |
| POST | `/api/quality/checks` | 创建质量检查任务 |
| GET | `/api/templates` | 报告模板列表 |
| GET | `/api/knowledge` | 知识条目列表 |
| GET | `/api/users` | 用户与角色列表 |
| GET | `/api/audit-logs` | 最近审计日志 |
| GET | `/api/platform/status` | 查看数据库扩展、Redis、MinIO、LibreOffice、模型网关状态 |
| GET | `/api/model-gateway/status` | 查看统一模型网关配置与可用性 |
| POST | `/api/model-gateway/generate` | 通过模型网关或本地 fallback 生成文本 |

## 权限说明

第一阶段已对写入类接口增加 Bearer Token 校验。未登录时，项目创建、资料上传、事实更新、章节生成、质量检查、成果导出等接口返回 `401`。

## 后续扩展

- POST `/api/reports/:id/generate` 生成章节初稿；
- POST `/api/artifacts/export` 生成 Word、Excel 或归档包。
- 将资料解析、质量检查、成果导出从 API 同步执行进一步切换为 Celery 任务状态轮询；
- 接入模型网关、Embedding、重排序、OCR/VLM 后补齐 RAG 检索和引用证据链。
