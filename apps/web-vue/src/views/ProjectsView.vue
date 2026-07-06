<script setup lang="ts">
import { reactive } from "vue";
import { Plus } from "@element-plus/icons-vue";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
const form = reactive({ open: false, name: "新建可研样本项目", location: "待补充" });

async function submit() {
  await store.addProject({ name: form.name, location: form.location });
  form.open = false;
}
</script>

<template>
  <div class="toolbar">
    <strong>项目建档</strong>
    <el-button type="primary" :icon="Plus" @click="form.open = true">新建项目</el-button>
  </div>
  <el-row :gutter="16">
    <el-col v-for="project in store.data.projects" :key="project.id" :xs="24" :md="12" :lg="8">
      <el-card class="panel" shadow="never" @click="store.currentProjectId = project.id">
        <div class="panel-title">
          <h2>{{ project.name }}</h2>
          <el-tag :type="project.risk === '阻断' ? 'danger' : project.risk === '严重' ? 'warning' : 'info'">{{ project.risk }}</el-tag>
        </div>
        <p>{{ project.location }} · {{ project.type }}</p>
        <el-progress :percentage="project.progress" />
        <small>{{ project.owner }} · {{ project.phase }}</small>
      </el-card>
    </el-col>
  </el-row>
  <el-dialog v-model="form.open" title="新建项目" width="420px">
    <el-form label-position="top">
      <el-form-item label="项目名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="项目地点"><el-input v-model="form.location" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="form.open = false">取消</el-button>
      <el-button type="primary" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

