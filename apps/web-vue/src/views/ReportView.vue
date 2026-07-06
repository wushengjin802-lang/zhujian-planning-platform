<script setup lang="ts">
import { MagicStick } from "@element-plus/icons-vue";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
</script>

<template>
  <el-row :gutter="16">
    <el-col :xs="24" :lg="8">
      <el-card class="panel" shadow="never">
        <div class="panel-title"><h2>章节清单</h2></div>
        <el-timeline>
          <el-timeline-item v-for="chapter in store.projectChapters" :key="chapter.id">
            <strong>{{ chapter.no }}. {{ chapter.title }}</strong>
            <div><el-tag>{{ chapter.status }}</el-tag> 引用 {{ chapter.citationCount }} 条</div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-col>
    <el-col :xs="24" :lg="16">
      <el-card class="panel" shadow="never">
        <div class="panel-title">
          <h2>章节编制草稿</h2>
          <el-tag type="success">Tiptap/ProseMirror 待接入</el-tag>
        </div>
        <el-alert title="当前版本根据已确认事实、资料切片和模板结构生成章节初稿，并记录引用回链。" type="info" show-icon :closable="false" />
        <el-table :data="store.projectChapters" stripe>
          <el-table-column label="章节" min-width="220">
            <template #default="{ row }">{{ row.no }}. {{ row.title }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" />
          <el-table-column label="操作" width="260">
            <template #default="{ row }">
              <el-button size="small" :icon="MagicStick" @click="store.generateChapter(row)">生成初稿</el-button>
              <el-button v-if="row.status !== '待审核' && row.status !== '已审核'" size="small" @click="store.submitChapter(row)">提交</el-button>
              <el-button v-if="row.status !== '已审核'" size="small" @click="store.approveChapter(row)">通过</el-button>
            </template>
          </el-table-column>
        </el-table>
        <h3>引用回链</h3>
        <el-empty v-if="!store.data.citations.length" description="生成章节初稿后自动形成引用回链" />
        <el-timeline v-else>
          <el-timeline-item v-for="citation in store.data.citations.slice(0, 8)" :key="citation.id">
            <strong>{{ citation.excerpt }}</strong>
            <div>{{ citation.source }} {{ citation.chunkId ? `· ${citation.chunkId}` : "" }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-col>
  </el-row>
</template>

