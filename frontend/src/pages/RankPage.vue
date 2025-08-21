<template>
  <div>
    <!-- Header / query context -->
    <section class="mx-32 mt-10 mb-4 text-sm leading-8 text-justify">
      <p v-if="inner && outer">
        Ranking pairs for <strong>{{ inner }} – {{ outer }} m</strong>
        <span v-if="count !== null" class="opacity-70"> · {{ count }} pairs found</span>
      </p>
      <p v-else class="opacity-80">
        No query parameters detected. You can still browse pairs, or
        <router-link class="underline" :to="{ name: 'query' }">run a query</router-link>.
      </p>
    </section>

    <!-- Controls -->
    <div class="mx-32 mb-2 flex items-center gap-4">
      <label class="text-sm">Pair width:</label>
      <select v-model.number="tileWidth" class="border rounded px-2 py-1 text-sm">
        <option :value="640">640 px</option>
        <option :value="760">760 px</option>
        <option :value="880">880 px</option>
        <option :value="1040">1040 px</option>
      </select>

      <label class="text-sm">Gap:</label>
      <select v-model.number="tileGap" class="border rounded px-2 py-1 text-sm">
        <option :value="16">16</option>
        <option :value="24">24</option>
        <option :value="32">32</option>
        <option :value="48">48</option>
      </select>

      <label class="text-sm">Aspect:</label>
      <select v-model="aspect" class="border rounded px-2 py-1 text-sm">
        <option value="4 / 3">4:3</option>
        <option value="3 / 2">3:2</option>
        <option value="16 / 9">16:9</option>
        <option value="1 / 1">1:1</option>
      </select>
    </div>

    <!-- STICKY progress -->
    <div class="sticky-progress">
      <div class="mx-32">
        <ProgressBar ref="progressBar" :userId="userId" />
      </div>
    </div>

    <!-- Virtualized gallery -->
    <div class="mx-32 mb-10">
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
              <div class="tile-wrap" :class="{ 'vanishing': item.isVanishing }">
                <PairTile
                  :pair="item"
                  :aspect="aspect"
                  @rate="onRate"
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

      tileWidth: 880,
      tileGap: 24,
      aspect: '4 / 3',

      selectedPair: null,
      _queue: [],
      _flushTimer: null,

      // user id for progress API - changed to default
      userId: 'default'
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
          rating: it.rating ?? null,
          seen: !!it.seen,
          starred: !!it.starred,
          isVanishing: false // Add animation state
        }))
        this.items.push(...mapped)
        this.total = data.total ?? this.total
        this.cursor = data.nextCursor ?? null
        this.$nextTick(() => this.$refs.scroller?.forceUpdate?.())
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
        this.queueInteraction({ pairId: item.id, seen: true })
      }
    },

    async onRate({ id, rating }) {
      const idx = this.items.findIndex(p => p.id === id)
      if (idx < 0) return

      // Add vanishing class to trigger animation
      const item = this.items[idx]
      item.isVanishing = true
      
      // Wait for animation to complete before removing
      setTimeout(() => {
        const currentIdx = this.items.findIndex(p => p.id === id)
        if (currentIdx >= 0) {
          this.items.splice(currentIdx, 1)
        }
      }, 500) // Match animation duration

      this.queueInteraction([{ pairId: id, rating, seen: true }])

      // immediately refresh progress bar
      this.$refs.progressBar?.fetchProgress()
    },

    queueInteraction(payload) {
      const arr = Array.isArray(payload) ? payload : [payload]
      this._queue.push(...arr)
      clearTimeout(this._flushTimer)
      this._flushTimer = setTimeout(this.flushInteractions, 400)
    },

    async flushInteractions() {
      if (!this._queue.length) return
      const batch = this._queue.splice(0, this._queue.length)
      try {
        await fetch('http://localhost:8000/interactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(batch)
        })
      } catch (e) {
        this._queue.unshift(...batch)
      }
    },

    onMapRequest(pair) {
      this.selectedPair = pair
      const idx = this.items.findIndex(p => p.id === pair.id)
      if (idx >= 0 && !this.items[idx].seen) {
        this.items[idx] = { ...this.items[idx], seen: true }
        this.queueInteraction({ pairId: pair.id, seen: true })
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
  padding: 0 var(--gap);
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
</style>