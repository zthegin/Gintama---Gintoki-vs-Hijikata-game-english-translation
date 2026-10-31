// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';

const hash = 'a'.repeat(64);
const records = () => [
  { id: 'first', source_words_sha256: 'b'.repeat(64), english: 'FIRST', translator_note: null },
  { id: 'second', source_words_sha256: 'c'.repeat(64), english: 'SECOND', translator_note: null },
];

function browser(t, namespace) {
  const previous = new Map(
    ['document', 'fetch', 'localStorage', 'setTimeout', 'window'].map((name) => [name, globalThis[name]]),
  );
  const createObjectURL = URL.createObjectURL,
    revokeObjectURL = URL.revokeObjectURL,
    elements = new Map(),
    downloads = [],
    blobs = new Map(),
    stored = new Map([
      [
        `${namespace}:${hash}:first`,
        JSON.stringify({ english: 'OLD', translator_note: 'Old note.' }),
      ],
    ]);
  let readsBlocked = false;
  const element = () => ({
    value: '',
    textContent: '',
    listeners: {},
    parentElement: { scrollTop: 0 },
    classList: { toggle() {}, add() {}, remove() {} },
    style: {},
    children: [],
    append(...options) {
      this.children.push(...options);
      for (const option of options) this.value ||= option.value || '';
    },
    replaceChildren() {},
    remove() {},
    addEventListener(event, handler) {
      this.listeners[event] = handler;
    },
    click() {
      if (this.download) downloads.push({ name: this.download, blob: blobs.get(this.href) });
    },
    getContext() {
      return {
        clearRect() {},
        createImageData: (width, height) => ({ data: new Uint8ClampedArray(width * height * 4) }),
        putImageData() {},
      };
    },
  });
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  globalThis.document = { getElementById: get, createElement: element, body: element() };
  globalThis.localStorage = {
    getItem(key) {
      if (readsBlocked) throw new Error('Storage is unavailable.');
      return stored.get(key) ?? null;
    },
    setItem() {
      throw new Error('Storage quota exceeded.');
    },
    get length() {
      return stored.size;
    },
    key: (i) => [...stored.keys()][i] ?? null,
  };
  globalThis.setTimeout = () => 0;
  URL.createObjectURL = (blob) => {
    const url = `blob:download-${blobs.size}`;
    blobs.set(url, blob);
    return url;
  };
  URL.revokeObjectURL = () => {};
  t.after(() => {
    for (const [name, value] of previous) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
  });
  get('filter').value = 'all';
  get('image-zoom').value = '4';
  return {
    get,
    downloads,
    stored,
    blockStorageReads() {
      readsBlocked = true;
    },
    input(id, value) {
      get(id).value = value;
      get(id).listeners.input();
    },
    async click(id) {
      await get(id).listeners.click();
      await setImmediate();
    },
  };
}

async function checkExports(page, ids, english) {
  await page.click(ids.json);
  await page.click(ids.csv);
  assert.equal(page.downloads.length, 2, page.get(ids.status).textContent);
  const json = JSON.parse(await page.downloads[0].blob.text());
  assert.equal(json.records[0].english, english);
  assert.equal(json.records[0].translator_note, 'New note.');
  assert.equal(json.records[1].english, 'SECOND');
  const csv = await page.downloads[1].blob.text();
  assert.ok(csv.includes(`first,${'b'.repeat(64)},${english},New note.\n`));
  assert.match(page.downloads[0].name, /\.json$/);
  assert.match(page.downloads[1].name, /\.csv$/);
}

test('dialogue drafts survive failed storage writes, navigation and both exports', async (t) => {
  const page = browser(t, 'gintama-draft');
  const batch = { format: 'gintama-community-translation-v1', batch_id: 'example', records: records() };
  const metadata = batch.records.map((record) => ({
    ...record,
    page_breaks: 0,
    line_breaks: 0,
    decode_status: 'ready',
  }));
  globalThis.fetch = async (url) => ({
    ok: true,
    json: async () => {
      if (url === 'assets/catalog.json')
        return { source_msb_sha256: hash, batches: [{ file: 'example.json', batch: 'Example' }] };
      if (url === 'assets/translations/example.json') return batch;
      if (url === 'assets/metadata/example.json') return metadata;
      return {};
    },
  });
  await import('../../web/app.mjs?failed-storage');
  await setImmediate();
  assert.equal(page.get('english').value, 'OLD');
  page.input('english', 'Fresh English');
  page.input('note', 'New note.');
  assert.match(page.get('record-status').textContent, /storage|tab|browser/i);
  assert.equal(JSON.parse(page.stored.get(`gintama-draft:${hash}:first`)).english, 'OLD');
  page.blockStorageReads();
  await page.click('next');
  assert.equal(page.get('english').value, 'SECOND');
  await page.click('previous');
  assert.equal(page.get('english').value, 'Fresh English');
  assert.equal(page.get('note').value, 'New note.');
  await checkExports(
    page,
    { json: 'download-json', csv: 'download-csv', status: 'export-status' },
    'Fresh English',
  );
});

test('dialogue suggestions keep a visible link when a popup is blocked', async (t) => {
  const page = browser(t, 'gintama-draft');
  const batch = { batch_id: 'example', records: records() };
  const metadata = batch.records.map((record) => ({ ...record, page_breaks: 0, line_breaks: 0 }));
  globalThis.fetch = async (url) => ({
    ok: true,
    json: async () => {
      if (url === 'assets/catalog.json')
        return { repository: 'owner/project', source_msb_sha256: hash, batches: [{ file: 'example.json', batch: 'Example' }] };
      if (url === 'assets/translations/example.json') return batch;
      if (url === 'assets/metadata/example.json') return metadata;
      return {};
    },
  });
  globalThis.window = { open: () => null };
  await import('../../web/app.mjs?blocked-suggestion-popup');
  await setImmediate();
  page.input('english', 'Fresh English.');
  page.input('note', 'Checked locally.');
  await page.click('issue');
  const link = page.get('record-status').children.find((child) => child.href);
  assert.ok(link, 'A blocked popup must not leave the user without a link.');
  const url = new URL(link.href);
  assert.equal(url.origin, 'https://github.com');
  assert.equal(url.pathname, '/owner/project/issues/new');
  assert.equal(url.searchParams.get('title'), 'Translation: first');
  assert.match(url.searchParams.get('body'), /Fresh English\./);
  assert.equal(link.textContent, 'Open the prepared suggestion.');
});

test('image drafts survive failed storage writes, navigation and both exports', async (t) => {
  const page = browser(t, 'gintama-image');
  const batch = { format: 'gintama-community-translation-v1', batch_id: 'example', records: records() };
  const catalog = {
    source_rom_sha256: hash,
    entries: batch.records.map((record) => ({
      id: record.id,
      canonical_english: record.english,
      compressed_capacity: 512,
      background: 'original_transparent',
    })),
  };
  const font = JSON.parse(readFileSync(new URL('../../graphics/pixel_font.json', import.meta.url)));
  globalThis.fetch = async (url) => ({
    ok: true,
    json: async () => {
      if (url === 'assets/graphics/catalog.json') return catalog;
      if (url === 'assets/graphics/translations.json') return batch;
      if (url === 'assets/graphics/pixel_font.json') return font;
      throw new Error(`Unexpected fixture request: ${url}`);
    },
  });
  await import('../../web/graphics.mjs?failed-storage');
  assert.equal(page.get('image-text').value, 'OLD');
  page.input('image-text', 'NEW');
  page.input('image-note', 'New note.');
  assert.match(page.get('image-status').textContent, /storage|tab|browser/i);
  assert.equal(JSON.parse(page.stored.get(`gintama-image:${hash}:first`)).english, 'OLD');
  page.blockStorageReads();
  await page.click('image-next');
  assert.equal(page.get('image-text').value, 'SECOND');
  await page.click('image-previous');
  assert.equal(page.get('image-text').value, 'NEW');
  assert.equal(page.get('image-note').value, 'New note.');
  await checkExports(
    page,
    { json: 'image-json', csv: 'image-csv', status: 'image-export-status' },
    'NEW',
  );
});

test('image suggestions open a credited issue route with a popup fallback', async (t) => {
  const page = browser(t, 'gintama-image');
  const batch = { format: 'gintama-community-translation-v1', batch_id: 'example', records: records() };
  const catalog = {
    source_rom_sha256: hash,
    entries: batch.records.map((row) => ({ id: row.id, canonical_english: row.english, compressed_capacity: 512, background: 'original_transparent' })),
  };
  const font = JSON.parse(readFileSync(new URL('../../graphics/pixel_font.json', import.meta.url)));
  globalThis.fetch = async (url) => ({ ok: true, json: async () => {
    if (url === 'assets/catalog.json') return { repository: 'owner/project' };
    if (url === 'assets/graphics/catalog.json') return catalog;
    if (url === 'assets/graphics/translations.json') return batch;
    if (url === 'assets/graphics/pixel_font.json') return font;
    throw new Error('Unexpected fixture request');
  } });
  globalThis.window = { open: () => null };
  await import('../../web/graphics.mjs?issue-suggestion');
  page.input('image-text', 'NEW');
  await page.click('image-suggest');
  const link = page.get('image-export-status').children.find((child) => child.href);
  assert.ok(link, page.get('image-export-status').textContent);
  const url = new URL(link.href);
  assert.equal(url.pathname, '/owner/project/issues/new');
  assert.match(url.searchParams.get('body'), /ID: first/);
  assert.match(url.searchParams.get('body'), /English \(JSON escaped\):\n"NEW"/);
  assert.ok(!url.searchParams.get('body').includes('Original pixels'));
});

test('image controls recover when used before the index finishes loading', async (t) => {
  const page = browser(t, 'gintama-image');
  const batch = { batch_id: 'example', records: records() };
  const catalog = {
    source_rom_sha256: hash,
    entries: batch.records.map((record) => ({
      id: record.id,
      canonical_english: record.english,
      compressed_capacity: 512,
      background: 'original_transparent',
    })),
  };
  const font = JSON.parse(readFileSync(new URL('../../graphics/pixel_font.json', import.meta.url)));
  let finishLoading, started;
  const loading = new Promise((resolve) => {
    finishLoading = resolve;
  });
  const requested = new Promise((resolve) => {
    started = resolve;
  });
  globalThis.fetch = async (url) => {
    started();
    await loading;
    return {
      ok: true,
      json: async () => {
        if (url === 'assets/graphics/catalog.json') return catalog;
        if (url === 'assets/graphics/translations.json') return batch;
        if (url === 'assets/graphics/pixel_font.json') return font;
        throw new Error(`Unexpected fixture request: ${url}`);
      },
    };
  };
  const starting = import('../../web/graphics.mjs?early-controls');
  await requested;
  try {
    await assert.doesNotReject(page.click('image-next'));
    await assert.doesNotReject(
      page.get('image-rom').listeners.change({
        target: {
          files: [{ name: 'original.nds', size: 0, arrayBuffer: async () => new ArrayBuffer(0) }],
        },
      }),
    );
    assert.equal(page.get('image-status').textContent, 'Wait for the image index to load.');
  } finally {
    finishLoading();
    await starting;
  }
  assert.equal(page.get('image-title').textContent, 'FIRST');
  await page.click('image-next');
  assert.equal(page.get('image-title').textContent, 'SECOND');
});

test('dialogue downloads wait for every page to have text and recover after correction', async (t) => {
  const page = browser(t, 'gintama-draft');
  const batch = { batch_id: 'example', records: records() };
  const metadata = batch.records.map((record) => ({
    ...record,
    page_breaks: 1,
    line_breaks: 0,
    decode_status: 'ready',
  }));
  globalThis.fetch = async (url) => ({
    ok: true,
    json: async () => {
      if (url === 'assets/catalog.json')
        return { source_msb_sha256: hash, batches: [{ file: 'example.json', batch: 'Example' }] };
      if (url === 'assets/translations/example.json') return batch;
      if (url === 'assets/metadata/example.json') return metadata;
      return {};
    },
  });
  await import('../../web/app.mjs?empty-page');
  await setImmediate();
  page.input('english', 'Hello.\\f');
  await page.click('download-json');
  await page.click('download-csv');
  assert.equal(page.downloads.length, 0);
  assert.match(page.get('export-status').textContent, /page is empty/);
  page.input('english', 'Hello.\\fNext page.');
  await page.click('download-json');
  await page.click('download-csv');
  assert.equal(page.downloads.length, 2);
  assert.equal(JSON.parse(await page.downloads[0].blob.text()).records[0].english, 'Hello.\fNext page.');
  assert.match(page.get('export-status').textContent, /1 changed English entries/);
});
