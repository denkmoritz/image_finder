<template>
  <div class="page-margins">
    <section class="mt-10 mb-4 text-sm leading-8">
      <h1 class="text-2xl font-bold mb-2">Exported Likes</h1>
      <p class="text-gray-200">
        All previously exported like sessions. Click "View Pairs" to explore them.
      </p>
    </section>

    <div v-if="loading" class="text-gray-300 mt-4">Loading…</div>
    <p v-else-if="!likes.length" class="text-gray-300 mt-4">No exported likes found.</p>

    <div v-else class="mt-6 overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-slate-800 text-gray-100">
            <th class="p-2 border border-slate-600">File Name</th>
            <th class="p-2 border border-slate-600">Likes</th>
            <th class="p-2 border border-slate-600">Inner</th>
            <th class="p-2 border border-slate-600">Outer</th>
            <th class="p-2 border border-slate-600">Lat</th>
            <th class="p-2 border border-slate-600">Lng</th>
            <th class="p-2 border border-slate-600">Radius (m)</th>
            <th class="p-2 border border-slate-600">Date</th>
            <th class="p-2 border border-slate-600">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="like in likes" :key="like.file_name" class="hover:bg-slate-600">
            <td class="p-2 border border-slate-600 break-all">{{ like.file_name }}</td>
            <td class="p-2 border border-slate-600">{{ like.like_count }}</td>
            <td class="p-2 border border-slate-600">{{ like.inner_buffer ?? '-' }}</td>
            <td class="p-2 border border-slate-600">{{ like.outer_buffer ?? '-' }}</td>
            <td class="p-2 border border-slate-600">{{ like.lat ?? '-' }}</td>
            <td class="p-2 border border-slate-600">{{ like.lng ?? '-' }}</td>
            <td class="p-2 border border-slate-600">{{ like.radius_m ?? '-' }}</td>
            <td class="p-2 border border-slate-600">{{ formatDate(like.timestamp) }}</td>
            <td class="p-2 border border-slate-600">
              <button
                @click="viewPairs(like.file_name)"
                class="bg-sky-500 hover:bg-sky-600 text-white font-semibold px-3 py-1 rounded"
              >
                View Pairs
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LikePage',
  data() {
    return {
      likes: [],
      loading: false
    }
  },
  created() {
    this.fetchLikes()
  },
  methods: {
    async fetchLikes() {
      this.loading = true
      try {
        const res = await fetch('http://localhost:8000/list-likes/')
        if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`)
        const data = await res.json()
        this.likes = data.likes || []
      } catch (e) {
        console.error('Error fetching likes:', e)
        alert('Failed to load exported likes.')
      } finally {
        this.loading = false
      }
    },
    formatDate(ts) {
      // ts is like "20250929_220537"
      if (!ts) return '-'
      const match = ts.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/)
      if (!match) return ts
      const [_, year, month, day, hour, min, sec] = match
      return `${day}.${month}.${year} ${hour}:${min}:${sec}`
    },
    viewPairs(fileName) {
      // Navigate to the pair view page, passing the file name
      // Assuming your pair view route exists, adjust as needed
      this.$router.push({ name: 'pairView', query: { file: fileName } })
    }
  }
}
</script>

<style scoped>
table {
  border: 1px solid #374151; /* slate-600 */
  border-radius: 6px;
}
th, td {
  text-align: left;
}
button {
  transition: background 0.2s ease;
}
</style>