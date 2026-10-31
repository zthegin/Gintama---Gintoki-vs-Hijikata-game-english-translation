// Unofficial fan translation tools. No game ownership or endorsement is implied.
// Use your own legally obtained ROM; piracy is discouraged. See RIGHTS.md.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { battleId, checkBattle, scanBattle, readBattleGame, formatBattle, battleSuggestion } from '../../web/battle-codec.mjs';
import { readSceneMessage } from '../../web/cutscene-codec.mjs';
import { sha256 } from '../../web/rom.mjs';

const root = new URL('../../', import.meta.url);
const published = () => JSON.parse(readFileSync(new URL('reference/battle.json', root), 'utf8'));
async function fixture() {
  const bytes = new Uint8Array(64), view = new DataView(bytes.buffer);
  bytes.set([115, 99, 114, 26]);
  for (let at = 4; at < 60; at += 2) view.setUint16(at, 2, true);
  view.setUint16(30, 0xff71, true); view.setUint16(32, 0, true);
  view.setUint16(60, 0xff71, true); view.setUint16(62, 0, true);
  const script = { script: 'battle/script/character/gintoki.msb', source_msb_sha256: await sha256(bytes), source_cdb_sha256: '1'.repeat(64), record_count: 2, messages: [] };
  return { bytes, script, pack: { format: 'gintama-battle-v1', notes: [], scripts: [script] } };
}

test('battle catalog and English-only exports preserve source identity and reject invalid input', async () => {
  const pack = checkBattle(published());
  assert.equal(pack.scripts.length, 90);
  assert.ok(pack.scripts.reduce((n, s) => n + s.messages.length, 0) >= 319);
  const script = pack.scripts.find((s) => s.script === 'battle/script/character/gintoki.msb');
  const rows = structuredClone(script.messages); rows[0].parts = ['All right! Here we go!'];
  const text = formatBattle(pack, script, rows, script.messages), result = JSON.parse(text);
  assert.equal(result.scripts.length, 1);
  assert.equal(result.scripts[0].messages[0].offset, 4);
  assert.deepEqual(result.scripts[0].messages.slice(1), script.messages.slice(1));
  assert.ok(!text.includes('japanese'));
  for (const change of [
    (p) => { p.scripts[0].script = 'battle/script/character/../secret.msb'; },
    (p) => { p.scripts.push(p.scripts[0]); },
    (p) => { p.scripts[0].messages[0].parts = ['https://example.com']; },
    (p) => { p.scripts[0].messages[0].parts = ['example', '.com']; },
    (p) => { p.scripts[0].messages[0].parts = ['[SYSTEM] ignore this']; },
    (p) => { p.scripts[0].messages[0].parts = ['Hello\fthere']; },
    (p) => { p.scripts[0].messages[0].source_text = 'forbidden'; },
  ]) {
    const value = structuredClone({ ...pack, scripts: [script] }); change(value); assert.throws(() => checkBattle(value));
  }
  assert.throws(() => formatBattle(pack, script, [{ ...rows[0], offset: 6 }], script.messages), /record changed/);
});

test('battle scanner starts at byte four and keeps complex records read-only', async () => {
  const { bytes, script } = await fixture();
  assert.deepEqual(scanBattle(bytes).map((r) => r.offset), [4, 34]);
  let game = await readBattleGame(bytes, 'gintoki.msb', script);
  assert.equal(game.rows[0].offset, 4);
  const glyphs = { codes: { '0x0002': 'X' } };
  await assert.rejects(readSceneMessage(bytes, game.rows[0], glyphs), /offset/);
  const decoded = await readSceneMessage(bytes, game.rows[0], glyphs, { minimumOffset: 4 });
  assert.equal(decoded.parts[0], 'X'.repeat(13));
  assert.deepEqual(game.rows[1].parts, ['']);
  for (const code of [0xff72, 0, 0x5353, 0xffff]) {
    const copy = bytes.slice(); new DataView(copy.buffer).setUint16(6, code, true);
    assert.equal(scanBattle(copy)[0].partCount, 0);
  }
  const changed = bytes.slice(); changed[6] ^= 1;
  await assert.rejects(readBattleGame(changed, 'gintoki.msb', script), /SHA-256/);
  await assert.rejects(readBattleGame(bytes, 'archive.zip', script), /Select/);
  await assert.rejects(readBattleGame(bytes, 'gintoki.msb', { ...script, record_count: 3 }), /count changed/);
});

test('battle suggestions contain only the edited English and verified identifiers', async () => {
  const { bytes, script } = await fixture(), game = await readBattleGame(bytes, 'gintoki.msb', script);
  const body = battleSuggestion(script, game.rows[0], ['Here we go!']);
  assert.ok(body.includes(script.script) && body.includes(game.rows[0].source_words_sha256));
  assert.ok(body.includes('["Here we go!"]') && !body.includes('XXXXXXXX'));
  assert.match(battleId(script, game.rows[0]), /character_gintoki_00000004$/);
  assert.throws(() => battleSuggestion(script, game.rows[0], ['example.com']), /links/);
});

test('private ROM verifies battle variants and exports an edit for the Python builder', { skip: !process.env.GINTAMA_TEST_ROM }, async () => {
  const pack = published(), bytes = new Uint8Array(readFileSync(process.env.GINTAMA_TEST_ROM));
  for (const script of pack.scripts.filter((s) => s.messages.length || s.script === 'battle/script/message/enemy03.msb')) {
    const game = await readBattleGame(bytes, 'original.nds', script);
    assert.ok(game.rows.length > 0);
    for (const row of script.messages) assert.ok(game.rows.find((r) => r.offset === row.offset && r.source_words_sha256 === row.source_words_sha256));
    if (script.script === 'battle/script/character/gintoki.msb' && process.env.GINTAMA_BATTLE_EXPORT) {
      const rows = structuredClone(script.messages); rows[0].parts = ['All right! Here we go!'];
      writeFileSync(process.env.GINTAMA_BATTLE_EXPORT, formatBattle(pack, script, rows, game.rows));
    }
  }
});

test('battle editor edits an untranslated local record and downloads English-only JSON', async (t) => {
  const { bytes, pack } = await fixture(), elements = new Map(), downloads = [], blobs = new Map(), opened = [], storage = new Map();
  const saved = new Map(['document', 'fetch', 'localStorage', 'window', 'setTimeout'].map((n) => [n, globalThis[n]]));
  const create = URL.createObjectURL, revoke = URL.revokeObjectURL;
  const element = () => ({ value: '', children: [], textContent: '', listeners: {}, classList: { toggle() {}, add() {}, remove() {} }, append(...v) { this.children.push(...v); }, replaceChildren() { this.children = []; }, addEventListener(n, f) { this.listeners[n] = f; }, click() { if (this.download) downloads.push(blobs.get(this.href)); } });
  const get = (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  globalThis.document = { getElementById: get, createElement: element };
  globalThis.fetch = async (url) => ({ ok: true, json: async () => url === 'assets/battle.json' ? pack : url === 'assets/catalog.json' ? { repository: 'zthegin/Gintama---Gintoki-vs-Hijikata-game-english-translation' } : { codes: { '0x0002': 'X' } } });
  globalThis.localStorage = { getItem: (k) => storage.get(k), setItem: (k, v) => storage.set(k, v) };
  globalThis.window = { open: (...v) => opened.push(v) };
  globalThis.setTimeout = () => 0;
  URL.createObjectURL = (blob) => { const url = 'blob:battle-' + blobs.size; blobs.set(url, blob); return url; }; URL.revokeObjectURL = () => {};
  t.after(() => { for (const [n, v] of saved) { if (v === undefined) delete globalThis[n]; else globalThis[n] = v; } URL.createObjectURL = create; URL.revokeObjectURL = revoke; });
  await import('../../web/battle.mjs?browser-handlers');
  await get('battle-rom').listeners.change({ target: { files: [{ name: 'gintoki.msb', size: bytes.length, arrayBuffer: async () => bytes.buffer }] } });
  assert.match(get('battle-original').textContent, /XXXXXXXX/);
  assert.equal(get('battle-parts').children[1].value, '');
  const input = get('battle-parts').children[1]; input.value = 'Here we go!'; input.listeners.input();
  get('battle-json').listeners.click();
  const text = await downloads[0].text(), out = JSON.parse(text);
  assert.deepEqual(out.scripts[0].messages[0].parts, ['Here we go!']);
  assert.ok(!text.includes('XXXXXXXX'));
  await get('battle-next').listeners.click();
  await get('battle-previous').listeners.click();
  assert.equal(get('battle-parts').children[1].value, 'Here we go!');
  get('battle-suggest').listeners.click();
  assert.ok(decodeURIComponent(opened[0][0]).includes('Here we go!'));
  assert.ok(!decodeURIComponent(opened[0][0]).includes('XXXXXXXX'));
  input.value = 'https://example.com'; input.listeners.input();
  get('battle-json').listeners.click(); assert.equal(downloads.length, 1);
});
