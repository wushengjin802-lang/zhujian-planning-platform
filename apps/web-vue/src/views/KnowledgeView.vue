<script setup lang="ts">
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
</script>

<template>
  <section class="split-grid">
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>报告模板</h2></div>
      <el-table :data="store.data.templates">
        <el-table-column prop="name" label="模板" min-width="260" />
        <el-table-column prop="reportType" label="类型" />
        <el-table-column prop="version" label="版本" />
        <el-table-column prop="status" label="状态" />
      </el-table>
    </el-card>
    <el-card class="panel" shadow="never">
      <div class="panel-title"><h2>知识条目</h2></div>
      <el-table :data="store.data.knowledgeItems">
        <el-table-column prop="title" label="标题" min-width="260" />
        <el-table-column prop="category" label="分类" />
        <el-table-column prop="status" label="状态" />
      </el-table>
    </el-card>
  </section>
</template>

