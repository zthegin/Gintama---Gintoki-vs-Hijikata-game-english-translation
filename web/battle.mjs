// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { draftKey } from './drafts.mjs';
import { parseStrictJson } from './text-policy.mjs';
import { checkParts, readSceneMessage } from './cutscene-codec.mjs';
import { battleId, checkBattle, readBattleGame, formatBattle, battleSuggestion } from './battle-codec.mjs';

const $ = (id) => document.getElementById(id);
const state = { pack: null, script: null, glyphs: null, repository: '', file: null, game: null, rows: [], active: 0, version: 0, drafts: new Map() };
const status = (text, error = false) => { $('battle-status').textContent = text; $('battle-status').classList.toggle('error', error); };
const key = (row) => draftKey('gintama-battle', state.script.source_msb_sha256, battleId(state.script, row));
function working(row) {
  let parts = state.drafts.get(key(row));
  if (!parts) {
    try {
      const raw = localStorage.getItem(key(row));
      if (raw) {
        const value = parseStrictJson(raw, 20000);
        if (Array.isArray(value) && value.length === row.parts.length && value.every((p) => typeof p === 'string')) parts = value;
      }
    } catch { /* Downloads still work when browser storage is blocked. */ }
  }
  return { ...row, parts: [...(parts || row.parts)] };
}
function list() {
  const query = $('battle-search').value.trim().toLowerCase();
  $('battle-entries').replaceChildren();
  let count = 0;
  state.rows.forEach((row, i) => {
    const text = working(row).parts.join('').replaceAll('\n', ' ');
    if (query && !`${battleId(state.script, row)} ${text}`.toLowerCase().includes(query)) return;
    const li = document.createElement('li'), button = document.createElement('button');
    button.type = 'button'; button.textContent = `${i + 1}. ${text || '(untranslated)'}`.slice(0, 85);
    button.classList.toggle('active', i === state.active);
    button.addEventListener('click', () => show(i)); li.append(button); $('battle-entries').append(li); count++;
  });
  $('battle-count').textContent = `${count} editable records${state.game ? `; ${state.game.unsupported} unsupported records left unchanged` : '; load your ROM to see untranslated records'}`;
}
function feedback() {
  const row = state.rows[state.active];
  if (!row) return;
  try {
    checkParts(working(row).parts, row.parts.length);
    $('battle-record-status').textContent = 'English checks passed. Build locally to check width and the fixed slot.';
    $('battle-record-status').classList.remove('error');
  } catch (e) { $('battle-record-status').textContent = e.message; $('battle-record-status').classList.add('error'); }
}
async function show(index) {
  if (!state.rows[index]) return;
  state.active = index;
  const version = ++state.version, row = state.rows[index];
  $('battle-id').textContent = battleId(state.script, row);
  $('battle-previous').disabled = index === 0; $('battle-next').disabled = index === state.rows.length - 1;
  $('battle-parts').replaceChildren();
  working(row).parts.forEach((part, i) => {
    const label = document.createElement('label'), input = document.createElement('textarea');
    label.textContent = `English part ${i + 1}`; label.htmlFor = `battle-part-${i}`;
    input.id = label.htmlFor; input.rows = 3; input.maxLength = 2500; input.value = part;
    input.addEventListener('input', () => {
      const parts = working(row).parts; parts[i] = input.value; state.drafts.set(key(row), parts);
      try { localStorage.setItem(key(row), JSON.stringify(parts)); }
      catch { status('Browser storage is unavailable. Download your JSON before leaving.', true); }
      feedback(); list();
    });
    $('battle-parts').append(label, input);
  });
  $('battle-original').textContent = 'Select your own legally obtained original ROM to read the Japanese here.';
  feedback(); list();
  if (state.game) {
    try {
      const source = await readSceneMessage(state.game.msb, row, state.glyphs, { minimumOffset: 4 });
      if (version !== state.version) return;
      $('battle-original').textContent = source.parts.map((p, i) => `Part ${i + 1}\n${p}`).join('\n\n');
      if (source.unknown.length) status('Some source glyphs are unknown. Check this line in your own game before translating.', true);
    } catch (e) { if (version === state.version) status(e.message, true); }
  }
}
async function selectScript() {
  if (!state.pack) return;
  ++state.version;
  state.script = state.pack.scripts[Number($('battle-script').value)];
  state.game = null; state.rows = state.script.messages; state.active = 0;
  $('battle-parts').replaceChildren(); $('battle-original').textContent = ''; $('battle-id').textContent = '';
  list();
  if (state.rows.length) await show(0);
  if (!state.file) { status('Choose a battle script. Load your own ROM to translate a new record.'); return; }
  const token = state.version;
  status('Verifying the selected battle script locally...');
  try {
    const game = await readBattleGame(state.file.bytes, state.file.name, state.script);
    if (token !== state.version) return;
    state.game = game; state.rows = game.rows;
    status('Original battle script verified. Game bytes and Japanese stay in this tab.');
    await show(0);
  } catch (e) { if (token === state.version) status(e.message, true); }
}
function exportText() {
  if (!state.script) throw new Error('Wait for the battle catalog.');
  const messages = state.rows.map(working).filter((row) => row.parts.some((p) => p.trim()));
  const changes = messages.filter((row) => row.parts.some((p, i) => p !== state.rows.find((r) => r.offset === row.offset).parts[i])).length;
  if (!changes) throw new Error('Change or add English before exporting.');
  return formatBattle(state.pack, state.script, messages, state.rows);
}
$('battle-json').addEventListener('click', () => {
  try {
    const blob = new Blob([exportText()], { type: 'application/json;charset=utf-8' }), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = 'battle_translations.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('battle-export-status').textContent = 'Downloaded English-only JSON. Test it with --battle as shown above.';
  } catch (e) { $('battle-export-status').textContent = e.message; }
});
$('battle-suggest').addEventListener('click', () => {
  try {
    const row = state.rows[state.active]; if (!row) throw new Error('Choose a record first.');
    const body = battleSuggestion(state.script, row, working(row).parts);
    const url = `https://github.com/${state.repository}/issues/new?title=${encodeURIComponent('Battle translation: ' + battleId(state.script, row))}&body=${encodeURIComponent(body)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
    const link = document.createElement('a'); link.href = url; link.rel = 'noreferrer'; link.textContent = 'open the prepared issue here';
    $('battle-record-status').textContent = 'Review and submit the English-only issue. If no tab opened, '; $('battle-record-status').append(link);
  } catch (e) { $('battle-record-status').textContent = e.message; }
});
$('battle-rom').addEventListener('change', async (event) => {
  const file = event.target.files?.[0]; if (!file) return;
  const version = ++state.version;
  state.file = null; state.game = null;
  $('battle-original').textContent = 'Checking the newly selected file...';
  try {
    if (file.size > 512 * 1024 * 1024) throw new Error('File exceeds 512 MiB.');
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (version !== state.version) return;
    state.file = { bytes, name: file.name }; await selectScript();
  } catch (e) { if (version === state.version) status(e.message, true); }
});
$('battle-script').addEventListener('change', selectScript);
$('battle-search').addEventListener('input', list);
$('battle-previous').addEventListener('click', () => show(state.active - 1));
$('battle-next').addEventListener('click', () => show(state.active + 1));
try {
  const [pack, glyphs, catalog] = await Promise.all(['assets/battle.json', 'assets/glyphs.json', 'assets/catalog.json'].map(async (url) => {
    const response = await fetch(url); if (!response.ok) throw new Error('Missing site data: ' + url); return response.json();
  }));
  state.pack = checkBattle(pack); state.glyphs = glyphs;
  if (!/^[a-z\d_.-]+\/[a-z\d_.-]+$/i.test(catalog.repository || '')) throw new Error('Invalid contribution repository.');
  state.repository = catalog.repository;
  pack.scripts.forEach((script, i) => {
    const option = document.createElement('option'); option.value = String(i);
    option.textContent = `${script.script.slice(14, -4)} (${script.messages.length}/${script.record_count})`;
    $('battle-script').append(option);
  });
  $('battle-script').value = String(pack.scripts.findIndex((s) => s.script === 'battle/script/character/gintoki.msb'));
  await selectScript();
} catch (e) { status(e.message, true); }
