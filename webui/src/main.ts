import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './styles/tokens.scss';
import './styles/global.scss';
import { initializeTheme } from '@/services/themeService';

/**
 * Web 前端入口。
 *
 * 目前所有设备数据和按钮动作均允许由 Mock 层兜底，便于一般3在其他模块
 * 未完成时独立开发和演示。后续只需替换 services/socketApi.ts 中的接口，
 * 页面组件无需大改。
 */
initializeTheme();
createApp(App).use(createPinia()).use(router).mount('#app');
