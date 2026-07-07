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
          :class="{ active: step.no <= activeNo, advancing: step.no === activeNo }"
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
  margin: 10px 24px 0;
  padding: 10px 24px 9px;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid rgba(194, 207, 222, 0.78);
  border-radius: 10px;
  background:
    radial-gradient(circle at 8% 26%, rgba(23, 190, 165, 0.09), transparent 16%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(252, 254, 255, 0.97));
  box-shadow: 0 8px 18px rgba(22, 42, 62, 0.06);
  scrollbar-width: thin;
}

.phase-progress-track {
  display: grid;
  grid-template-columns:
    repeat(6, minmax(74px, 1fr) minmax(34px, 0.55fr))
    minmax(74px, 1fr);
  align-items: flex-start;
  width: 100%;
  min-width: 920px;
}

.phase-step {
  position: relative;
  z-index: 2;
  display: grid;
  justify-items: center;
  min-width: 0;
  padding-bottom: 8px;
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
  width: 32px;
  height: 32px;
  margin-bottom: 5px;
  place-items: center;
  border: 2px solid #c6d1e1;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.96);
  color: #25364b;
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
  box-shadow: 0 2px 8px rgba(34, 64, 92, 0.05);
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
    0 0 0 3px rgba(20, 184, 166, 0.14),
    0 0 12px rgba(20, 184, 166, 0.24),
    0 6px 12px rgba(15, 159, 134, 0.14);
}

.phase-step.passed .phase-step-index {
  border-color: rgba(231, 255, 250, 0.96);
  background: linear-gradient(145deg, #49cdbd 0%, #14a98f 100%);
  color: #ffffff;
  box-shadow: 0 5px 12px rgba(20, 184, 166, 0.14);
}

.phase-step strong {
  display: block;
  color: #111f35;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1.2;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.phase-step small {
  display: block;
  margin-top: 3px;
  color: #607187;
  font-size: 11px;
  line-height: 1.15;
  white-space: nowrap;
}

.phase-step.active strong,
.phase-step.active small {
  color: #089981;
}

.phase-step.active::after {
  content: "";
  position: absolute;
  bottom: 0;
  width: 58px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, #0fa88d, #16b39b);
  box-shadow: 0 3px 8px rgba(16, 163, 139, 0.14);
}

.phase-connector {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  min-width: 0;
  height: 32px;
  pointer-events: none;
  transform: translateY(1px);
}

.phase-connector::before {
  content: "";
  position: absolute;
  top: 15px;
  left: 0;
  right: 0;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(196, 210, 226, 0.18), #cbd8e6 42%, rgba(196, 210, 226, 0.14));
}

.phase-connector::after {
  content: "»»";
  position: absolute;
  top: 4px;
  left: 50%;
  color: #a9bad0;
  font-family: Arial, sans-serif;
  font-size: 21px;
  font-weight: 900;
  letter-spacing: -6px;
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

.phase-connector.advancing::after {
  animation: arrow-pulse 1.2s ease-in-out infinite;
}

@keyframes arrow-pulse {
  0%,
  100% {
    opacity: 0.72;
    transform: translateX(-50%) scale(0.96);
    filter: drop-shadow(0 0 2px rgba(45, 212, 191, 0.2));
  }

  45% {
    opacity: 1;
    transform: translateX(calc(-50% + 4px)) scale(1.08);
    filter: drop-shadow(0 0 8px rgba(45, 212, 191, 0.68));
  }
}

@media (prefers-reduced-motion: reduce) {
  .phase-connector.advancing::after {
    animation: none;
  }
}

@media (max-width: 1280px) {
  .phase-progress-card {
    padding: 9px 18px 8px;
  }

  .phase-progress-track {
    min-width: 880px;
  }
}

@media (max-width: 720px) {
  .phase-progress-card {
    width: calc(100% - 24px);
    margin: 8px 12px 0;
    padding: 9px 12px 8px;
    border-radius: 10px;
  }

  .phase-progress-track {
    min-width: 860px;
  }
}
</style>
