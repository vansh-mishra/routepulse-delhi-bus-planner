(() => {
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  const label = button?.querySelector('.theme-toggle-label');
  const icon = button?.querySelector('.theme-toggle-icon');

  function applyTheme(theme, persist = true) {
    const safeTheme = theme === 'dark' ? 'dark' : 'light';
    root.dataset.theme = safeTheme;
    if (persist) {
      try { localStorage.setItem('routepulse-theme', safeTheme); } catch (_) { /* Storage may be disabled. */ }
    }
    const isDark = safeTheme === 'dark';
    if (button) {
      button.setAttribute('aria-pressed', String(isDark));
      button.setAttribute('aria-label', isDark ? 'Switch to light theme' : 'Switch to dark theme');
      button.title = isDark ? 'Switch to light theme' : 'Switch to dark theme';
    }
    if (label) label.textContent = isDark ? 'Light' : 'Dark';
    if (icon) icon.textContent = isDark ? '☀' : '☾';
    if (metaTheme) metaTheme.content = isDark ? '#0b1220' : '#f6f8fc';
    window.dispatchEvent(new CustomEvent('routepulse:themechange', { detail: { theme: safeTheme } }));
  }

  applyTheme(root.dataset.theme || 'light', false);
  button?.addEventListener('click', () => {
    applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
  });
})();
