<template>
  <div>
    <section class="mx-32 mt-16 mb-8 text-sm leading-8 text-justify">
      <p>
        This is the actual querying part. Please enter the desired range for the circles, e.g., 7 - 12 m is reasonable.
      </p>
    </section>
    <p class="mx-32 mt-8 mb-8 text-m leading-8 text-justify"> Enter the distance for the desired range (in meters):</p>

    <form class="mx-32 mb-8 flex items-center space-x-4" @submit.prevent="runQuery">
      <input
        v-model="inner"
        type="text"
        placeholder="Inner Circle"
        class="border border-gray-300 rounded w-32 text-center"
      />
      <input
        v-model="outer"
        type="text"
        placeholder="Outer Circle"
        class="border border-gray-300 rounded w-32 text-center"
      />
      <button
        type="submit"
        class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-28 text-center"
      >
        Query
      </button>

      <!-- Result next to button -->
      <div v-if="count !== null" class="text-sm/8">
        {{ count }} pairs found for {{ inner }} - {{ outer }} m
      </div>
    </form>

    <div class="mx-32 mb-8 flex items-center space-x-4">
      <span class="text-m">Get first 10 image pairs</span>
      <button
        @click="downloadPairs"
        class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-28 text-center"
      >
        Download
      </button>
    </div>

    <div class="mx-32 mb-16 rounded-md overflow-hidden">
      <MapView ref="mapView" />
    </div>
  </div>
</template>

<script>
import MapView from '../components/MapView.vue';

export default {
  components: {
    MapView
  },
  data() {
    return {
      inner: null,
      outer: null,
      image: null,
      count: null,
      locations: []
    };
  },
  methods: {
    async runQuery() {
      console.log("Query button clicked");

      try {
        const response = await fetch("http://localhost:8000/query/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            inner_buffer: parseFloat(this.inner),
            outer_buffer: parseFloat(this.outer)
          })
        });

        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }

        const data = await response.json();
        console.log("Response:", data);
        this.count = data.count;
      } catch (err) {
        console.error("Query failed:", err);
      }
    },
    async downloadPairs() {
      console.log("Download button clicked");

      try {
        const response = await fetch("http://localhost:8000/download/", {
          method: "POST"
        });

        if (!response.ok) {
          throw new Error(`Download failed: ${response.status}`);
        }

        const data = await response.json();
        console.log("Download response:", data);
        alert(data.message || "Download completed");

        if (data.locations) {
          this.locations = data.locations;
          this.$refs.mapView.setPairs(this.locations);
        }
      } catch (err) {
        console.error("Download failed:", err);
        alert("Download failed. Check backend logs.");
      }
    }
  }
};
</script>