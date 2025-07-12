<template>
  <div>
    <h1 class="mx-32 mt-16 mb-8 text-2xl font-bold">Welcome to the Image Pair Finder!</h1>

    <section class="mx-32 text-sm/8 text-justify">
      <p>
        This tool explores the hypothesis that humans perceive streetscapes differently depending on their location. For example, the way you perceive a road from the sidewalk is very different from how it appears in the middle of the street — yet many image datasets (like Google Street View) place the camera where people wouldn’t normally stand.
      </p>
      <p>
        The goal of this frontend is to help users find <strong>image pairs</strong> taken from different, but spatially close, viewpoints. These images must be within a specified buffer range and have a similar viewing direction (heading difference ≤ 45°). The generated plot helps you visualize the query logic: the <strong>white slice area</strong> represents the only possible area where a red candidate image can be located relative to the reference.
      </p>
      <p>
        You can then decide whether to use a suggested image pair. All data comes from the <a href="https://github.com/ualsg/global-streetscapes" target="_blank"> <u>Global Streetscapes dataset</u></a>, with images sourced from Mapillary.
      </p>
    </section>

    <p class="mx-32 mt-8 mb-8 text-m/8 text-justify"> Enter the distance for the distance range (in meters):</p>

    <form class="mx-32" @submit.prevent="generatePlot">
      <input v-model="inner" type="text" placeholder="Inner Circle" class="border border-gray-300 rounded w-32 mr-4 text-center"/>
      <input v-model="outer" type="text" placeholder="Outer Circle" class="border border-gray-300 rounded w-32 mr-4 text-center"/>
      <button type="submit" class="border border-gray-300 hover:bg-teal-700 font-semibold rounded shadow w-20 text-center">Plot</button>
    </form>

    <div v-if="image" class="plot-section mx-32 mt-8 w-[400px] object-cover">
        <img :src="image" alt="Plot"/>
        <button @click="$router.push('/map')">Continue to Map</button>
    </div>

  </div>
</template>

<script>
export default {
  data() {
    return {
      inner: null,
      outer: null,
      image: null
    };
  },
  methods: {
    async generatePlot() {
      const response = await fetch("http://localhost:8000/plot-slice/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          inner_buffer: parseFloat(this.inner),
          outer_buffer: parseFloat(this.outer)
        })
      });

      const data = await response.json();
      this.image = data.image;
    }
  }
};
</script>