import { createRouter, createWebHistory } from 'vue-router';
import AuthLayout from '@/layouts/AuthLayout.vue';
import DashboardLayout from '@/layouts/DashboardLayout.vue';
import { TOKEN_KEY } from '@/services/socketApi';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/',
      component: AuthLayout,
      children: [
        { path: 'login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
        { path: 'register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
      ],
    },
    {
      path: '/',
      component: DashboardLayout,
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'devices', name: 'devices', component: () => import('@/views/DevicesView.vue') },
        { path: 'scenes', name: 'scenes', component: () => import('@/views/ScenesView.vue') },
        { path: 'alerts', name: 'alerts', component: () => import('@/views/AlertsView.vue') },
        { path: 'gateway', name: 'gateway', component: () => import('@/views/GatewayView.vue') },
        { path: 'history', name: 'history', component: () => import('@/views/HistoryView.vue') },
        { path: 'users', name: 'users', component: () => import('@/views/UsersView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
});

/**
 * 简化的路由守卫。
 * 当前Qt与Web共用Bearer Token认证接口；后续启用HTTPS后可将浏览器会话迁移为HttpOnly Cookie。
 */
router.beforeEach((to) => {
  if (to.meta.public) return true;
  return localStorage.getItem(TOKEN_KEY) ? true : { name: 'login' };
});

export default router;
