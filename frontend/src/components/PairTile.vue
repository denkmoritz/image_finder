<script>
export default {
  name: 'PairTile',
  props: {
    pair: { type: Object, required: true },
    aspect: { type: String, default: '4 / 3' }
  },
  emits: ['like', 'open', 'map'],
  methods: {
    toggleLike() {
      this.$emit('like', { id: this.pair.id, liked: !this.pair.liked })
    }
  }
}
</script>

<template>
  <div class="bg-gradient-to-r from-slate-900 to-sky-950 pair-tile" :style="{ '--img-aspect': aspect }">
    <div class="imgs" @click="$emit('open', pair)">
      <img :src="pair.left.src" alt="Left image" loading="lazy" />
      <img :src="pair.right.src" alt="Right image" loading="lazy" />
    </div>

    <div class="meta">
      <button 
        class="like-btn" 
        :class="{ liked: pair.liked }" 
        @click.stop="toggleLike" 
        :title="pair.liked ? 'Unlike' : 'Like'"
      >
        {{ pair.liked ? '❤️ Liked' : '🤍 Like' }}
      </button>

      <button class="map" @click.stop="$emit('map', pair)">Map</button>
    </div>
  </div>
</template>

<style scoped>
.pair-tile { display:flex; flex-direction:column; gap:10px; border-radius:12px; padding:12px; }
.imgs { display:grid; grid-template-columns:1fr 1fr; gap:8px; cursor:zoom-in; }
.imgs img {
  width: 100%;
  aspect-ratio: var(--img-aspect, 4 / 3);
  object-fit: cover;
  border-radius: 8px;
  background: #4d4848;
}

.meta { display:flex; align-items:center; justify-content:space-between; gap:8px; }

.like-btn {
  background: transparent;
  border: 1px solid #555;
  border-radius: 8px;
  padding: 4px 12px;
  cursor: pointer;
  color: #aaa;
  font-size: 14px;
  transition: all 0.2s ease;
}
.like-btn.liked {
  background: #e63946;
  color: white;
  border-color: #e63946;
}
.like-btn:hover { opacity: 0.85; }

.map { border:1px solid #333; padding:4px 8px; border-radius:8px; font-size:12px; }
</style>