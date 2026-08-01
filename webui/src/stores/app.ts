import { defineStore } from 'pinia';
import { applyTheme, getInitialTheme, type ThemeMode } from '@/services/themeService';

export type ToastType = 'info' | 'success' | 'error';
interface ToastItem { id: number; title: string; message: string; type: ToastType; }

/** 全局只保存UI和会话展示状态，不保存设备真值。 */
export const useAppStore = defineStore('app', {
  state: () => ({
    sidebarCollapsed: false,
    currentVehicle: '星辰号 · 7.2米',
    vehicleState: '等待设备链路',
    alertCount: 0,
    theme: getInitialTheme() as ThemeMode,
    user: { name: localStorage.getItem('nomadhub_username') || '管理员', role: localStorage.getItem('nomadhub_role') || 'admin', avatar: 'N' },
    toasts: [] as ToastItem[],
    toastSeed: 1,
  }),
  actions: {
    setUser(username: string, role: string) {
      this.user = { name: username, role: role === 'admin' ? '管理员' : '普通用户', avatar: username.slice(0, 1).toUpperCase() || 'N' };
      localStorage.setItem('nomadhub_username', username);
      localStorage.setItem('nomadhub_role', role);
    },
    setTheme(theme: ThemeMode) {
      this.theme = theme;
      applyTheme(theme);
    },
    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark');
    },
    setOnlineState(gateway: boolean, u5: boolean, rct6: boolean) {
      this.vehicleState = gateway ? (u5 ? (rct6 ? '全链路在线' : 'U5在线 · RCT6离线') : '网关在线 · U5离线') : '网关离线';
    },
    pushToast(title: string, message: string, type: ToastType = 'info') {
      const id = this.toastSeed++;
      this.toasts.push({ id, title, message, type });
      window.setTimeout(() => { this.toasts = this.toasts.filter((item) => item.id !== id); }, 3200);
    },
  },
});
