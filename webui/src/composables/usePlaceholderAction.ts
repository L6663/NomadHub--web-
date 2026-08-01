import { ref } from 'vue';
import { useAppStore } from '@/stores/app';

/**
 * 所有占位按钮统一经过此函数处理。
 * 当前没有真实接口时按钮仍有加载和反馈；后续接入真实接口时只需替换execute回调。
 */
export function usePlaceholderAction() {
  const loading = ref(false);
  const app = useAppStore();

  async function run(actionName: string, execute?: () => Promise<unknown>) {
    if (loading.value) return;
    loading.value = true;
    try {
      if (execute) {
        await execute();
      } else {
        await new Promise((resolve) => window.setTimeout(resolve, 450));
      }
      app.pushToast('占位操作已执行', `${actionName}：当前使用Mock逻辑，等待真实接口接入。`, 'success');
    } catch (error) {
      app.pushToast('操作失败', error instanceof Error ? error.message : '未知错误', 'error');
    } finally {
      loading.value = false;
    }
  }

  return { loading, run };
}
