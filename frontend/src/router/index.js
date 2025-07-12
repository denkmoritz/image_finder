import { createRouter, createWebHistory } from 'vue-router';
import WelcomePage from '../pages/WelcomePage.vue';
import MapPage from '../pages/MapPage.vue';

const routes = [
  { path: '/', name: 'WelcomePlot', component: WelcomePage },
  { path: '/map', name: 'Map', component: MapPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;