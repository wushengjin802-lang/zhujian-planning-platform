<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import type { FactItem } from "../types";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();

async function resolve(fact: FactItem) {
  const result = await ElMessageBox.prompt("确认后的事实值", "处理冲突", { inputValue: fact.value });
  await store.resolveFact(fact, result.value);
}
</script>

<template>
  <el-card class="table-card" shadow="never">
    <el-table :data="store.projectFacts" stripe>
      <el-table-column prop="name" label="事实项" min-width="160" />
      <el-table-column prop="group" label="分组" />
      <el-table-column label="值">
        <template #default="{ row }">{{ row.value }}{{ row.unit ?? "" }}</template>
      </el-table-column>
      <el-table-column prop="source" label="来源" min-width="220" />
      <el-table-column prop="owner" label="责任人" />
      <el-table-column prop="status" label="状态">
        <template #default="{ row }"><el-tag :type="row.status === '有冲突' ? 'warning' : row.status === '已锁定' ? 'success' : 'info'">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button v-if="row.status === '有冲突'" size="small" @click="resolve(row)">处理</el-button>
          <el-button v-if="row.status !== '已确认' && row.status !== '已锁定'" size="small" @click="store.confirmFact(row)">确认</el-button>
          <el-button v-if="row.status !== '已锁定'" size="small" @click="store.lockFact(row)">锁定</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

