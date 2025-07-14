<template>
  <div>
    <div id="map" style="height: 600px; width: 100%"></div>

    <!-- Modal with blurred background -->
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

const showModal = ref(false)
const imageA = ref('')
const imageB = ref('')

// Setup Leaflet marker icon
const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

const map = ref(null)
const markers = ref([])
const isReady = ref(false)

function clearMarkers() {
  markers.value.forEach(m => {
    if (map.value?.hasLayer(m)) {
      map.value.removeLayer(m)
    }
  })
  markers.value = []
}

function setPairs(locations) {
  if (!isReady.value || !map.value) return

  clearMarkers()

  locations.forEach(pair => {
    const markerA = L.marker([pair.lat_1, pair.lon_1], { icon: DefaultIcon })
      .bindTooltip("Click to view pair", { direction: 'top' })
      .addTo(map.value)

    markerA.on('click', () => {
      imageA.value = `http://localhost:8000/image/${pair.uuid}`
      imageB.value = `http://localhost:8000/image/${pair.relation_uuid}`
      showModal.value = true
    })

    const markerB = L.marker([pair.lat_2, pair.lon_2], { icon: DefaultIcon })
      .addTo(map.value)

    const line = L.polyline(
      [
        [pair.lat_1, pair.lon_1],
        [pair.lat_2, pair.lon_2]
      ],
      { weight: 2 }
    ).addTo(map.value)

    markers.value.push(markerA, markerB, line)
  })

  const bounds = L.latLngBounds(
    locations.flatMap(pair => [
      [pair.lat_1, pair.lon_1],
      [pair.lat_2, pair.lon_2]
    ])
  )
  map.value.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 })
}

onMounted(() => {
  nextTick(() => {
    const container = document.getElementById('map')
    if (!container) {
      console.error("Map container not found")
      return
    }

    map.value = L.map('map').setView([52.52, 13.4], 13)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map.value)

    isReady.value = true

    setTimeout(() => {
      map.value.invalidateSize()
    }, 300)
  })
})

defineExpose({
  setPairs
})
</script>