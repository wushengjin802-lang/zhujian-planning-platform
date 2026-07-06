<script setup lang="ts">
import { Download, VideoPlay } from "@element-plus/icons-vue";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
</script>

<template>
  <section class="split-grid">
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>成果清单</h2><el-tag>Python Office</el-tag></div>
      <el-table :data="store.projectArtifacts">
        <el-table-column prop="name" label="成果" min-width="220" />
        <el-table-column prop="format" label="格式" width="100" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }"><el-tag :type="row.status === '已生成' ? 'success' : row.status === '受阻' ? 'danger' : 'info'">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" :icon="VideoPlay" @click="store.exportArtifact(row.id)">导出</el-button>
            <el-button v-if="row.status === '已生成'" size="small" :icon="Download" tag="a" :href="`/api/artifacts/${row.id}/download`">下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>发布门禁</h2></div>
      <el-result :icon="store.blocked ? 'warning' : 'success'" :title="store.blocked ? '存在未关闭阻断问题' : '质量门禁已通过'" :sub-title="store.blocked ? '正式成果发布暂不可用' : '可进入成果发布和归档'" />
    </el-card>
  </section>
</template>

