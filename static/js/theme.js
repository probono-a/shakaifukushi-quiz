/** テーマ切り替え — head 内でインライン実行してフラッシュを防ぐ */
(function () {
  const KEY = 'quiz-theme';

  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(KEY, theme);
    const btn = document.getElementById('btn-theme');
    if (btn) btn.innerHTML = theme === 'light' ? '🌙' : '☀️';
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
  }

  // ページ読み込み時に即座に適用（FOUC 防止）
  apply(localStorage.getItem(KEY) || 'dark');

  window.toggleTheme = function () {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    apply(cur === 'dark' ? 'light' : 'dark');
  };

  // DOM 構築後にボタンアイコンを同期
  document.addEventListener('DOMContentLoaded', () => {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    const btn = document.getElementById('btn-theme');
    if (btn) btn.innerHTML = cur === 'light' ? '🌙' : '☀️';
  });
})();
