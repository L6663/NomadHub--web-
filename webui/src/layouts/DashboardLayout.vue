<template>
  <div class="dashboard-layout">
    <AppHeader />
    <AppSidebar />
    <main class="dashboard-main">
      <RouterView />
    </main>
    <ToastHost />
  </div>
</template>

<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue';
import AppSidebar from '@/components/AppSidebar.vue';
import ToastHost from '@/components/ToastHost.vue';

/** 所有业务页面统一使用固定顶栏和侧栏。 */
</script>

<style scoped lang="scss">
.dashboard-main {
  min-height: 100vh;
  padding: calc(var(--nh-header-height) + 22px) 22px 30px calc(var(--nh-sidebar-width) + 22px);
}
</style>
