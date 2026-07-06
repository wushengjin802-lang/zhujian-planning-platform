# 第一阶段 MVP 验收执行记录

## 执行时间

2026-07-03

## 验收范围

- 登录认证和写接口鉴权；
- 资料上传、解析任务、切片生成和来源定位；
- 章节初稿生成、事实和资料引用回链；
- 质量检查任务和发布门禁问题生成；
- Word、Excel、PPT、归档包导出；
- PostgreSQL、PostGIS、pgvector、Alembic 迁移状态；
- Vue3 前端类型检查和生产构建。

## 执行命令

```bash
npm run api:migrate
python scripts/phase1_acceptance.py
npm run typecheck
npm run build
```

## 执行结果

```json
{
  "status": "passed",
  "project": "P001",
  "parseExecution": "sync",
  "qualityExecution": "sync",
  "exportExecution": "sync",
  "citations": 2
}
```

本机未启动 Redis，因此解析、质量检查和导出按设计走同步兜底。部署环境启动 Redis 和 Celery worker 后，相同接口会优先进入队列。

## 剩余联调项

- 在目标环境启动 Redis、Celery worker、MinIO、LibreOffice 后复跑验收脚本；
- 使用客户提供的脱敏历史项目资料替换演示样本；
- 对扫描 PDF 和图片资料接入 OCR/VLM；
- 按企业正式模板精修 Word、Excel、PPT 的版式。
