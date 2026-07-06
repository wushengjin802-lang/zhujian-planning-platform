<script setup lang="ts">
import { reactive, ref } from "vue";
import { Plus, Upload } from "@element-plus/icons-vue";
import type { UploadRequestOptions } from "element-plus";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();
const form = reactive({ open: false, name: "新上传资料.pdf", category: "基础资料" });
const uploadRef = ref();

async function submit() {
  await store.addDocument({ name: form.name, category: form.category });
  form.open = false;
}

function uploadFile(options: UploadRequestOptions) {
  return store.upload(options.file as File);
}
</script>

<template>
  <div class="toolbar">
    <strong>资料清点与解析</strong>
    <div>
      <el-upload ref="uploadRef" :show-file-list="false" :http-request="uploadFile">
        <el-button :icon="Upload">上传文件</el-button>
      </el-upload>
      <el-button type="primary" :icon="Plus" @click="form.open = true">登记资料</el-button>
    </div>
  </div>
  <el-card class="table-card" shadow="never">
    <el-table :data="store.projectDocuments" stripe>
      <el-table-column prop="name" label="资料名称" min-width="220" />
      <el-table-column prop="category" label="分类" />
      <el-table-column prop="version" label="版本" width="100" />
      <el-table-column prop="parseStatus" label="解析状态" width="120">
        <template #default="{ row }"><el-tag>{{ row.parseStatus }}</el-tag></template>
      </el-table-column>
      <el-table-column label="文件/切片" width="140">
        <template #default="{ row }">{{ row.fileSize ? `${Math.round(row.fileSize / 1024)} KB` : "未上传" }} / {{ row.chunkCount ?? 0 }}片</template>
      </el-table-column>
      <el-table-column prop="source" label="来源" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.parseStatus !== '已解析'" size="small" @click="store.parse(row)">解析</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
  <el-dialog v-model="form.open" title="登记资料" width="420px">
    <el-form label-position="top">
      <el-form-item label="资料名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="分类"><el-input v-model="form.category" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="form.open = false">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

