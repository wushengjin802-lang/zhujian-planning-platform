<script setup lang="ts">
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
</script>

<template>
  <section class="system-grid">
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>组织与角色</h2></div>
      <el-table :data="store.data.users">
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="role" label="角色" />
        <el-table-column prop="department" label="部门" />
      </el-table>
    </el-card>
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>最近审计</h2></div>
      <el-table :data="store.data.auditLogs">
        <el-table-column prop="action" label="动作" />
        <el-table-column prop="entityType" label="对象" />
        <el-table-column prop="actor" label="操作者" />
      </el-table>
    </el-card>
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>质量规则</h2></div>
      <el-table :data="store.data.qualityRules">
        <el-table-column prop="name" label="规则" />
        <el-table-column prop="severity" label="等级" />
        <el-table-column prop="enabled" label="状态">
          <template #default="{ row }">{{ row.enabled ? "启用" : "停用" }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
  <el-card class="panel capability-panel" shadow="never">
    <div class="panel-title"><h2>平台能力状态</h2><el-tag>运行状态</el-tag></div>
    <el-descriptions v-if="store.platformStatus" :column="2" border>
      <el-descriptions-item label="数据空间">{{ store.platformStatus.database.schema }}</el-descriptions-item>
      <el-descriptions-item label="后台任务服务">
        <el-tag :type="store.platformStatus.redis.available ? 'success' : 'warning'">{{ store.platformStatus.redis.available ? "可用" : "未连接" }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="空间分析能力">
        <el-tag :type="store.platformStatus.database.extensions.postgis?.installed ? 'success' : 'warning'">
          {{ store.platformStatus.database.extensions.postgis?.installed ? "可用" : "待配置" }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="智能检索能力">
        <el-tag :type="store.platformStatus.database.extensions.vector?.installed ? 'success' : 'warning'">
          {{ store.platformStatus.database.extensions.vector?.installed ? "可用" : "待配置" }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="资料存储服务">
        <el-tag :type="store.platformStatus.minio.available ? 'success' : 'info'">{{ store.platformStatus.minio.available ? "可用" : "本地兜底" }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="成果转换服务">
        <el-tag :type="store.platformStatus.libreOffice.available ? 'success' : 'warning'">{{ store.platformStatus.libreOffice.available ? "可用" : "待配置" }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="智能生成服务">
        <el-tag :type="store.platformStatus.modelGateway.available ? 'success' : 'info'">{{ store.platformStatus.modelGateway.available ? "可用" : "本地规则" }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="生成配置">
        {{ store.platformStatus.modelGateway.configured ? "已配置" : "未配置，使用本地规则" }}
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>
