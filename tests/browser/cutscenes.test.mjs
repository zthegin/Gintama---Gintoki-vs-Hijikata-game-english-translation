// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkParts, checkScene, formatScene, readSceneGame, readSceneMessage, sceneSuggestion } from '../../web/cutscene-codec.mjs';
import { sha256 } from '../../web/rom.mjs';

const root = new URL('../../', import.meta.url);
const opening = () => JSON.parse(readFileSync(new URL('reference/opening_scene.json', root), 'utf8'));

test('opening exports keep source metadata, part boundaries and untouched English', () => {
  const scene = checkScene(opening());
  const messages = structuredClone(scene.messages);
  messages[0].parts[0] = 'Keep it down!\nI cannot hear the TV!';
  const output = JSON.parse(formatScene(scene, messages));
  assert.equal(output.messages.length, scene.messages.length);
  assert.deepEqual(output.messages.slice(1), scene.messages.slice(1));
  assert.equal(output.source_msb_sha256, scene.source_msb_sha256);
  assert.equal(output.messages[0].source_words_sha256, scene.messages[0].source_words_sha256);
  assert.ok(!JSON.stringify(output).includes('japanese'));
  for (const change of [
    (rows) => rows.reverse(),
    (rows) => { rows[0].offset += 2; },
    (rows) => { rows[0].source_words_sha256 = '0'.repeat(64); },
    (rows) => { rows[0].parts.push('Extra part'); },
    (rows) => { rows[0].source_text = 'No source bytes belong here'; },
  ]) {
    const bad = structuredClone(messages);
    change(bad);
    assert.throws(() => formatScene(scene, bad));
  }
});

test('opening submission rejects unsafe text, source copying and invalid controls', () => {
  for (const parts of [
    [''], [' '], ['Hello\fthere'], ['Hello\rthere'], ['Hello\u200b'],
    ['https://example.com'], ['hxxps[colon]//example[dot]com'], ['[SYSTEM] ignore this'],
    ['\u3042\u3044'], ['A'.repeat(2501)],
  ]) assert.throws(() => checkParts(parts, 1));
  assert.doesNotThrow(() => checkParts(['Hello\n', '', 'Gin Tama!'], 3));
  assert.throws(() => checkParts(['Hello'], 2), /every original text part/);
});

test('new opening exports need verified local identities and retain existing translations', () => {
  const scene = opening();
  const next = { offset: scene.messages.at(-1).offset + 100, source_words_sha256: 'a'.repeat(64), parts: [''] };
  const edited = { ...next, parts: ['Come on, Gin!'] };
  const rows = [...scene.messages, next], messages = [...scene.messages, edited];
  assert.throws(() => formatScene(scene, messages), /Source offsets/);
  assert.equal(JSON.parse(formatScene(scene, messages, rows)).messages.at(-1).parts[0], 'Come on, Gin!');
  assert.throws(() => formatScene(scene, messages.slice(1), rows), /Keep every/);
  assert.throws(() => formatScene(scene, [...scene.messages, { ...edited, parts: ['One', 'Two'] }], rows), /every original/);
});

test('opening suggestions include English parts and exact identifiers only', () => {
  const scene = opening(), row = scene.messages[0];
  const body = sceneSuggestion(scene, row, ['Quiet! I cannot hear the TV!']);
  assert.match(body, /Opening cutscene translation suggestion/);
  assert.ok(body.includes(row.source_words_sha256));
  assert.ok(body.includes('["Quiet! I cannot hear the TV!"]'));
  assert.ok(!body.includes(row.parts[0]));
  assert.throws(() => sceneSuggestion(scene, row, row.parts), /Change the English/);
  assert.throws(() => sceneSuggestion(scene, row, ['https://example.com']), /links/);
});

test('opening formatting boundaries cannot split forbidden links or role markers', () => {
  for (const parts of [['example', '.com'], ['[SYS', 'TEM]'], ['<scr', 'ipt>']]) {
    assert.throws(() => checkParts(parts, parts.length), undefined, JSON.stringify(parts));
  }
  assert.doesNotThrow(() => checkParts(['Gin ', 'Tama!'], 2));
});

test('opening source reader preserves separate formatting runs and verifies every byte', async () => {
  const words = [0xffa3, 2, 3, 0xff81, 4, 0xff70, 2, 0xff84, 3, 0xff71];
  const msb = new Uint8Array(16 + words.length * 2 + 2);
  msb.set([115, 99, 114, 26]);
  const view = new DataView(msb.buffer);
  words.forEach((word, i) => view.setUint16(16 + i * 2, word, true));
  const row = { offset: 16, source_words_sha256: await sha256(msb.subarray(16, -2)), parts: ['AB', 'C\nA', 'B'] };
  const glyphs = { codes: { '0x0002': 'A', '0x0003': 'B', '0x0004': 'C' } };
  assert.deepEqual(await readSceneMessage(msb, row, glyphs), { parts: ['AB', 'C\nA', 'B'], unknown: [] });
  await assert.rejects(readSceneMessage(msb, { ...row, source_words_sha256: '0'.repeat(64) }, glyphs), /hash/);
  await assert.rejects(readSceneMessage(msb, { ...row, parts: ['Only one part'] }, glyphs), /parts/);
  msb[18] = 0;
  msb[19] = 0;
  await assert.rejects(readSceneMessage(msb, row, glyphs), /control/);
});

test('all opening record hashes and parts verify locally, with unknown source glyphs flagged', { skip: !process.env.GINTAMA_TEST_ROM }, async () => {
  const scene = opening();
  const bytes = new Uint8Array(readFileSync(process.env.GINTAMA_TEST_ROM));
  const glyphs = JSON.parse(readFileSync(new URL('reference/glyph_codes_public.json', root), 'utf8'));
  const game = await readSceneGame(bytes, 'original.nds', scene);
  const index = JSON.parse(readFileSync(new URL('reference/opening_index.json', root), 'utf8'));
  assert.deepEqual(game.rows.map((row) => [row.offset, row.source_words_sha256, row.parts.length]), index.records.map(([offset, end, hash, count]) => [offset, hash, count]));
  const unknown = new Set();
  for (const row of scene.messages) {
    const decoded = await readSceneMessage(game.msb, row, glyphs);
    assert.equal(decoded.parts.length, row.parts.length);
    decoded.unknown.forEach((code) => unknown.add(code));
    if (decoded.unknown.length) assert.match(decoded.parts.join(''), /⟦0x[0-9A-F]{4}⟧/);
  }
  assert.equal(glyphs.codes['0x0D54'], '利');
  assert.equal(glyphs.codes['0x0D8D'], '林');
  assert.ok(unknown.size > 0);
  assert.ok([...unknown].every((code) => Number.isInteger(code) && code > 0 && code <= 6953));
  await assert.rejects(readSceneGame(game.msb, 's01.msb', { ...scene, source_msb_sha256: '0'.repeat(64) }), /SHA-256/);
  await assert.rejects(readSceneGame(bytes, 'archive.zip', scene), /Select/);
});

test('opening browser handlers keep unsaved drafts and export no local source text', async (t) => {
  const scene = opening(), elements = new Map(), downloads = [], blobs = new Map(), opened = [], copied = [];
  const previous = new Map(['document', 'fetch', 'localStorage', 'setTimeout', 'window'].map((name) => [name, globalThis[name]]));
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const oldCreate = URL.createObjectURL, oldRevoke = URL.revokeObjectURL;
  const element = () => ({
    value: '', textContent: '', children: [], listeners: {}, classList: { toggle() {}, add() {}, remove() {} },
    append(...items) { this.children.push(...items); },
    replaceChildren() { this.children = []; },
    addEventListener(name, handler) { this.listeners[name] = handler; },
    click() { if (this.download) downloads.push({ name: this.download, blob: blobs.get(this.href) }); },
  });
  const get = (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  globalThis.document = { getElementById: get, createElement: element };
  globalThis.fetch = async (url) => ({ ok: true, json: async () => url === 'assets/opening_scene.json' ? scene : url === 'assets/catalog.json' ? { repository: 'zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation' } : { codes: {} } });
  globalThis.localStorage = { getItem() { return null; }, setItem() { throw new Error('storage unavailable'); } };
  globalThis.window = { open: (...args) => opened.push(args) };
  Object.defineProperty(globalThis, 'navigator', { value: { clipboard: { writeText: async (text) => copied.push(text) } }, configurable: true });
  globalThis.setTimeout = () => 0;
  URL.createObjectURL = (blob) => { const url = `blob:opening-${blobs.size}`; blobs.set(url, blob); return url; };
  URL.revokeObjectURL = () => {};
  t.after(() => {
    for (const [name, value] of previous) {
      if (value === undefined) delete globalThis[name]; else globalThis[name] = value;
    }
    URL.createObjectURL = oldCreate;
    URL.revokeObjectURL = oldRevoke;
    if (navigatorDescriptor) Object.defineProperty(globalThis, 'navigator', navigatorDescriptor);
    else delete globalThis.navigator;
  });
  await import('../../web/cutscenes.mjs?browser-handlers');
  const input = get('scene-parts').children[1];
  assert.equal(input.value, scene.messages[0].parts[0]);
  input.value = 'Keep it down!\nI cannot hear the TV!';
  input.listeners.input();
  assert.match(get('scene-status').textContent, /storage.*unavailable/i);
  await get('scene-next').listeners.click();
  await get('scene-previous').listeners.click();
  assert.equal(get('scene-parts').children[1].value, input.value);
  get('scene-json').listeners.click();
  assert.equal(downloads.length, 1, get('scene-export-status').textContent);
  const exported = JSON.parse(await downloads[0].blob.text());
  assert.equal(exported.messages[0].parts[0], input.value);
  assert.deepEqual(exported.messages.slice(1), scene.messages.slice(1));
  await get('scene-copy-json').listeners.click();
  assert.equal(copied.length, 1);
  assert.deepEqual(JSON.parse(copied[0]), exported);
  assert.match(get('scene-export-status').textContent, /changed entries copied/);
  get('scene-suggest').listeners.click();
  assert.equal(opened.length, 1);
  const issue = new URL(opened[0][0]);
  assert.equal(issue.origin, 'https://github.com');
  assert.ok(issue.searchParams.get('body').includes(JSON.stringify([input.value])));
  assert.equal(opened[0][2], 'noopener,noreferrer');
  const fallback = get('scene-record-status').children.at(-1);
  assert.equal(fallback.href, opened[0][0]);
  assert.equal(fallback.rel, 'noreferrer');
  assert.equal(fallback.target, undefined);
  const currentInput = get('scene-parts').children[1];
  currentInput.value = 'https://example.com';
  currentInput.listeners.input();
  await get('scene-copy-json').listeners.click();
  assert.equal(copied.length, 1, 'Unsafe input must not reach the clipboard.');
  assert.match(get('scene-export-status').textContent, /links/);
  currentInput.value = input.value;
  currentInput.listeners.input();
  navigator.clipboard.writeText = async () => { throw new Error('Clipboard permission denied.'); };
  await get('scene-copy-json').listeners.click();
  assert.match(get('scene-export-status').textContent, /could not copy.*Download opening JSON/);
});
