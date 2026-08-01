<template>
  <main class="auth-layout">
    <div class="auth-theme"><ThemeToggle /></div>
    <RouterView />
    <ToastHost />
  </main>
</template>

<script setup lang="ts">
import ToastHost from '@/components/ToastHost.vue';
import ThemeToggle from '@/components/ThemeToggle.vue';
</script>

<style scoped lang="scss">
.auth-layout {
  min-height: 100vh;
}

.auth-theme {
  position: fixed;
  z-index: 500;
  top: 20px;
  right: 24px;
}
</style>
