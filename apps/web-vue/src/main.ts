import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import DashboardView from "./views/DashboardView.vue";
import ProjectsView from "./views/ProjectsView.vue";
import DocumentsView from "./views/DocumentsView.vue";
import FactsView from "./views/FactsView.vue";
import ReportView from "./views/ReportView.vue";
import AnalysisView from "./views/AnalysisView.vue";
import ComparisonView from "./views/ComparisonView.vue";
import QualityView from "./views/QualityView.vue";
import ArtifactsView from "./views/ArtifactsView.vue";
import KnowledgeView from "./views/KnowledgeView.vue";
import SystemView from "./views/SystemView.vue";
import "./styles/global.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/dashboard", name: "dashboard", component: DashboardView },
    { path: "/projects", name: "projects", component: ProjectsView },
    { path: "/documents", name: "documents", component: DocumentsView },
    { path: "/facts", name: "facts", component: FactsView },
    { path: "/report", name: "report", component: ReportView },
    { path: "/analysis", name: "analysis", component: AnalysisView },
    { path: "/comparison", name: "comparison", component: ComparisonView },
    { path: "/quality", name: "quality", component: QualityView },
    { path: "/artifacts", name: "artifacts", component: ArtifactsView },
    { path: "/knowledge", name: "knowledge", component: KnowledgeView },
    { path: "/system", name: "system", component: SystemView }
  ]
});

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app");

