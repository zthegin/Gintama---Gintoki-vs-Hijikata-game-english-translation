// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';

test('batch failures stay visible at startup and after changing the selection', async (t) => {
  const elements = new Map();
  const element = () => ({
    value: '',
    textContent: '',
    listeners: {},
    classList: { toggle() {} },
    append(option) {
      this.value ||= option.value;
    },
    addEventListener(event, handler) {
      this.listeners[event] = handler;
    },
  });
  const originalDocument = globalThis.document;
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.document = originalDocument;
    globalThis.fetch = originalFetch;
  });
  globalThis.document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element,
  };
  let offline = false;
  globalThis.fetch = async (url) => {
    if (offline) throw new Error('Connection lost.');
    const catalog = { batches: [{ file: 'example.json', batch: 'Example', count: 0 }] };
    if (url === 'assets/catalog.json') return { ok: true, json: async () => catalog };
    if (url === 'assets/glyphs.json' || url === 'assets/glossary.json')
      return { ok: true, json: async () => ({}) };
    return { ok: false };
  };
  await import('../../web/app.mjs');
  await setImmediate();
  assert.equal(elements.get('status').textContent, 'Cannot read batch files.');
  offline = true;
  elements.get('batch').listeners.change();
  await setImmediate();
  assert.equal(elements.get('status').textContent, 'Connection lost.');
});
