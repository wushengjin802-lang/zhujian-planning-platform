# Celery Worker

第一阶段 PDD 主线的异步任务入口位于 `apps/api-py/app/worker`。

启动命令：

```bash
npm run worker:dev
```

队列约定：

- `parse`：资料解析、OCR/VLM 预处理；
- `ai`：章节生成、RAG 检索、模型网关调用；
- `export`：Word、Excel、PPT、归档包生成；
- `calc`：质量检查、投资测算、GIS 指标计算。

