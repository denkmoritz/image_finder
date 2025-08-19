<template>
  <div>
    <section class="mx-32 mt-16 mb-8 text-sm leading-8 text-justify">
      <p>
        This is the actual querying part. Please enter the desired range for the circles, e.g., 7 - 12 m is reasonable.
      </p>
    </section>

    <p class="mx-32 mt-8 mb-8 text-m leading-8 text-justify">
      Enter the distance for the desired range (in meters):
    </p>

    <form class="mx-32 mb-8 flex items-center space-x-4" @submit.prevent="runQuery">
      <input v-model="inner" type="text" placeholder="Inner Circle" class="border border-gray-300 rounded w-32 text-center" />
      <input v-model="outer" type="text" placeholder="Outer Circle" class="border border-gray-300 rounded w-32 text-center" />
      <button type="submit" class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-28 text-center">
        Query
      </button>

      <div v-if="count !== null" class="text-sm/8">
        {{ count }} pairs found for {{ inner }} - {{ outer }} m
      </div>
    </form>

    <div class="mx-32 mb-8 flex items-center space-x-4">
      <span class="text-m">Get first 10 image pairs</span>
      <button @click="downloadPairs" class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-28 text-center">
        Download
      </button>
    </div>

    <!-- GALLERY first -->
    <div class="mx-32 mb-10">
      <ImagePairGallery
        v-if="pairs.length"
        :pairs="pairs"
        :columns="1"
        :rowHeight="300"
        :gap="128"
        :showControls="true"
        @map="onMapRequest"
      />
      <p v-else class="text-sm text-gray-500">No pairs yet — run “Download”.</p>
    </div>

    <!-- MAP MODAL (centered like Zoom) -->
    <dialog ref="mapDialog" class="map-dialog" @click="onMapBackdrop">
      <div class="map-stage">
        <button @click="closeMap" class="map-close" aria-label="Close">×</button>
        <MapView ref="mapView" />
      </div>
    </dialog>
  </div>
</template>

<script>
import ImagePairGallery from '../components/ImagePairGallery.vue'
import MapView from '../components/MapView.vue'

export default {
  name: 'MapPage',
  components: { MapView, ImagePairGallery },
  data() {
    return {
      inner: null,
      outer: null,
      count: null,
      locations: [],
      pairs: [],
      selectedPair: null
    }
  },
  methods: {
    async runQuery() {
      try {
        const inner = parseFloat(this.inner)
        const outer = parseFloat(this.outer)
        const response = await fetch('http://localhost:8000/query/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ inner_buffer: inner, outer_buffer: outer })
        })
        if (!response.ok) throw new Error(`Request failed: ${response.status}`)
        const data = await response.json()
        this.count = data.count
      } catch (err) {
        console.error('Query failed:', err)
      }
    },

    async downloadPairs() {
      try {
        // call exactly what worked in curl:
        const limit = 10; // first 10 pairs
        const response = await fetch(`http://localhost:8000/download/?limit_pairs=${limit}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`Download failed: ${response.status}`);
        const data = await response.json();

        // basic toast/info
        const msg =
          data.message ??
          `Downloaded ${data.downloaded ?? 0}/${data.attempted ?? 0} images to ${data.images_dir ?? 'images/'}`;
        alert(msg);

        // if backend returns locations, render them; else show a hint
        if (Array.isArray(data.locations) && data.locations.length) {
          this.locations = data.locations;
          this.pairs = this.locations.map((p, i) => ({
            id: p.relation_id ?? p.id ?? i,
            left: {
              src: `http://localhost:8000/image/${p.uuid}`,
              alt: 'Left image',
              lat: Number(p.lat_1),
              lng: Number(p.lon_1)
            },
            right: {
              src: `http://localhost:8000/image/${p.relation_uuid}`,
              alt: 'Right image',
              lat: Number(p.lat_2),
              lng: Number(p.lon_2)
            },
            caption: '',
            tags: []
          }));
        } else {
          console.warn('No locations in response. Did the backend include them?');
          this.pairs = [];
        }
      } catch (err) {
        console.error('Download failed:', err);
        alert('Download failed. Check backend logs.');
      }
    },

    // Called from ImagePairGallery @map
    onMapRequest(pair) {
      this.selectedPair = pair
      // open modal (dialog exists because we removed v-if)
      const dlg = this.$refs.mapDialog
      if (dlg && !dlg.open) dlg.showModal()
      // render markers after the dialog is laid out
      this.$nextTick(() => {
        this.$refs.mapView?.showPair?.(pair)
      })
      document.addEventListener('keydown', this.onEsc)
    },

    closeMap() {
      const dlg = this.$refs.mapDialog
      if (dlg?.open) dlg.close()
      this.$refs.mapView?.clear?.()
      this.selectedPair = null
      document.removeEventListener('keydown', this.onEsc)
    },

    onEsc(e) {
      if (e.key === 'Escape') this.closeMap()
    },

    onMapBackdrop(e) {
      if (e.target === this.$refs.mapDialog) this.closeMap()
    }
  }
}
</script>

<style scoped>
/* Map dialog styling (same approach as lightbox) */
.map-dialog {
  width: min(1200px, 96vw);
  margin: auto;
  padding: 0;
  border: none;
  background: transparent;
}
.map-dialog::backdrop {
  background: rgba(0,0,0,.35);
  backdrop-filter: blur(6px);
}

.map-stage {
  position: relative;
  background: #111;
  padding: 0;
  border-radius: 14px;
  overflow: hidden; /* no white corners */
  width: 100%;
  height: auto; /* adjustable */
}
.map-stage #map {
  width: 100%;
  height: 100%;
}

/* Close button inside panel */
.map-close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255,255,255,0.12);
  color: #fff;
  font-size: 20px;
  line-height: 36px;
  text-align: center;
  cursor: pointer;
  box-shadow: 0 2px 10px rgba(0,0,0,.35);
  backdrop-filter: blur(2px);
  z-index: 10;
}
.map-close:hover { background: rgba(255,255,255,0.18); }
.map-close:focus-visible { outline: 2px solid rgba(255,255,255,0.45); outline-offset: 2px; }
</style>