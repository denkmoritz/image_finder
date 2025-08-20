<script>
export default {
  name: 'PairTile',
  props: {
    pair: { type: Object, required: true },
    aspect: { type: String, default: '4 / 3' } // NEW: image aspect ratio (W/H)
  },
  emits: ['rate', 'open', 'map'],
  methods: {
    rate(v) { this.$emit('rate', { id: this.pair.id, rating: v }) }
  }
}
</script>

<style scoped>
.pair-tile { display:flex; flex-direction:column; gap:10px; background:#0f0f0f; border-radius:12px; padding:12px; }
.imgs { display:grid; grid-template-columns:1fr 1fr; gap:8px; cursor:zoom-in; }

/* WIDTH is controlled by parent container; HEIGHT derives from aspect-ratio */
.imgs img {
  width: 100%;
  aspect-ratio: var(--img-aspect, 4 / 3);
  object-fit: cover;
  border-radius: 8px;
  background: #222;
}

.meta { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.stars { display:flex; gap:6px; align-items:center; }
.star { border:none; background:transparent; font-size:20px; cursor:pointer; opacity:.55; }
.star.on { opacity:1; }
.clear { margin-left:4px; font-size:12px; opacity:.8; }
.map { border:1px solid #333; padding:4px 8px; border-radius:8px; font-size:12px; }
</style>

<template>
  <div class="pair-tile" :style="{ '--img-aspect': aspect }">
    <div class="imgs" @click="$emit('open', pair)">
      <img :src="pair.left.src" alt="Left image" loading="lazy">
      <img :src="pair.right.src" alt="Right image" loading="lazy">
    </div>

    <div class="meta">
      <div class="stars" role="radiogroup" aria-label="Rate pair">
        <button v-for="s in 5" :key="s" class="star" :class="{ on: (pair.rating ?? 0) >= s }"
                :aria-checked="pair.rating === s" @click.stop="rate(s)" :title="`Rate ${s}`">★</button>
        <button class="clear" @click.stop="rate(null)" title="Clear rating">Clear</button>
      </div>
      <button class="map" @click.stop="$emit('map', pair)">Map</button>
    </div>
  </div>
</template>