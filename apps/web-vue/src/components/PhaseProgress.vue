<script setup lang="ts">
import { RouterLink } from "vue-router";

type PhaseStep = {
  no: number;
  name?: string;
  title?: string;
  sub?: string;
  subtitle?: string;
  route?: string;
};

withDefaults(
  defineProps<{
    steps: PhaseStep[];
    activeNo?: number;
    linkable?: boolean;
    ariaLabel?: string;
  }>(),
  {
    activeNo: 1,
    linkable: true,
    ariaLabel: "项目阶段进度"
  }
);

function stepName(step: PhaseStep) {
  return step.name || step.title || "未命名阶段";
}

function stepSubtitle(step: PhaseStep) {
  return step.sub || step.subtitle || "";
}
</script>

<template>
  <section class="phase-progress-card" :aria-label="ariaLabel">
    <div class="phase-progress-track">
      <template v-for="(step, index) in steps" :key="step.no">
        <component
          :is="linkable && step.route ? RouterLink : 'div'"
          :to="linkable && step.route ? `/${step.route}` : undefined"
          class="phase-step"
          :class="{ active: step.no === activeNo, passed: step.no < activeNo }"
        >
          <span class="phase-step-index">{{ step.no }}</span>
          <strong>{{ stepName(step) }}</strong>
          <small>{{ stepSubtitle(step) }}</small>
        </component>
        <span
          v-if="index < steps.length - 1"
          class="phase-connector"
          :class="{ active: step.no <= activeNo }"
          aria-hidden="true"
        />
      </template>
    </div>
  </section>
</template>

<style scoped>
.phase-progress-card {
  box-sizing: border-box;
  width: calc(100% - 48px);
  margin: 18px 24px 0;
  padding: 38px 52px 34px;
  overflow: hidden;
  border: 1px solid rgba(194, 207, 222, 0.78);
  border-radius: 24px;
  background:
    radial-gradient(circle at 8% 28%, rgba(23, 190, 165, 0.1), transparent 18%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(252, 254, 255, 0.96));
  box-shadow: 0 18px 40px rgba(22, 42, 62, 0.08);
}

.phase-progress-track {
  display: grid;
  grid-template-columns: repeat(7, minmax(116px, 1fr));
  align-items: start;
  min-width: 920px;
}

.phase-step {
  position: relative;
  z-index: 2;
  display: grid;
  justify-items: center;
  min-width: 0;
  color: #25364b;
  text-align: center;
  text-decoration: none;
  outline: none;
}

.phase-step:focus-visible .phase-step-index {
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.2);
}

.phase-step-index {
  display: grid;
  width: 54px;
  height: 54px;
  margin-bottom: 22px;
  place-items: center;
  border: 3px solid #c6d1e1;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.96);
  color: #25364b;
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 2px 12px rgba(34, 64, 92, 0.05);
  transition: all 0.2s ease;
}

.phase-step:hover .phase-step-index {
  transform: translateY(-1px);
  border-color: #9eb2ca;
}

.phase-step.active .phase-step-index {
  border-color: rgba(231, 255, 250, 0.98);
  background: linear-gradient(145deg, #14b8a6 0%, #0f9f86 48%, #06906e 100%);
  color: #ffffff;
  box-shadow:
    0 0 0 5px rgba(20, 184, 166, 0.2),
    0 0 20px rgba(20, 184, 166, 0.42),
    0 12px 24px rgba(15, 159, 134, 0.22);
}

.phase-step.passed .phase-step-index {
  border-color: rgba(231, 255, 250, 0.96);
  background: linear-gradient(145deg, #49cdbd 0%, #14a98f 100%);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(20, 184, 166, 0.18);
}

.phase-step strong {
  display: block;
  color: #111f35;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 0.01em;
  line-height: 1.2;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.phase-step small {
  display: block;
  margin-top: 10px;
  color: #607187;
  font-size: 16px;
  line-height: 1.15;
  white-space: nowrap;
}

.phase-step.active strong,
.phase-step.active small {
  color: #089981;
}

.phase-step.active::after {
  content: "";
  width: 96px;
  height: 7px;
  margin-top: 24px;
  border-radius: 999px;
  background: linear-gradient(90deg, #0fa88d, #16b39b);
  box-shadow: 0 6px 12px rgba(16, 163, 139, 0.18);
}

.phase-connector {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 54px;
  margin: 0 -20px;
  align-self: start;
  pointer-events: none;
  transform: translateY(2px);
}

.phase-connector::before {
  content: "";
  position: absolute;
  top: 24px;
  left: 4px;
  right: 4px;
  height: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(196, 210, 226, 0.2), #cbd8e6 42%, rgba(196, 210, 226, 0.16));
}

.phase-connector::after {
  content: "»»";
  position: absolute;
  top: 3px;
  left: 50%;
  color: #a9bad0;
  font-family: Arial, sans-serif;
  font-size: 42px;
  font-weight: 900;
  letter-spacing: -10px;
  line-height: 1;
  text-shadow: 0 0 10px rgba(82, 121, 164, 0.22);
  transform: translateX(-50%);
}

.phase-connector.active::before {
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.15), #2dd4bf 48%, rgba(20, 184, 166, 0.08));
  box-shadow: 0 0 16px rgba(45, 212, 191, 0.35);
}

.phase-connector.active::after {
  color: #2dd4bf;
  text-shadow:
    0 0 10px rgba(45, 212, 191, 0.75),
    0 0 18px rgba(45, 212, 191, 0.46);
}

@media (max-width: 1280px) {
  .phase-progress-card {
    padding: 30px 28px 28px;
    overflow-x: auto;
  }

  .phase-progress-track {
    min-width: 980px;
  }
}

@media (max-width: 720px) {
  .phase-progress-card {
    width: calc(100% - 24px);
    margin: 12px 12px 0;
    padding: 24px 20px 22px;
    border-radius: 18px;
  }
}
</style>
