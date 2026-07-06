<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessageBox } from "element-plus";
import {
  Bell,
  DataAnalysis,
  Document,
  Files,
  Finished,
  Folder,
  Grid,
  House,
  Location,
  Management,
  Memo,
  Setting,
  UserFilled
} from "@element-plus/icons-vue";
import loginBackground from "./assets/login-bg.png";
import { usePlatformStore } from "./stores/platform";

const store = usePlatformStore();
const route = useRoute();
const bootstrapped = ref(false);
const email = ref("owner@zhujian.local");
const password = ref("demo123");

const routeIcon: Record<string, unknown> = {
  dashboard: House,
  projects: Folder,
  documents: Files,
  facts: Grid,
  report: Document,
  analysis: Location,
  comparison: DataAnalysis,
  quality: Finished,
  artifacts: Memo,
  knowledge: Management,
  system: Setting
};

const meta = computed(() => store.data.routeMeta[String(route.name ?? "dashboard")] ?? ["工作台", ""]);

onMounted(async () => {
  await store.bootstrap();
  bootstrapped.value = true;
});

async function submitLogin() {
  await store.doLogin(email.value, password.value);
}

async function confirmLogout() {
  await ElMessageBox.confirm("确认退出当前账号？", "退出登录", { type: "warning" });
  await store.doLogout();
}
</script>

<template>
  <section v-if="!bootstrapped || !store.currentUser" class="login-page" :style="{ backgroundImage: `url(${loginBackground})` }">
    <div class="login-panel">
      <div class="login-brand">
        <span>住建智策</span>
        <strong>工程咨询辅助编制平台</strong>
      </div>
      <h1>欢迎登录</h1>
      <p>面向住建项目前期策划、资料解析、报告编制、质量门禁和成果归档的一体化工作台。</p>
      <el-form class="login-form" label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="email" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" size="large" type="password" show-password autocomplete="current-password" @keyup.enter="submitLogin" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="store.loading" @click="submitLogin">登录系统</el-button>
      </el-form>
    </div>
  </section>

  <el-container v-else class="app-shell">
    <el-aside class="sidebar" width="280px">
      <div class="brand">
        <div class="brand-mark">策</div>
        <div>
          <strong>住建智策</strong>
          <span>工程咨询辅助编制平台</span>
        </div>
      </div>

      <section class="project-chip" v-if="store.currentProject">
        <span>当前项目</span>
        <strong>{{ store.currentProject.name }}</strong>
        <small>{{ store.currentProject.type }} · {{ store.currentProject.phase }}</small>
      </section>

      <el-scrollbar class="nav-scroll">
        <nav class="main-nav">
          <section v-for="group in store.data.navGroups" :key="group.title">
            <h2>{{ group.title }}</h2>
            <router-link v-for="item in group.items" :key="item.route" :to="`/${item.route}`" class="nav-item">
              <el-icon><component :is="routeIcon[item.route]" /></el-icon>
              <span>{{ item.label }}</span>
              <em v-if="item.count">{{ item.count }}</em>
            </router-link>
          </section>
        </nav>
      </el-scrollbar>

      <div class="sidebar-foot">
        <el-icon><Finished /></el-icon>
        <span>项目流程闭环运行中</span>
      </div>
    </el-aside>

    <el-container class="main-shell">
      <el-header class="topbar" height="112px">
        <div>
          <span class="eyebrow">项目策划与成果编制</span>
          <h1>{{ meta[0] }}</h1>
          <p>{{ meta[1] }}</p>
        </div>
        <div class="topbar-actions">
          <el-select v-model="store.currentProjectId" class="project-select" placeholder="选择项目">
            <el-option v-for="project in store.data.projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
          <el-button :icon="Bell" circle />
          <el-button :icon="UserFilled" @click="confirmLogout">{{ store.currentUser.name }}</el-button>
        </div>
      </el-header>

      <section class="workflow-strip">
        <router-link v-for="step in store.data.workflow" :key="step.no" :to="`/${step.route}`">
          <span>{{ step.no }}</span>
          <strong>{{ step.name }}</strong>
          <small>{{ step.sub }}</small>
        </router-link>
      </section>

      <div class="status-line" v-loading="store.loading">{{ store.notice }}</div>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
