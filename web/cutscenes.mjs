// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { draftKey } from './drafts.mjs';
import { parseStrictJson } from './text-policy.mjs';
import { checkParts, checkScene, formatScene, readSceneGame, readSceneMessage, sceneId, sceneSuggestion } from './cutscene-codec.mjs';

const $ = (id) => document.getElementById(id);
const state = { scene: null, rows: [], glyphs: null, repository: '', game: null, active: 0, version: 0, gameVersion: 0, drafts: new Map() };
const status = (text, error = false) => {
  $('scene-status').textContent = text;
  $('scene-status').classList.toggle('error', error);
};
const key = (row) => draftKey('gintama-opening', state.scene.source_msb_sha256, sceneId(row));

function working(row) {
  let parts = state.drafts.get(key(row));
  if (!parts) {
    try {
      const raw = localStorage.getItem(key(row));
      if (raw) {
        const draft = parseStrictJson(raw, 20000);
        if (Array.isArray(draft) && draft.length === row.parts.length && draft.every((part) => typeof part === 'string')) parts = draft;
      }
    } catch {}
  }
  return { ...row, parts: [...(parts || row.parts)] };
}

function list() {
  if (!state.scene) return;
  const q = $('scene-search').value.trim().toLowerCase();
  $('scene-entries').replaceChildren();
  let count = 0;
  state.rows.forEach((row, i) => {
    const english = working(row).parts.join('');
    if (q && !`${sceneId(row)} ${english}`.toLowerCase().includes(q)) return;
    const li = document.createElement('li'), button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${sceneId(row)}: ${english.replaceAll('\n', ' ').slice(0, 65) || '(untranslated)'}`;
    button.classList.toggle('active', i === state.active);
    button.addEventListener('click', () => show(i));
    li.append(button);
    $('scene-entries').append(li);
    count++;
  });
  $('scene-count').textContent = `${count} opening entries`;
}

function feedback() {
  const row = state.rows[state.active];
  try {
    checkParts(working(row).parts, row.parts.length);
    $('scene-record-status').textContent = 'English checks passed. The Python build checks bubble width and the fixed message slot.';
    $('scene-record-status').classList.remove('error');
  } catch (error) {
    $('scene-record-status').textContent = error.message;
    $('scene-record-status').classList.add('error');
  }
}

function savePart(index, value) {
  const row = state.rows[state.active], parts = working(row).parts;
  parts[index] = value;
  state.drafts.set(key(row), parts);
  try {
    localStorage.setItem(key(row), JSON.stringify(parts));
  } catch {
    status('Browser storage is unavailable. Download your JSON before closing this tab.', true);
  }
  feedback();
  list();
}

async function show(index) {
  if (!state.scene || index < 0 || index >= state.rows.length) return;
  state.active = index;
  const token = ++state.version, row = state.rows[index], current = working(row);
  $('scene-title').textContent = `Opening entry ${index + 1}`;
  $('scene-id').textContent = sceneId(row);
  $('scene-previous').disabled = index === 0;
  $('scene-next').disabled = index === state.rows.length - 1;
  $('scene-parts').replaceChildren();
  current.parts.forEach((part, i) => {
    const label = document.createElement('label'), strong = document.createElement('strong'), textarea = document.createElement('textarea');
    strong.textContent = `English part ${i + 1}`;
    label.className = 'field-heading';
    label.htmlFor = `scene-part-${i}`;
    label.append(strong);
    textarea.id = `scene-part-${i}`;
    textarea.rows = 3;
    textarea.maxLength = 2500;
    textarea.value = part;
    textarea.addEventListener('input', () => savePart(i, textarea.value));
    $('scene-parts').append(label, textarea);
  });
  $('scene-original').textContent = 'Select your own legally obtained original ROM to read the Japanese here.';
  feedback();
  list();
  if (state.game) {
    try {
      const result = await readSceneMessage(state.game.msb, row, state.glyphs);
      if (token !== state.version) return;
      $('scene-original').textContent = result.parts.map((part, i) => `Part ${i + 1}\n${part}`).join('\n\n');
      if (result.unknown.length) status('Some glyphs could not be decoded. Check the scene in your own game before translating.', true);
    } catch (error) {
      if (token === state.version) status(error.message, true);
    }
  }
}

function exportScene() {
  if (!state.scene) throw new Error('Wait for the opening entries to load.');
  const messages = state.rows.map(working).filter((row) => row.parts.some((part) => part.trim()));
  const originals = new Map(state.rows.map((row) => [row.offset, row]));
  const changes = messages.filter((row) => row.parts.some((part, p) => part !== originals.get(row.offset).parts[p])).length;
  if (!changes) throw new Error('Change the English before exporting an edited scene.');
  return { changes, content: formatScene(state.scene, messages, state.rows) };
}

function download() {
  try {
    const { changes, content } = exportScene();
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url;
    a.download = 'opening_scene.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('scene-export-status').textContent = `${changes} changed entries. Test this JSON with --cutscene before submitting. It contains English and identifiers only.`;
  } catch (error) {
    $('scene-export-status').textContent = error.message;
  }
}

async function copyJson() {
  let exported;
  try {
    exported = exportScene();
  } catch (error) {
    $('scene-export-status').textContent = error.message;
    return;
  }
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard is unavailable.');
    await navigator.clipboard.writeText(exported.content);
    $('scene-export-status').textContent = `${exported.changes} changed entries copied. Paste into a new opening_scene.json file, then test it with --cutscene.`;
  } catch {
    $('scene-export-status').textContent = 'This browser could not copy the JSON. Use Download opening JSON, or allow clipboard access and try again.';
  }
}

function suggest() {
  try {
    if (!state.scene || !state.repository) throw new Error('Wait for the editor to load.');
    const row = state.rows[state.active];
    const body = sceneSuggestion(state.scene, row, working(row).parts);
    const issueUrl = `https://github.com/${state.repository}/issues/new?title=${encodeURIComponent('Opening translation: ' + sceneId(row))}&body=${encodeURIComponent(body)}`;
    window.open(issueUrl, '_blank', 'noopener,noreferrer');
    $('scene-record-status').classList.remove('error');
    $('scene-record-status').textContent = 'Review the English-only issue and submit it on GitHub. A maintainer imports opening suggestions manually. If no tab opened, ';
    const link = document.createElement('a');
    link.href = issueUrl;
    link.rel = 'noreferrer';
    link.textContent = 'open the prepared issue here';
    $('scene-record-status').append(link);
  } catch (error) {
    $('scene-record-status').textContent = error.message;
    $('scene-record-status').classList.add('error');
  }
}

$('scene-rom').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const version = ++state.gameVersion;
  state.version++;
  state.game = null;
  const selectedOffset = state.rows[state.active]?.offset;
  state.rows = state.scene?.messages || [];
  state.active = Math.max(0, state.rows.findIndex((row) => row.offset === selectedOffset));
  $('scene-original').textContent = 'Checking the newly selected file…';
  status('Checking your local original game file…');
  try {
    if (!state.scene) throw new Error('Wait for the opening index to load.');
    if (file.size > 512 * 1024 * 1024) throw new Error('File exceeds the 512 MiB limit.');
    const game = await readSceneGame(new Uint8Array(await file.arrayBuffer()), file.name, state.scene);
    if (version !== state.gameVersion) return;
    state.game = game;
    state.rows = game.rows;
    state.active = Math.max(0, state.rows.findIndex((row) => row.offset === selectedOffset));
    status('Original opening verified. Your game bytes and Japanese stay in this tab.');
    await show(state.active);
  } catch (error) {
    if (version !== state.gameVersion) return;
    status(error.message, true);
    show(state.active);
  }
});
$('scene-search').addEventListener('input', list);
$('scene-previous').addEventListener('click', () => show(state.active - 1));
$('scene-next').addEventListener('click', () => show(state.active + 1));
$('scene-json').addEventListener('click', download);
$('scene-copy-json').addEventListener('click', copyJson);
$('scene-suggest').addEventListener('click', suggest);

try {
  const [scene, glyphs, catalog] = await Promise.all(['assets/opening_scene.json', 'assets/glyphs.json', 'assets/catalog.json'].map(async (url) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Missing site data: ' + url);
    return response.json();
  }));
  state.scene = checkScene(scene);
  state.rows = state.scene.messages;
  state.glyphs = glyphs;
  if (!/^[a-z\d_.-]+\/[a-z\d_.-]+$/i.test(catalog.repository || '')) throw new Error('Invalid contribution repository.');
  state.repository = catalog.repository;
  await show(0);
  status('Edit the opening English here. Select your own legally obtained original game file to see its Japanese.');
} catch (error) {
  status(error.message, true);
}
