// Unofficial fan project. Use only legally obtained ROMs. See RIGHTS.md.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

async function page(t, { saved = null, dark = false, blocked = false } = {}) {
  const names = ['document', 'window', 'localStorage'];
  const previous = new Map(names.map((name) => [name, globalThis[name]]));
  const attributes = {}, handlers = {}, values = new Map(saved === null ? [] : [['gintama-theme', saved]]);
  const root = { dataset: {} };
  const button = { hidden: true, setAttribute: (key, value) => { attributes[key] = value; }, addEventListener: (name, handler) => { handlers[name] = handler; } };
  const system = { matches: dark, addEventListener: (name, handler) => { handlers.system = handler; } };
  globalThis.document = { documentElement: root, getElementById: (id) => { assert.equal(id, 'theme-toggle'); return button; } };
  globalThis.window = { matchMedia: (query) => { assert.equal(query, '(prefers-color-scheme: dark)'); return system; } };
  globalThis.localStorage = {
    getItem: (key) => { if (blocked) throw new Error('Storage blocked'); return values.get(key) ?? null; },
    setItem: (key, value) => { if (blocked) throw new Error('Storage blocked'); values.set(key, value); },
  };
  t.after(() => { for (const [name, value] of previous) { if (value === undefined) delete globalThis[name]; else globalThis[name] = value; } });
  await import(`../../web/theme.mjs?${t.name}`);
  return { root, button, attributes, handlers, system, values };
}

test('theme follows the system until the visitor chooses and remembers that choice', async (t) => {
  const p = await page(t);
  assert.equal(p.button.hidden, false);
  assert.equal(p.attributes['aria-pressed'], 'false');
  assert.equal(p.root.dataset.theme, undefined);
  assert.equal(p.values.size, 0);
  p.system.matches = true; p.handlers.system();
  assert.equal(p.attributes['aria-pressed'], 'true');
  p.handlers.click();
  assert.equal(p.root.dataset.theme, 'light');
  assert.equal(p.values.get('gintama-theme'), 'light');
  p.system.matches = false; p.handlers.system();
  p.system.matches = true; p.handlers.system();
  assert.equal(p.attributes['aria-pressed'], 'false');
  p.handlers.click();
  assert.equal(p.root.dataset.theme, 'dark');
  assert.equal(p.attributes['aria-pressed'], 'true');
});

test('saved theme overrides the system on the next page', async (t) => {
  const p = await page(t, { saved: 'dark' });
  assert.equal(p.root.dataset.theme, 'dark');
  assert.equal(p.attributes['aria-pressed'], 'true');
});

test('unrecognized stored theme is ignored', async (t) => {
  const p = await page(t, { saved: '<script>', dark: true });
  assert.equal(p.root.dataset.theme, undefined);
  assert.equal(p.attributes['aria-pressed'], 'true');
});

test('blocked storage does not stop switching themes', async (t) => {
  const p = await page(t, { dark: true, blocked: true });
  p.handlers.click();
  assert.equal(p.root.dataset.theme, 'light');
  assert.equal(p.attributes['aria-pressed'], 'false');
});

test('all seven pages load the local theme script and keep a usable toggle', () => {
  const names = ['index', 'cutscenes', 'battle', 'graphics', 'guide', 'install', 'rights'];
  for (const name of names) {
    const html = readFileSync(new URL(`../../web/${name}.html`, import.meta.url), 'utf8');
    assert.equal((html.match(/id="theme-toggle"/g) || []).length, 1, name);
    assert.match(html, /<script type="module" src="theme\.mjs"><\/script>/);
    assert.match(html, /script-src 'self'/);
    assert.match(html, /id="theme-toggle"[^>]+type="button"[^>]+aria-pressed="false"/);
    assert.ok(!html.includes("'unsafe-inline'"));
  }
});

test('both palettes keep body text, hints, links and errors readable', () => {
  const css = readFileSync(new URL('../../web/style.css', import.meta.url), 'utf8');
  const luminance = (hex) => {
    const expanded = hex.length === 4 ? hex.slice(1).split('').map((c) => c + c).join('') : hex.slice(1);
    return [0.2126, 0.7152, 0.0722].reduce((sum, weight, i) => {
      const c = parseInt(expanded.slice(i * 2, i * 2 + 2), 16) / 255;
      return sum + weight * (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    }, 0);
  };
  for (const selector of [':root', ':root[data-theme="dark"]']) {
    const block = css.slice(css.indexOf(selector + ' {')).split('}')[0];
    const colors = Object.fromEntries([...block.matchAll(/--([a-z-]+): (#[a-f0-9]+);/g)].map((m) => [m[1], luminance(m[2])]));
    const ratio = (a, b) => (Math.max(colors[a], colors[b]) + 0.05) / (Math.min(colors[a], colors[b]) + 0.05);
    for (const foreground of ['text', 'muted', 'link', 'error']) {
      for (const background of ['page', 'surface', 'selected']) assert.ok(ratio(foreground, background) >= 4.5, `${selector}: ${foreground}/${background}`);
    }
    assert.ok(ratio('border', 'page') >= 3, `${selector}: form border`);
    assert.ok(ratio('focus', 'page') >= 3, `${selector}: focus ring`);
  }
});
