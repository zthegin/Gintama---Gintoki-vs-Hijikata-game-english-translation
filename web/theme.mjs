// Unofficial fan project. Use only legally obtained ROMs. See RIGHTS.md.
const root = document.documentElement;
const toggle = document.getElementById('theme-toggle');
const system = window.matchMedia('(prefers-color-scheme: dark)');
const key = 'gintama-theme';

try {
  const saved = localStorage.getItem(key);
  if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;
} catch { /* The toggle still works when browser storage is unavailable. */ }

function isDark() {
  return root.dataset.theme ? root.dataset.theme === 'dark' : system.matches;
}

function render() {
  toggle.setAttribute('aria-pressed', String(isDark()));
}

toggle.addEventListener('click', () => {
  root.dataset.theme = isDark() ? 'light' : 'dark';
  try {
    localStorage.setItem(key, root.dataset.theme);
  } catch { /* Keep the selected theme for this page. */ }
  render();
});
system.addEventListener('change', render);
render();
toggle.hidden = false;
