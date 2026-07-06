<script setup lang="ts">
import { computed, onMounted } from "vue";
import { Coin, DataBoard, Loading, Money, TrendCharts } from "@element-plus/icons-vue";
import { usePlatformStore } from "../stores/platform";

const store = usePlatformStore();

const estimate = computed(() => store.investmentEstimate);
const output = computed(() => estimate.value?.output);
const sensitivity = computed(() => estimate.value?.sensitivity ?? []);
const statusTag = computed(() => {
  if (!estimate.value) return "未计算";
  if (estimate.value.status === "confirmed") return "已确认";
  if (estimate.value.status === "calculated") return "已计算";
  return "草稿";
});
const statusTagType = computed(() => {
  if (estimate.value?.status === "confirmed") return "success" as const;
  if (estimate.value?.status === "calculated") return "warning" as const;
  return "info" as const;
});

const metricCards = computed(() => {
  if (!output.value) return [];
  const cards = [
    { label: "项目总投资", value: `${output.value.totalInvestment} 万元`, icon: Money, color: "#2b7a4b" },
    { label: "投资构成项", value: `${output.value.breakdown.length} 项`, icon: DataBoard, color: "#2d6ea0" },
  ];
  const unitKeys = Object.keys(output.value.unitMetrics);
  if (unitKeys.length > 0) {
    const um = output.value.unitMetrics[unitKeys[0]];
    cards.push({ label: `单位投资（${unitKeys[0]}）`, value: `${um.unitInv} 万元/㎡`, icon: TrendCharts, color: "#b05a1e" });
  }
  if (Object.keys(output.value.funding).length > 0) {
    const bond = output.value.funding["专项债资金"];
    if (bond) {
      cards.push({ label: "专项债资金", value: `${bond.amount} 万元`, icon: Coin, color: "#7c3aed" });
    }
  }
  return cards;
});

const sensitivityRows = computed(() => {
  if (!output.value || sensitivity.value.length === 0) return [];
  const base = output.value.totalInvestmentRaw;
  return sensitivity.value.map((s) => ({
    ...s,
    baseTotal: output.value!.totalInvestment,
    isBase: s.delta === 0,
  }));
});

onMounted(() => {
  store.fetchInvestmentEstimate();
});
</script>

<template>
  <section>
    <!-- toolbar -->
    <div class="toolbar">
      <div>
        <el-tag :type="statusTagType" size="large">{{ statusTag }}</el-tag>
        <span v-if="estimate?.confirmedBy" style="margin-left: 12px; color: #6b7c88; font-size: 13px">
          确认人：{{ estimate.confirmedBy }}
        </span>
      </div>
      <div style="display: flex; gap: 8px">
        <el-button type="primary" :icon="Loading" :loading="store.loading" @click="store.runInvestmentCalculation()">
          重新计算
        </el-button>
        <el-button
          type="success"
          :disabled="!estimate || estimate.status === 'confirmed'"
          @click="store.confirmInvestment()"
        >
          确认结果
        </el-button>
      </div>
    </div>

    <!-- summary metric cards -->
    <div class="metric-grid" v-if="output">
      <el-card class="metric-card" shadow="never" v-for="card in metricCards" :key="card.label">
        <div>
          <span style="font-size: 13px; color: #6b7c88">{{ card.label }}</span>
          <strong :style="{ color: card.color }">{{ card.value }}</strong>
        </div>
        <el-icon :size="24" :color="card.color"><component :is="card.icon" /></el-icon>
      </el-card>
    </div>

    <div class="split-grid">
      <!-- investment breakdown -->
      <el-card class="panel" shadow="never">
        <div class="panel-title"><h2>投资构成</h2></div>
        <el-table :data="output?.breakdown ?? []" v-if="output">
          <el-table-column prop="category" label="费用类别" min-width="140" />
          <el-table-column prop="ratio" label="占比" width="90">
            <template #default="{ row }">{{ (row.ratio * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column prop="amount" label="金额（万元）" min-width="130" />
        </el-table>
        <el-empty v-else description="点击「重新计算」生成投资构成" />
      </el-card>

      <!-- funding structure + per-unit metrics -->
      <div style="display: flex; flex-direction: column; gap: 16px">
        <el-card class="panel" shadow="never" v-if="output && Object.keys(output.funding).length > 0">
          <div class="panel-title"><h2>资金结构</h2></div>
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="(item, key) in output.funding"
              :key="key"
              :label="key"
            >
              <span>{{ item.amount }} 万元</span>
              <el-tag size="small" style="margin-left: 8px">{{ (item.ratio * 100).toFixed(0) }}%</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card class="panel" shadow="never" v-if="output && Object.keys(output.unitMetrics).length > 0">
          <div class="panel-title"><h2>单位指标</h2></div>
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="(um, key) in output.unitMetrics"
              :key="key"
              :label="key"
            >
              <span>{{ um.area }} ㎡</span>
              <el-tag size="small" style="margin-left: 8px">{{ um.unitInv }} 万元/㎡</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </div>
    </div>

    <!-- sensitivity analysis -->
    <el-card class="panel" shadow="never" style="margin-top: 16px" v-if="sensitivityRows.length > 0">
      <div class="panel-title">
        <h2>敏感性分析</h2>
        <el-tag>工程费用变动情景</el-tag>
      </div>
      <el-table :data="sensitivityRows">
        <el-table-column prop="scenario" label="情景" min-width="160" />
        <el-table-column prop="baseTotal" label="基准总投资（万元）" width="160" />
        <el-table-column prop="totalVariant" label="变动后总投资（万元）" min-width="180">
          <template #default="{ row }">
            <span :style="{ color: row.changePctRaw > 0 ? '#c0392b' : row.changePctRaw < 0 ? '#1f7c62' : '#1b2b3a', fontWeight: row.isBase ? 700 : 400 }">
              {{ row.totalVariant }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="changePct" label="变化率" width="100">
          <template #default="{ row }">
            <el-tag
              v-if="!row.isBase"
              :type="row.changePctRaw > 0 ? 'danger' : 'success'"
              size="small"
            >
              {{ row.changePctRaw > 0 ? '+' : '' }}{{ row.changePct }}%
            </el-tag>
            <span v-else>基准</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- GIS placeholder -->
    <el-card class="panel" shadow="never" style="margin-top: 16px">
      <div class="panel-title"><h2>区位分析</h2><el-tag>空间分析</el-tag></div>
      <div class="map-box"></div>
    </el-card>
  </section>
</template>
