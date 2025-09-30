<template>
  <div class="page-margins">
    <!-- Header / query context -->
    <section class="mt-10 mb-4 text-sm leading-8 text-justify">
      <p v-if="inner && outer">
        Ranking pairs for <strong>{{ inner }} – {{ outer }} m</strong>
        <span v-if="count !== null" class="opacity-70"> · {{ count }} pairs found</span>
      </p>
      <p v-else class="opacity-80">
        No query parameters detected. You can still browse pairs, or
        <router-link class="underline" :to="{ name: 'query' }">run a query</router-link>.
      </p>
    </section>

    <!-- STICKY progress + end session button -->
    <div class="sticky-progress">
      <div class="progress-container">
        <ProgressBar :rated="ratedCount" :total="totalCount" />

        <button 
          @click="confirmEndSession" 
          :disabled="exporting"
          class="export-btn end-btn"
        >
          {{ exporting ? 'Exporting...' : 'End Session' }}
        </button>
      </div>
    </div>

    <!-- Virtualized gallery -->
    <div class="mb-10">
      <DynamicScroller
        v-if="items.length"
        ref="scroller"
        :items="items"
        :min-item-size="minItemSize"
        key-field="id"
        class="v-list"
        :style="{ '--gap': tileGap + 'px', '--tile-w': tileWidth + 'px' }"
        @scroll-end="onScrollEnd"
      >
        <template #default="{ item }">
          <DynamicScrollerItem :item="item" :active="true">
            <div class="row">
              <div class="tile-wrap">
                <PairTile
                  :pair="item"
                  :aspect="aspect"
                  @like="onLike"
                  @map="onMapRequest"
                  v-observe="visible => onVisible(item, visible)"
                />
              </div>
            </div>
          </DynamicScrollerItem>
        </template>
      </DynamicScroller>

      <p v-else class="text-sm text-gray-500">No pairs yet — load will start automatically.</p>

      <div v-if="loading" class="mt-4 text-sm opacity-70">Loading…</div>
      <div v-else-if="!cursor && items.length && total && items.length >= total" class="mt-4 text-sm opacity-70">
        End of results.
      </div>
    </div>

    <!-- MAP MODAL -->
    <dialog ref="mapDialog" class="map-dialog" @click="onMapBackdrop">
      <div class="map-stage">
        <button @click="closeMap" class="map-close" aria-label="Close">×</button>
        <MapView ref="mapView" />
      </div>
    </dialog>
  </div>
</template>

<script>
import PairTile from '../components/PairTile.vue'
import ProgressBar from '../components/ProgressBar.vue'
import MapView from '../components/MapView.vue'

export default {
  name: 'RankPage',
  components: { MapView, PairTile, ProgressBar },

  directives: {
    observe: {
      mounted(el, binding) {
        const getRoot = () => el.closest('.vue-recycle-scroller') || null
        const cb = (entries) => {
          for (const e of entries) {
            const visible = e.isIntersecting && e.intersectionRatio >= 0.6
            el.__onVisible__ && el.__onVisible__(visible)
          }
        }
        el.__onVisible__ = binding.value
        el.__io__ = new IntersectionObserver(cb, { root: getRoot(), threshold: [0, 0.6, 1] })
        el.__io__.observe(el)
      },
      updated(el, binding) { el.__onVisible__ = binding.value },
      unmounted(el) {
        el.__io__ && el.__io__.disconnect()
        delete el.__io__
        delete el.__onVisible__
      }
    }
  },

  data() {
    return {
      // route-provided context
      inner: this.$route.query.inner ?? null,
      outer: this.$route.query.outer ?? null,
      count: this.$route.query.count ? Number(this.$route.query.count) : null,

      items: [],
      total: null,
      cursor: null,
      loading: false,

      // Fixed display settings
      tileWidth: 1000,
      tileGap: 24,
      aspect: '4 / 3',

      selectedPair: null,
      
      // export state
      ratedCount: 0,
      totalCount: 0,
      exporting: false
    }
  },

  computed: {
    minItemSize() {
      const parts = String(this.aspect).split('/')
      const w = parseFloat(parts[0])
      const h = parseFloat(parts[1])
      const ar = (isFinite(w) && isFinite(h) && h !== 0) ? (w / h) : (4 / 3)
      const imageHeight = (this.tileWidth / 2) / ar
      const chrome = 140
      return Math.round(imageHeight + chrome)
    }
  },

  created() { this.loadFirst() },

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
        const res = await fetch('http://localhost:8000/pairs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })
        if (!res.ok) throw new Error(`/pairs failed: ${res.status}`)
        const data = await res.json()
        const mapped = (data.items || []).map(it => ({
          id: it.id,
          left: it.left,
          right: it.right,
          liked: it.liked ?? false,
          // IMPORTANT: ignore server-provided 'seen' — treat seen only locally
          seen: false
        }))
        this.items.push(...mapped)

        // keep the server total if available
        this.total = data.total ?? this.total
        this.cursor = data.nextCursor ?? null
        this.$nextTick(() => this.$refs.scroller?.forceUpdate?.())

        // initialize / refresh frontend-only progress after loading new items
        this.updateProgress()
      } finally {
        this.loading = false
      }
    },

    onScrollEnd() { if (this.cursor) this.loadMore() },

    onVisible(item, visible) {
      if (!visible) return
      const idx = this.items.findIndex(p => p.id === item.id)
      if (idx >= 0 && !this.items[idx].seen) {
        this.items[idx] = { ...this.items[idx], seen: true }
        this.updateProgress()
      }
    },

    onLike({ id, liked }) {
      const idx = this.items.findIndex(p => p.id === id)
      if (idx < 0) return

      this.items[idx] = { ...this.items[idx], liked, seen: true }
      this.updateProgress()
    },
    updateProgress() {
      // Prefer explicit route-provided count if present (query param),
      // otherwise prefer server total, otherwise fallback to loaded items length
      this.totalCount = this.count ?? this.total ?? this.items.length

      // Only count pairs that were liked *or* locally seen in this session
      this.ratedCount = this.items.filter(p => p.liked || p.seen).length
    },


    async confirmEndSession() {
      const confirmed = confirm(
        `Are you sure you want to end this session?\n\n` +
        `All liked pairs from the current query will be exported to your default download path. After this, the ranking session will close.`
      )
      if (!confirmed) return

      await this.exportSession()
      this.$router.push({ name: 'like' })
    },

    async exportSession() {
      if (this.exporting) return
      this.exporting = true

      try {
        // Collect all liked pairs
        const likes = this.items.filter(p => p.liked)
        if (!likes.length) {
          alert("No liked pairs to export!")
          this.exporting = false
          return
        }

        // Build payload using PlotRequest fields + likes
        const payload = {
          inner_buffer: this.$route.query.inner ?? null,
          outer_buffer: this.$route.query.outer ?? null,
          area: this.$route.query.area ? JSON.parse(this.$route.query.area) : null,
          likes
        }

        // Call backend API
        const res = await fetch("http://localhost:8000/export-likes/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        })

        if (!res.ok) {
          const error = await res.json()
          alert(`Export failed: ${error.detail || 'Unknown error'}`)
          return
        }

        const data = await res.json()
        alert(`Liked pairs successfully exported to server:\n${data.csv_path}`)

      } catch (e) {
        console.error("Export error:", e)
        alert("Failed to export liked pairs.")
      } finally {
        this.exporting = false
      }
    },

    convertToCSV(pairs) {
      const headers = ['pair_id', 'left_image', 'right_image']
      const rows = pairs.map(p => [p.id, p.left?.src, p.right?.src])
      return [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    },

    onMapRequest(pair) {
      this.selectedPair = pair
      const idx = this.items.findIndex(p => p.id === pair.id)
      if (idx >= 0 && !this.items[idx].seen) {
        this.items[idx] = { ...this.items[idx], seen: true }
        this.updateProgress()
      }
      const dlg = this.$refs.mapDialog
      if (dlg && !dlg.open) dlg.showModal()
      this.$nextTick(() => this.$refs.mapView?.showPair?.(pair))
      document.addEventListener('keydown', this.onEsc)
    },

    closeMap() {
      const dlg = this.$refs.mapDialog
      if (dlg?.open) dlg.close()
      this.$refs.mapView?.clear?.()
      this.selectedPair = null
      document.removeEventListener('keydown', this.onEsc)
    },

    onEsc(e) { if (e.key === 'Escape') this.closeMap() },
    onMapBackdrop(e) { if (e.target === this.$refs.mapDialog) this.closeMap() }
  }
}
</script>

<style scoped>
/* Sticky progress: always visible */
.sticky-progress {
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 10px 0 8px;
  background: rgba(12, 22, 32, 0.75);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
  border-bottom: 1px solid rgba(255,255,255,0.07);
}

/* Vanishing animation */
.tile-wrap {
  transition: all 0.5s cubic-bezier(0.4, 0.0, 0.2, 1);
  transform-origin: center;
}

.tile-wrap.vanishing {
  opacity: 0;
  transform: scale(0.95) translateY(-20px);
  pointer-events: none;
}

/* Add subtle hover effect for non-vanishing items */
.tile-wrap:not(.vanishing):hover {
  transform: translateY(-2px);
  transition: transform 0.2s ease;
}

/* Virtualized list layout: one centered tile per row */
.v-list { margin: 0; }
.row { width: 100%; padding: var(--gap) 0; }
.tile-wrap {
  width: var(--tile-w);
  margin: 0 auto;
  box-sizing: border-box;
}

/* Kill the magnifier/hover on images */
.tile-wrap :deep(.imgs) { cursor: default; pointer-events: none; }
.tile-wrap :deep(.map) { pointer-events: auto; }

/* vue-virtual-scroller internal wrapper behaves like block rows */
.v-list :deep(.vue-recycle-scroller__item-view) { display: block; }

/* Map dialog */
.map-dialog {
  width: min(1200px, 96vw);
  margin: auto;
  padding: 0;
  border: none;
  background: transparent;
}
.map-dialog::backdrop { background: rgba(0,0,0,.35); backdrop-filter: blur(6px); }
.map-stage { position: relative; background: #111; padding: 0; border-radius: 14px; overflow: hidden; width: 100%; height: auto; }
.map-stage #map { width: 100%; height: 100%; }
.map-close {
  position: absolute; top: 8px; right: 8px; width: 36px; height: 36px; border-radius: 50%;
  border: none; background: rgba(255,255,255,0.12); color: #fff; font-size: 20px;
  line-height: 36px; text-align: center; cursor: pointer; box-shadow: 0 2px 10px rgba(0,0,0,.35);
  backdrop-filter: blur(2px); z-index: 10;
}
.map-close:hover { background: rgba(255,255,255,0.18); }
.map-close:focus-visible { outline: 2px solid rgba(255,255,255,0.45); outline-offset: 2px; }

.progress-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 12px;
}

.export-btn.end-btn {
  background: #276b8e;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.2s ease;
}

.export-btn.end-btn:hover {
  background: #1d77a4;
}

</style>