<template>
    <div id="map" style="height: 600px; width: 100%"></div>
</template>

<script setup>
import { onMounted } from 'vue'
import L from 'leaflet'

onMounted(() => {

    const map = L.map('map').setView([52.520008, 13.404954], 13)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map)

  L.marker([52.52, 13.40]).addTo(map).bindPopup('Berlin!').openPopup()
})
</script>

