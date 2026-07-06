<template>
  <el-card class="panel" shadow="never">
    <div class="panel-title"><h2>方案决策与收敛</h2><el-tag type="info">第三阶段增强</el-tag></div>
    <el-steps :active="1" align-center>
      <el-step title="候选方案登记" />
      <el-step title="投资与约束校核" />
      <el-step title="多角色评价" />
      <el-step title="推荐与冻结" />
    </el-steps>
  </el-card>
</template>

