<template>
  <div class="page-margins">
    <!-- Intro -->
    <section class="mt-16 mb-8 text-m leading-8 text-justify">
      <p>
        Choose a buffer range (e.g., 7 – 12 m). Optionally draw a circle on the map to limit the search area.
        If you don’t draw anything, the entire dataset will be used.
      </p>
    </section>

    <!-- Area picker -->
    <div class="mb-6">
      <AreaPickerMap v-model="area" />
    </div>

    <!-- Query form -->
    <p class="mt-2 mb-4 text-m leading-8 text-justify">
      Distance range (meters):
    </p>

    <form class="mb-6 flex items-center flex-wrap gap-4" @submit.prevent="runQuery">
      <input v-model="inner" type="text" placeholder="Inner Circle" class="border border-gray-300 rounded w-32 mr-4 text-center"/>
      <input v-model="outer" type="text" placeholder="Outer Circle" class="border border-gray-300 rounded w-32 mr-4 text-center"/>

      <button :disabled="loading" type="submit" class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-20 text-center">
        {{ loading ? 'Querying…' : 'Query' }}
      </button>

      <div v-if="count !== null" class="text-sm/8">
        {{ count }} pairs found for {{ inner }} – {{ outer }} m
        <span v-if="area" class="opacity-70">in selected area</span>
        <span v-else class="opacity-70">in full dataset</span>
      </div>
    </form>

    <div>
      <button
        v-if="count !== null && count > 0"
        @click="goRank"
        class="mb-8 border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow px-4 py-2"
      >
        Start ranking
      </button>
      <p v-else-if="count === 0" class="mb-8 text-sm text-gray-500">No pairs for that query — adjust range or area.</p>
    </div>
  </div>
</template>

<script>
import AreaPickerMap from '../components/AreaPickerMap.vue'

export default {
  name: 'QueryPage',
  components: { AreaPickerMap },
  data() {
    return {
      inner: null,
      outer: null,
      area: null,
      count: null,
      loading: false
    }
  },
  methods: {
    async runQuery() {
        this.loading = true
        try {
            const toNumOrNull = (v) => {
            const n = v === '' || v == null ? null : Number(v)
            return Number.isFinite(n) ? n : null
            }

            const payload = {
            inner_buffer: toNumOrNull(this.inner),
            outer_buffer: toNumOrNull(this.outer),
            ...(this.area ? { area: this.area } : {})
            }

            const res = await fetch('http://localhost:8000/query/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
            })
            if (!res.ok) {
            const detail = await res.json().catch(() => ({}))
            console.error('/query failed', res.status, detail)
            throw new Error(`Request failed: ${res.status}`)
            }
            const data = await res.json()
            this.count = data.count ?? null
        } finally {
            this.loading = false
        }
    },
    goRank() {
      this.$router.push({
        name: 'rank',
        query: {
          inner: this.inner,
          outer: this.outer,
          count: this.count,
          // These are just UI context hints; backend has already been primed by /query.
          // Keep them short so URLs stay shareable.
          ...(this.area ? {
            // encode center/radius as strings for display context
            lng: this.area.center[0],
            lat: this.area.center[1],
            r: Math.round(this.area.radius_m)
          } : {})
        }
      })
    }
  }
}
</script>