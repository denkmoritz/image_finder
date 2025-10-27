<template>
  <div class="page-margins">
    <section>
      <p v-if="inner && outer">
        Ranking pairs for <strong>{{ inner }} – {{ outer }} m</strong>
        <span v-if="count !== null"> · {{ count }} pairs found</span>
      </p>
      <p v-else>No query parameters detected.</p>
    </section>
    
    <div>
      <div v-if="items.length">
        <PairTile
          v-for="item in items"
          :key="item.id"
          :pair="item"
          @like="onLike"
          @map="onMapRequest"
        />
      </div>
      <p v-else>Loading pairs…</p>
      
      <button 
        v-if="cursor && !loading" 
        @click="loadMore"
        class="load-more-btn"
      >
        Load More
      </button>
      <p v-if="loading">Loading...</p>
    </div>
  </div>
</template>

<script>
import PairTile from '../components/PairTile.vue'

const IMAGE_BASE = 'http://localhost:8000/image'

export default {
  name: 'RankPage',
  components: { PairTile },
  data() {
    return {
      inner: this.$route.query.inner ?? null,
      outer: this.$route.query.outer ?? null,
      count: this.$route.query.count ? Number(this.$route.query.count) : null,
      items: [],
      total: null,
      cursor: null,
      loading: false
    }
  },
  created() { 
    this.loadFirst() 
  },
  methods: {
    async loadFirst() {
      this.items = []
      this.total = null
      this.cursor = null
      await this.loadMore()
    },
    async loadMore() {
      if (this.loading) return
      if (this.total !== null && !this.cursor && this.items.length >= this.total) return
      
      this.loading = true
      try {
        const body = { limit: 50 }
        if (this.cursor) body.cursor = this.cursor
        
        const res = await fetch('http://localhost:8000/pairs/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })
        
        if (!res.ok) throw new Error(`/pairs failed: ${res.status}`)
        
        const data = await res.json()
        const mapped = (data.items || []).map(it => ({
          id: it.id,
          left: { src: `${IMAGE_BASE}?uuid=${it.left.uuid}`, alt: '' },
          right: { src: `${IMAGE_BASE}?uuid=${it.right.uuid}`, alt: '' },
          liked: it.liked ?? false,
          seen: false
        }))
        
        this.items.push(...mapped)
        this.total = data.total ?? this.total
        this.cursor = data.nextCursor ?? null
      } finally {
        this.loading = false
      }
    },
    async onLike({ id, liked }) {
      const idx = this.items.findIndex(p => p.id === id)
      if (idx < 0) return
      
      const pair = this.items[idx]
      
      // Optimistic update (Vue 3 style)
      this.items[idx] = { ...pair, liked, seen: true }
      
      // Send to backend
      try {
        const res = await fetch('http://localhost:8000/like/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            id: id,
            liked: liked
          })
        })
        
        if (!res.ok) {
          console.error('Failed to save like:', res.status)
          // Revert on error
          this.items[idx] = { ...pair, liked: !liked, seen: true }
        }
      } catch (err) {
        console.error('Error saving like:', err)
        // Revert on error
        this.items[idx] = { ...pair, liked: !liked, seen: true }
      }
    },
    onMapRequest(pair) {
      console.log('Map requested for pair', pair)
    }
  }
}
</script>

<style scoped>
.load-more-btn {
  display: block;
  margin: 20px auto;
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
.load-more-btn:hover {
  background: #0056b3;
}
</style>