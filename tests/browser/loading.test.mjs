// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import { compress } from '../../web/graphics-codec.mjs';

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function page(t) {
  const previous = new Map(
    ['document', 'fetch', 'localStorage'].map((name) => [name, globalThis[name]]),
  );
  const elements = new Map();
  const element = () => ({
    value: '',
    textContent: '',
    listeners: {},
    style: {},
    parentElement: { scrollTop: 0 },
    classList: { toggle() {}, add() {}, remove() {} },
    append(option) {
      this.value ||= option.value || '';
    },
    replaceChildren() {},
    addEventListener(event, handler) {
      this.listeners[event] = handler;
    },
    getContext() {
      return {
        clearRect: () => { this.painted = false; },
        createImageData: (width, height) => ({ data: new Uint8ClampedArray(width * height * 4) }),
        putImageData: () => { this.painted = true; },
      };
    },
  });
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  globalThis.document = { getElementById: get, createElement: element };
  globalThis.localStorage = { getItem: () => null, length: 0 };
  get('filter').value = 'all';
  get('image-zoom').value = '4';
  t.after(() => {
    for (const [name, value] of previous) {
      if (value === undefined) delete globalThis[name];
      else globalThis[name] = value;
    }
  });
  return get;
}

function translation(name, sourceHash = 'b'.repeat(64)) {
  const record = {
    id: name,
    source_words_sha256: sourceHash,
    english: `${name} English`,
    translator_note: null,
  };
  return {
    batch: { batch_id: name, records: [record] },
    metadata: [{ ...record, decode_status: 'ready', page_breaks: 0, line_breaks: 0, offset_hex: '0x10' }],
  };
}

const response = (data) => ({ ok: true, json: async () => data });

test('a slow earlier batch cannot replace the batch selected most recently', async (t) => {
  const get = page(t),
    first = deferred(),
    second = deferred();
  const catalog = {
    source_msb_sha256: 'a'.repeat(64),
    batches: [
      { file: 'first.json', batch: 'First' },
      { file: 'second.json', batch: 'Second' },
    ],
  };
  globalThis.fetch = async (url) => {
    if (url === 'assets/catalog.json') return response(catalog);
    if (url === 'assets/glyphs.json' || url === 'assets/glossary.json') return response({});
    const chosen = url.endsWith('/first.json') ? await first.promise : await second.promise;
    return response(url.includes('/metadata/') ? chosen.metadata : chosen.batch);
  };
  await import('../../web/app.mjs?batch-order');
  await setImmediate();
  get('batch').value = 'second.json';
  get('batch').listeners.change();
  second.resolve(translation('second'));
  await setImmediate();
  assert.equal(get('entry-id').textContent, 'second');
  first.resolve(translation('first'));
  await setImmediate();
  assert.equal(get('batch').value, 'second.json');
  assert.equal(get('entry-id').textContent, 'second');
  assert.equal(get('english').value, 'second English');
});

test('a stale startup batch cannot clear a newer selection error', async (t) => {
  const get = page(t),
    initial = deferred();
  globalThis.fetch = async (url) => {
    if (url === 'assets/catalog.json')
      return response({
        source_msb_sha256: 'a'.repeat(64),
        batches: [
          { file: 'initial.json', batch: 'Initial' },
          { file: 'missing.json', batch: 'Missing' },
        ],
      });
    if (url === 'assets/glyphs.json' || url === 'assets/glossary.json') return response({});
    if (url.endsWith('/missing.json')) return { ok: false };
    const data = await initial.promise;
    return response(url.includes('/metadata/') ? data.metadata : data.batch);
  };
  await import('../../web/app.mjs?stale-startup');
  await setImmediate();
  get('batch').value = 'missing.json';
  get('batch').listeners.change();
  await setImmediate();
  assert.equal(get('status').textContent, 'Cannot read batch files.');
  initial.resolve(translation('initial'));
  await setImmediate();
  assert.equal(get('status').textContent, 'Cannot read batch files.');
});

test('an earlier ROM selection cannot hide the latest file validation error', async (t) => {
  const get = page(t),
    oldFile = deferred();
  const msb = new Uint8Array(22);
  msb.set([115, 99, 114, 26]);
  msb.set([1, 0, 0x71, 0xff, 0, 0], 16);
  const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
  const data = translation('example', sha(msb.subarray(16, 20)));
  globalThis.fetch = async (url) => {
    if (url === 'assets/catalog.json')
      return response({
        source_msb_sha256: sha(msb),
        batches: [{ file: 'example.json', batch: 'Example' }],
      });
    if (url === 'assets/glyphs.json') return response({ codes: { '0x0001': 'A' } });
    if (url === 'assets/glossary.json') return response({});
    return response(url.includes('/metadata/') ? data.metadata : data.batch);
  };
  await import('../../web/app.mjs?rom-order');
  await setImmediate();
  const change = get('rom').listeners.change;
  const pending = change({
    target: {
      files: [{ name: 'original.msb', size: msb.length, arrayBuffer: () => oldFile.promise }],
    },
  });
  await change({
    target: {
      files: [
        { name: 'wrong.msb', size: 2, arrayBuffer: async () => new Uint8Array(2).buffer },
      ],
    },
  });
  const error = get('status').textContent;
  assert.match(error, /Not the expected MSB format/);
  oldFile.resolve(msb.buffer);
  await pending;
  await setImmediate();
  assert.equal(get('status').textContent, error);
  assert.notEqual(get('japanese').textContent, 'A');
});

function delayDigest(t, matches) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  const started = deferred(), resume = deferred();
  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: {
      subtle: {
        async digest(algorithm, bytes) {
          if (matches(bytes)) {
            started.resolve();
            await resume.promise;
          }
          return webcrypto.subtle.digest(algorithm, bytes);
        },
      },
    },
  });
  t.after(() => {
    resume.resolve();
    Object.defineProperty(globalThis, 'crypto', descriptor);
  });
  return { started: started.promise, resume: resume.resolve };
}

test('selecting another file clears dialogue and invalidates a pending source render', { timeout: 10000 }, async (t) => {
  const get = page(t), nextFile = deferred();
  const msb = new Uint8Array(28);
  msb.set([115, 99, 114, 26]);
  msb.set([1, 0, 0x71, 0xff, 0, 0, 2, 0, 0x71, 0xff, 0, 0], 16);
  const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
  const rows = [16, 22].map((offset, i) => ({
    id: `entry-${i}`,
    source_words_sha256: sha(msb.subarray(offset, offset + 4)),
    english: 'English',
    translator_note: null,
  }));
  const metadata = rows.map((row, i) => ({
    ...row, decode_status: 'ready', page_breaks: 0, line_breaks: 0,
    offset_hex: (16 + i * 6).toString(16),
  }));
  globalThis.fetch = async (url) => {
    if (url === 'assets/catalog.json')
      return response({ source_msb_sha256: sha(msb), batches: [{ file: 'test.json', batch: 'Test' }] });
    if (url === 'assets/glyphs.json') return response({ codes: { '0x0001': 'A', '0x0002': 'B' } });
    if (url === 'assets/glossary.json') return response({});
    return response(url.includes('/metadata/') ? metadata : { batch_id: 'test', records: rows });
  };
  const digest = delayDigest(t, (bytes) => bytes.length === 4 && bytes[0] === 2);
  await import('../../web/app.mjs?pending-source-render');
  await setImmediate();
  const change = get('rom').listeners.change;
  await change({ target: { files: [{ name: 'old.msb', size: msb.length, arrayBuffer: async () => msb.buffer }] } });
  assert.equal(get('japanese').textContent, 'A');

  const rendering = get('next').listeners.click();
  await digest.started;
  const replacement = change({ target: { files: [{ name: 'new.msb', size: 2, arrayBuffer: () => nextFile.promise }] } });
  t.after(() => nextFile.resolve(new Uint8Array(2).buffer));
  assert.match(get('japanese').textContent, /Checking/);
  assert.doesNotMatch(get('source-note').textContent, /Verified/);
  digest.resume();
  await rendering;
  assert.match(get('japanese').textContent, /Checking/);

  nextFile.resolve(new Uint8Array(2).buffer);
  await replacement;
  assert.match(get('status').textContent, /Not the expected MSB format/);
  assert.notEqual(get('japanese').textContent, 'B');
});

function imageFixture() {
  const decoded = new Uint8Array(512).fill(0x11);
  const palette = compress(new Uint8Array(32)), image = compress(decoded);
  const container = new Uint8Array(palette.length + image.length);
  container.set(palette);
  container.set(image, palette.length);
  const rom = new Uint8Array(0x300 + container.length), view = new DataView(rom.buffer);
  view.setUint32(0x40, 0x80, true);
  view.setUint32(0x44, 20, true);
  view.setUint32(0x48, 0x100, true);
  view.setUint32(0x4c, 8, true);
  view.setUint32(0x80, 8, true);
  view.setUint16(0x86, 1, true);
  rom.set([10, ...new TextEncoder().encode('labels.bin'), 0], 0x88);
  view.setUint32(0x100, 0x300, true);
  view.setUint32(0x104, rom.length, true);
  rom.set(container, 0x300);
  const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
  const entry = {
    id: 'test', english: 'TEST', translator_note: null,
    canonical_english: 'Test', source_words_sha256: sha(decoded),
    compressed_capacity: image.length, offset: palette.length,
    background: 'original_transparent',
  };
  return {
    rom,
    catalog: {
      source_rom_sha256: sha(rom), source_container: 'labels.bin',
      source_container_sha256: sha(container), palette_offset: 0, entries: [entry],
    },
    batch: { batch_id: 'test', records: [entry] },
  };
}

test('selecting another file clears the image and invalidates a pending source render', { timeout: 10000 }, async (t) => {
  const get = page(t), nextFile = deferred(), { rom, catalog, batch } = imageFixture();
  const font = JSON.parse(readFileSync(new URL('../../graphics/pixel_font.json', import.meta.url)));
  globalThis.fetch = async (url) => response(
    url.endsWith('/catalog.json') ? catalog : url.endsWith('/pixel_font.json') ? font : batch,
  );
  const digest = delayDigest(t, (bytes) => bytes.length === 512);
  await import('../../web/graphics.mjs?pending-source-render');
  const change = get('image-rom').listeners.change;
  const rendering = change({ target: { files: [{ size: rom.length, arrayBuffer: async () => rom.buffer }] } });
  await digest.started;
  get('image-source').painted = true;
  const replacement = change({ target: { files: [{ size: 2, arrayBuffer: () => nextFile.promise }] } });
  t.after(() => nextFile.resolve(new Uint8Array(2).buffer));
  assert.equal(get('image-source').painted, false);
  digest.resume();
  await rendering;
  assert.equal(get('image-source').painted, false);

  nextFile.resolve(new Uint8Array(2).buffer);
  await replacement;
  assert.match(get('image-status').textContent, /ROM SHA-256 does not match/);
  assert.equal(get('image-source').painted, false);
});
