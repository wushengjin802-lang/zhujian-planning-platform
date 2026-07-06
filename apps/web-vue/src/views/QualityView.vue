<script setup lang="ts">
import { VideoPlay } from "@element-plus/icons-vue";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
</script>

<template>
  <div class="toolbar">
    <strong>质量门禁</strong>
    <el-button type="primary" :icon="VideoPlay" @click="store.runQualityCheck">运行检查</el-button>
  </div>
  <el-card class="table-card" shadow="never">
    <el-table :data="store.projectIssues" stripe>
      <el-table-column prop="severity" label="等级" width="100">
        <template #default="{ row }"><el-tag :type="row.severity === '阻断' ? 'danger' : row.severity === '严重' ? 'warning' : 'info'">{{ row.severity }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="type" label="类型" />
      <el-table-column prop="title" label="问题" min-width="260" />
      <el-table-column prop="owner" label="责任人" />
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button v-if="row.status !== '已关闭'" size="small" @click="store.closeIssue(row)">关闭</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

