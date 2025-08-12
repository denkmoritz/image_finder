<template>
  <div>
    <div ref="mapEl" style="height: 600px; width: 100%"></div>

    <!-- Modal with blurred background (unchanged UX) -->
    <div
      v-if="showModal"
      class="fixed inset-0 backdrop-blur-sm bg-white/30 flex justify-center items-center text-black"
      style="z-index: 5000;"
    >
      <div class="bg-white p-6 rounded-lg shadow-lg max-w-5xl w-full">
        <h2 class="text-xl font-semibold mb-6 text-center">Image Pair</h2>
        <div class="flex gap-6 justify-center">
          <img :src="imageA" alt="Image A" class="max-w-md rounded border" />
          <img :src="imageB" alt="Image B" class="max-w-md rounded border" />
        </div>
        <div class="flex justify-center mt-6">
          <button
            @click="showModal = false"
            class="px-6 py-2 bg-gray-200 text-black rounded hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

/* ------- Modal state (unchanged) ------- */
const showModal = ref(false)
const imageA = ref('')
const imageB = ref('')

/* ------- Leaflet setup ------- */
const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

const mapEl = ref(null)
const map = ref(null)
const overlays = ref([]) // markers + line

function clear() {
  overlays.value.forEach(layer => {
    if (map.value?.hasLayer(layer)) map.value.removeLayer(layer)
  })
  overlays.value = []
}

/**
 * Accepts either:
 * - Backend shape:
 *   { lat_1, lon_1, lat_2, lon_2, uuid, relation_uuid }
 * - Gallery shape:
 *   { left:{lat,lng,src}, right:{lat,lng,src} }
 */
async function showPair(pair) {
  if (!map.value) return

  // If MapView is toggled from hidden -> visible, ensure layout is measured
  await nextTick()
  setTimeout(() => map.value.invalidateSize(), 0)

  // Normalize coordinates + image URLs
  const lat1 = getNum(pair.left?.lat ?? pair.lat_1)
  const lon1 = getNum(pair.left?.lng ?? pair.lon_1 ?? pair.left?.lon)
  const lat2 = getNum(pair.right?.lat ?? pair.lat_2)
  const lon2 = getNum(pair.right?.lng ?? pair.lon_2 ?? pair.right?.lon)

  if (![lat1, lon1, lat2, lon2].every(n => typeof n === 'number' && !Number.isNaN(n))) {
    console.warn('showPair: missing/invalid lat/lng:', { lat1, lon1, lat2, lon2, pair })
    return
  }

  clear()

  // Markers
  const m1 = L.marker([lat1, lon1]).addTo(map.value).bindPopup('Left image')
  const m2 = L.marker([lat2, lon2]).addTo(map.value).bindPopup('Right image')

  // Optional line connecting them (comment out if you don’t want it)
  const line = L.polyline([[lat1, lon1], [lat2, lon2]], { weight: 2 }).addTo(map.value)

  overlays.value.push(m1, m2, line)

  // Fit bounds
  const bounds = L.latLngBounds([[lat1, lon1], [lat2, lon2]])
  map.value.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 })

  // Wire up modal image sources
  // Backend endpoints
  if (pair.uuid && pair.relation_uuid) {
    imageA.value = `http://localhost:8000/image/${pair.uuid}`
    imageB.value = `http://localhost:8000/image/${pair.relation_uuid}`
  } else {
    // Gallery shape: use provided image sources
    imageA.value = pair.left?.src || ''
    imageB.value = pair.right?.src || ''
  }

  // Click either marker to open modal
  m1.on('click', () => (showModal.value = true))
  m2.on('click', () => (showModal.value = true))
}

// Back-compat: (keep if you still want to show many pairs at once)
function setPairs(locations) {
  if (!map.value || !Array.isArray(locations) || !locations.length) return
  clear()
  const layers = []
  locations.forEach(pair => {
    const lat1 = getNum(pair.lat_1), lon1 = getNum(pair.lon_1)
    const lat2 = getNum(pair.lat_2), lon2 = getNum(pair.lon_2)
    if ([lat1, lon1, lat2, lon2].some(n => Number.isNaN(n))) return

    const m1 = L.marker([lat1, lon1]).addTo(map.value).bindTooltip('Click to view pair', { direction: 'top' })
    m1.on('click', () => {
      imageA.value = `http://localhost:8000/image/${pair.uuid}`
      imageB.value = `http://localhost:8000/image/${pair.relation_uuid}`
      showModal.value = true
    })
    const m2 = L.marker([lat2, lon2]).addTo(map.value)
    const line = L.polyline([[lat1, lon1], [lat2, lon2]], { weight: 2 }).addTo(map.value)
    layers.push(m1, m2, line)
  })
  overlays.value = layers
  const all = locations.flatMap(p => [[p.lat_1, p.lon_1], [p.lat_2, p.lon_2]])
  map.value.fitBounds(L.latLngBounds(all), { padding: [30, 30], maxZoom: 16 })
}

function getNum(x) { const n = Number(x); return Number.isFinite(n) ? n : NaN }

onMounted(() => {
  nextTick(() => {
    if (!mapEl.value) return
    map.value = L.map(mapEl.value).setView([52.52, 13.4], 13)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map.value)

    // In case the parent shows the map after mount
    setTimeout(() => map.value.invalidateSize(), 300)
  })
})

defineExpose({
  showPair,  // add exactly two markers for the selected pair
  clear,     // remove markers/line
  setPairs   // (optional) legacy multi-pair setter
})
</script>

<style>
.leaflet-container { font: inherit; }
</style>