# 工作台功能 v1.5 边界内完善说明

版本：v1.5.0  
日期：2026-07-06

## 开发边界

本次继续限定在工作台功能边界内，只增强工作台已有对象和页面能力，不新增报告编制、GIS、投资测算、方案比选等非工作台业务模块。

## 本次完成内容

1. **SLA 提醒持久化**  
   在工作台聚合时，对已逾期和 24 小时内到期的工作项、审核任务生成站内提醒，避免 SLA 风险只停留在前端展示。

2. **更完整的 SLA 字段**  
   工作项和审核任务返回 `dueHoursRemaining`、`slaLevel`、`slaLabel`，前端可展示更明确的逾期或到期信息。

3. **行级动作原因**  
   工作项和审核任务返回 `actionReasons`，用于说明不可执行动作的原因，后续可接入禁用按钮或提示。

4. **任务心跳状态**  
   异步任务返回 `heartbeat` 与 `stuckMinutes`，用于区分“正常更新”“长时间未更新”“疑似卡住”。

5. **工作台健康状态**  
   `GET /api/dashboard` 新增 `cardHealth` 与 `slaSummary`，对项目范围、待办、审核、任务、质量、通知等卡片进行健康汇总。

6. **前端健康区块**  
   工作台页面新增“工作台健康状态”区块，统一展示 SLA 摘要和各卡片健康状态。

7. **版本号顺延**  
   根包、前端包、FastAPI OpenAPI 和后端 pyproject 版本号更新为 `1.5.0`。

## 新增/增强的返回字段

```text
GET /api/dashboard
  slaSummary
  cardHealth
  workItems[].dueHoursRemaining
  workItems[].slaLevel
  workItems[].slaLabel
  workItems[].actionReasons
  reviewQueue[].dueHoursRemaining
  reviewQueue[].slaLevel
  reviewQueue[].slaLabel
  reviewQueue[].actionReasons
  tasks[].heartbeat
  tasks[].stuckMinutes
```

## 仍未扩展的范围

以下能力仍属于后续版本或平台级治理，本次未扩展：

- 完整 RBAC；
- 工作项 SLA 自动升级和自动催办；
- 评论回复流；
- 正式会签规则；
- 独立通知中心和推送订阅；
- Worker 内部阶段级全面埋点；
- 任务安全停止点；
- 单卡后端完全隔离执行。
