# 工作台功能 v1.2 迭代说明

更新时间：2026-07-06

## 版本定位

本版本在“工作台边界补齐版”的基础上继续完善工作台闭环，版本号升级为 `v1.2.0`。目标是让工作台不只是展示聚合数据，而是能够承载待办处理、审核协同、通知处理、后台任务治理和操作留痕。

## 本次新增能力

### 1. 工作项评论流与取消

新增工作项事件表 `workbench_events`，支持对工作项进行：

- 领取留痕；
- 转交留痕；
- 完成留痕；
- 补充意见；
- 取消工作项。

新增接口：

```text
GET  /api/work-items/{item_id}/events
POST /api/work-items/{item_id}/comments
POST /api/work-items/{item_id}/cancel
```

前端工作台待办区新增“意见”和“取消”操作。

### 2. 审核任务分配、意见与会签

审核任务新增：

- 分配审核人；
- 审核意见追加；
- 会签意见；
- 通过/退回留痕；
- 分配审核人时定向生成通知。

新增接口：

```text
GET  /api/review-tasks/{task_id}/events
POST /api/review-tasks/{task_id}/comments
POST /api/review-tasks/{task_id}/assign
POST /api/review-tasks/{task_id}/countersign
```

前端待审核队列新增“分配、意见、会签”操作。

### 3. 通知批量处理与归档

新增通知批量处理接口：

```text
POST /api/notifications/read-all
POST /api/notifications/{notification_id}/archive
```

前端风险与提醒面板新增：

- 全部已读；
- 单条已读；
- 单条归档。

### 4. 任务阶段级日志

新增 `task_events` 表，后台任务提交、取消、重试时写入阶段日志。

新增接口：

```text
GET /api/tasks/{task_id}/events?taskKind=parse|quality|artifact
```

前端异步任务中心支持展开行查看阶段日志。

### 5. Celery 取消增强

新增 `revoke_task()`，在取消后台任务时尝试调用 Celery revoke。当前为 best-effort 策略：即使 broker 不可用，也会保留业务侧取消状态和任务日志。

### 6. 工作台事件视图

近期活动面板新增“审计 / 事件”切换：

- 审计：展示系统审计日志；
- 事件：展示工作项、审核任务的处理留痕。

## 数据库迁移

新增迁移：

```text
apps/api-py/alembic/versions/20260706_0005_workbench_v12_events.py
```

新增表：

```text
workbench_events
任务/审核/工作项协作事件

task_events
后台任务阶段日志

notification_subscriptions
通知订阅偏好预留表
```

## 仍未完全完成的边界

本版本继续推进工作台能力，但以下内容仍建议放入后续迭代：

- 正式会签参与人列表和会签完成率；
- 通知订阅偏好前端配置；
- WebSocket/Server-Sent Events 实时推送；
- Worker 内部安全停止点；
- 任务阶段日志由 Worker 自动写入每个阶段；
- 全量业务接口 RBAC 和项目成员数据隔离；
- 独立工作项详情页。

## 验证记录

已执行：

```bash
python -m compileall apps/api-py/app apps/api-py/tests
PYTHONPATH=apps/api-py DATABASE_URL=sqlite+pysqlite:///:memory: python apps/api-py/tests/test_dashboard.py
```

当前容器缺少 `minio` 和前端 npm 依赖，因此 FastAPI 完整导入、Vue typecheck 和 Vite build 请在本地执行：

```bash
npm ci
npm run typecheck
npm run build
python -m pip install -r apps/api-py/requirements.txt
npm run api:migrate
```
