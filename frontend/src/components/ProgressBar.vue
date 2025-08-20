<template>
  <div class="wrap" v-if="total && total > 0">
    <div class="label">
      <strong>{{ reviewed }}</strong> / {{ total }} reviewed
      <span v-if="pct >= 0"> ({{ Math.round(pct) }}%)</span>
    </div>
    <div class="bar">
      <div class="fill" :style="{ width: pct + '%' }"></div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ProgressBar',
  props: {
    reviewed: { type: Number, required: true },
    total: { type: Number, required: true }
  },
  computed: {
    pct() {
      if (!this.total) return 0
      return Math.min(100, 100 * (this.reviewed / this.total))
    }
  }
}
</script>

<style scoped>
.wrap { display:flex; flex-direction:column; gap:6px; }
.label { font-size:12px; opacity:.85; }
.bar { height:8px; background:#1d1d1d; border-radius:999px; overflow:hidden; }
.fill { height:100%; background:#1fb6ff; }
</style>