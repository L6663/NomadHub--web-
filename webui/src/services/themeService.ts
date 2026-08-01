export type ThemeMode = 'dark' | 'light';

export const THEME_KEY = 'nomadhub_theme';

/** 返回当前用户保存的主题。主题只属于浏览器界面偏好，不进入 users.db。 */
export function getInitialTheme(): ThemeMode {
  const saved = localStorage.getItem(THEME_KEY);
  return saved === 'light' || saved === 'dark' ? saved : 'dark';
}

/** 将主题写入 html[data-theme]，所有页面通过 CSS 变量同步切换。 */
export function applyTheme(theme: ThemeMode): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

/** 在 Vue 挂载前调用，避免页面先闪出错误主题。 */
export function initializeTheme(): ThemeMode {
  const theme = getInitialTheme();
  applyTheme(theme);
  return theme;
}
