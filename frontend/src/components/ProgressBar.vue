<template>
  <div class="px-6 rounded-lg wrap" v-if="total && total > 0">
    <div class="label">
      <strong>{{ rated }}</strong> / {{ total }} rated
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
    userId: { type: String, required: true },
    pollInterval: { type: Number, default: 5000 } // ms
  },
  data() {
    return {
      rated: 0,
      total: 0,
      timer: null
    }
  },
  computed: {
    pct() {
      if (!this.total) return 0;
      return Math.min(100, 100 * (this.rated / this.total));
    }
  },
  methods: {
    async fetchProgress() {
      try {
        // Use full URL to API server, not relative URL
        const res = await fetch(`http://localhost:8000/progress?user_id=${this.userId}`);
        
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          const text = await res.text();
          console.error('Non-JSON response:', text.substring(0, 200));
          throw new Error('Server returned non-JSON response');
        }
        
        const data = await res.json();
        this.rated = data.rated || 0;
        this.total = data.total || 0;
        
      } catch (err) {
        console.error("Failed to fetch progress:", err);
        // Set defaults on error to prevent UI issues
        this.rated = 0;
        this.total = 0;
      }
    }
  },
  mounted() {
    this.fetchProgress();
    this.timer = setInterval(this.fetchProgress, this.pollInterval);
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer);
  }
}
</script>

<style scoped>
.wrap { display: flex; flex-direction: column; gap: 6px; }
.label { font-size: 12px; opacity: .85; }
.bar { height: 8px; background: #1d1d1d; border-radius: 999px; overflow: hidden; }
.fill { height: 100%; background: #1fb6ff; transition: width 0.3s; }
</style>