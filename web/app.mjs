// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { draftKey, readDraft } from './drafts.mjs';
import { translationSuggestion } from './suggestions.mjs';
import { readGameFile, verifyGame, readRecord } from './rom.mjs';
import { checkDialogue, encodeCsv, formatBatch } from './export.mjs';
import { parseStrictJson, stripColors } from './text-policy.mjs';

const $ = (id) => document.getElementById(id);
const state = {
  catalog: null,
  glyphs: null,
  glossary: null,
  game: null,
  batch: null,
  metadata: null,
  entries: [],
  active: -1,
  visible: [],
  repository: '',
  renderVersion: 0,
  batchVersion: 0,
  gameVersion: 0,
  drafts: new Map(),
};
const setStatus = (message, error = false) => {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
};
const asText = (text) => (text || '').replace(/\f/g, '\\f');
const fromText = (text) => text.replace(/\\f/g, '\f');
const keyFor = (entry) => draftKey('gintama-draft', state.catalog.source_msb_sha256, entry.id);
function englishPreview() {
  try {
    $('english-preview').textContent = stripColors(fromText($('english').value)).replace(
      /\f/g, '\n--- page ---\n',
    );
  } catch (error) {
    $('english-preview').textContent = error.message;
  }
}
const save = () => {
  if (state.active < 0) return;
  const entry = state.batch.records[state.active];
  const payload = {
    english: fromText($('english').value) || null,
    translator_note: fromText($('note').value) || null,
  };
  state.drafts.set(keyFor(entry), payload);
  englishPreview();
  $('record-status').classList.remove('error');
  try {
    localStorage.setItem(keyFor(entry), JSON.stringify(payload));
    $('record-status').textContent = 'Saved in this browser.';
  } catch {
    $('record-status').textContent =
      'Browser storage is unavailable. Edits stay in this tab; export before closing it.';
  }
  refreshList();
};
function draft(entry) {
  if (state.drafts.has(keyFor(entry))) return state.drafts.get(keyFor(entry));
  try {
    const raw = readDraft(localStorage, 'gintama-draft', state.catalog.source_msb_sha256, entry.id);
    if (!raw) return null;
    const data = parseStrictJson(raw, 16000);
    return data &&
      (typeof data.english === 'string' || data.english === null) &&
      (typeof data.translator_note === 'string' || data.translator_note === null)
      ? { english: data.english, translator_note: data.translator_note }
      : null;
  } catch {
    return null;
  }
}
function working(entry) {
  return { ...entry, ...(draft(entry) || {}) };
}
function selectedMetadata() {
  return state.metadata[state.active];
}
function filtered() {
  if (!state.batch) return [];
  const f = $('filter').value,
    term = $('search').value.toLowerCase().trim();
  return state.batch.records
    .map((entry, i) => ({ entry, i, work: working(entry) }))
    .filter(({ entry, work }) => {
      const d = draft(entry),
        changed = d && (d.english !== entry.english || d.translator_note !== entry.translator_note);
      return (
        (f === 'all' ||
          (f === 'open' && !work.english) ||
          (f === 'draft' && changed) ||
          (f === 'existing' && !!entry.english)) &&
        (!term ||
          entry.id.toLowerCase().includes(term) ||
          (work.english || '').toLowerCase().includes(term))
      );
    })
    .map((x) => x.i);
}
function refreshList() {
  if (!state.batch) return;
  state.visible = filtered();
  const list = $('entries'),
    scroll = list.parentElement.scrollTop;
  list.replaceChildren();
  for (const i of state.visible) {
    const e = state.batch.records[i],
      work = working(e),
      li = document.createElement('li'),
      b = document.createElement('button');
    b.type = 'button';
    b.className = i === state.active ? 'active' : '';
    const title = document.createElement('span');
    title.textContent = `${i + 1}. ${e.id}`;
    const secondary = document.createElement('small');
    secondary.textContent = draft(e)
      ? 'Local draft'
      : work.english
        ? 'English draft'
        : 'Untranslated';
    b.append(title, secondary);
    b.addEventListener('click', () => show(i));
    li.append(b);
    list.append(li);
  }
  list.parentElement.scrollTop = scroll;
  $('progress').textContent =
    `${state.visible.length} shown · ${state.batch.records.filter((e) => !!working(e).english).length} with English / ${state.batch.records.length}`;
}
async function show(i) {
  if (!state.batch || !state.batch.records[i]) return;
  state.active = i;
  const renderVersion = ++state.renderVersion;
  const entry = state.batch.records[i],
    meta = selectedMetadata(),
    work = working(entry);
  $('entry-count').textContent = `ENTRY ${i + 1} / ${state.batch.records.length}`;
  $('entry-id').textContent = entry.id;
  $('decode').textContent = meta.decode_status.replaceAll('_', ' ');
  $('english').value = asText(work.english);
  englishPreview();
  $('note').value = asText(work.translator_note);
  $('pages').textContent =
    `Source: ${meta.page_breaks} page break(s), ${meta.line_breaks} line break(s)`;
  $('japanese').textContent = 'Select your matching game file to read this line.';
  $('source-note').textContent = 'Source bytes are checked before display.';
  $('record-status').textContent = '';
  if (state.game) {
    try {
      const result = await readRecord(state.game.msb, meta, state.glyphs);
      if (state.active !== i || renderVersion !== state.renderVersion) return;
      meta.color_controls = result.colorControls;
      meta.control_sequence = result.controlSequence;
      $('japanese').textContent = result.text.replace(/\f/g, '\n──────── page ────────\n');
      $('source-note').textContent = result.unknown.length
        ? 'This entry has unresolved glyphs or controls. Do not guess.'
        : 'Verified against the original message hash.';
    } catch (error) {
      if (state.active === i && renderVersion === state.renderVersion) {
        $('japanese').textContent = 'Unable to verify this entry.';
        $('source-note').textContent = error.message;
      }
    }
  }
  $('previous').disabled = i === 0;
  $('next').disabled = i === state.batch.records.length - 1;
  refreshList();
}
async function loadBatch() {
  const filename = $('batch').value,
    version = ++state.batchVersion;
  try {
    const [batchResponse, metaResponse] = await Promise.all([
      fetch('assets/translations/' + filename),
      fetch('assets/metadata/' + filename),
    ]);
    if (version !== state.batchVersion) return false;
    if (!batchResponse.ok || !metaResponse.ok) throw new Error('Cannot read batch files.');
    const batch = await batchResponse.json(),
      metadata = await metaResponse.json();
    if (version !== state.batchVersion) return false;
    if (
      batch.records.length !== metadata.length ||
      batch.records.some(
        (e, i) =>
          e.id !== metadata[i].id || e.source_words_sha256 !== metadata[i].source_words_sha256,
      )
    )
      throw new Error('Translation batch and source index differ.');
    state.batch = batch;
    state.metadata = metadata;
    $('search').value = '';
    $('filter').value = 'all';
    await show(0);
    return version === state.batchVersion;
  } catch (error) {
    if (version === state.batchVersion) throw error;
    return false;
  }
}

function download(content, filename, type) {
  const blob = new Blob([content], { type }),
    url = URL.createObjectURL(blob),
    a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportBatch(format) {
  try {
    if (!state.batch) throw new Error('Choose a batch.');
    const merged = state.batch.records.map(working);
    let edits = 0;
    merged.forEach((entry, i) => {
      const previous = state.batch.records[i];
      if (
        entry.english !== previous.english ||
        entry.translator_note !== previous.translator_note
      ) {
        if (entry.english === previous.english)
          throw new Error(`${entry.id}: note-only edits are not accepted as translation PRs.`);
        if (previous.english && entry.english === null)
          throw new Error(`${entry.id}: cannot erase an existing translation.`);
        checkDialogue(entry, state.metadata[i]);
        edits++;
      }
    });
    if (!edits) throw new Error('No changed translations in this batch.');
    const suffix = format === 'csv' ? 'csv' : 'json';
    const payload = format === 'csv' ? encodeCsv(merged) : formatBatch(state.batch, merged);
    download(
      payload,
      `${state.batch.batch_id}.${suffix}`,
      format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8',
    );
    $('export-status').textContent =
      `${edits} changed English entries. Download both formats before sending your contribution.`;
  } catch (error) {
    $('export-status').textContent = error.message;
  }
}
function issue() {
  try {
    if (!state.repository)
      throw new Error(
        'Repository address not configured. Download both files and use the contributor guide.',
      );
    if (!state.batch || state.active < 0) throw new Error('Choose a dialogue entry first.');
    const e = working(state.batch.records[state.active]);
    checkDialogue(e, selectedMetadata());
    const body = translationSuggestion(e, state.batch.records[state.active]);
    const url = `https://github.com/${state.repository}/issues/new?title=${encodeURIComponent('Translation: ' + e.id)}&body=${encodeURIComponent(body)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
    $('record-status').classList.remove('error');
    $('record-status').textContent =
      'Review the English-only issue before submitting it. Issue suggestions are imported manually.';
    const link = document.createElement('a');
    link.href = url;
    link.textContent = 'Open the prepared suggestion.';
    $('record-status').append(' ', link);
  } catch (err) {
    $('record-status').textContent = err.message;
    $('record-status').classList.add('error');
  }
}
function terms() {
  const query = $('term-search').value.trim().toLowerCase(),
    container = $('term-results');
  container.replaceChildren();
  if (!query || !state.glossary) return;
  const matched = [...(state.glossary.core_terms || []), ...(state.glossary.entries || [])]
    .filter((e) => JSON.stringify(e).toLowerCase().includes(query))
    .slice(0, 20);
  for (const item of matched) {
    const p = document.createElement('p');
    p.textContent = `${item.English || item.english || ''}${item.aliases?.length ? ' (' + item.aliases.join(', ') + ')' : ''}`;
    container.append(p);
  }
}
async function main() {
  try {
    const [catalog, glyphs, glossary] = await Promise.all(
      ['assets/catalog.json', 'assets/glyphs.json', 'assets/glossary.json'].map(async (url) => {
        const r = await fetch(url);
        if (!r.ok) throw new Error('Missing site data: ' + url);
        return r.json();
      }),
    );
    state.catalog = catalog;
    state.glyphs = glyphs;
    state.glossary = glossary;
    state.repository = /^[a-z\d_.-]+\/[a-z\d_.-]+$/i.test(catalog.repository || '')
      ? catalog.repository
      : '';
    for (const entry of catalog.batches) {
      const option = document.createElement('option');
      option.value = entry.file;
      option.textContent = `${entry.batch} (${entry.count})`;
      $('batch').append(option);
    }
    const loaded = await loadBatch();
    if (loaded)
      setStatus(
        'Choose your matching, legally obtained game file to see the original Japanese. You can browse English drafts without one.',
      );
  } catch (err) {
    setStatus(err.message, true);
  }
}
$('rom').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const version = ++state.gameVersion;
  ++state.renderVersion;
  state.game = null;
  $('japanese').textContent = 'Checking the newly selected file…';
  $('source-note').textContent = 'Source bytes are checked before display.';
  setStatus('Reading and verifying your local file…');
  try {
    if (!state.catalog) throw new Error('Wait for the translation index to load.');
    if (file.size > 512 * 1024 * 1024)
      throw new Error('File is larger than the 512 MiB safety limit.');
    const game = readGameFile(new Uint8Array(await file.arrayBuffer()), file.name);
    await verifyGame(game, state.catalog);
    if (version !== state.gameVersion) return;
    state.game = game;
    setStatus('Game file verified. No file bytes are uploaded.');
    await show(Math.max(0, state.active));
  } catch (err) {
    if (version !== state.gameVersion) return;
    setStatus(err.message, true);
    if (state.active >= 0) show(state.active);
  }
});
$('batch').addEventListener('change', () => {
  loadBatch().catch((error) => setStatus(error.message, true));
});
$('filter').addEventListener('change', refreshList);
$('search').addEventListener('input', refreshList);
$('english').addEventListener('input', save);
$('note').addEventListener('input', save);
$('previous').addEventListener('click', () => show(state.active - 1));
$('next').addEventListener('click', () => show(state.active + 1));
$('download-json').addEventListener('click', () => exportBatch('json'));
$('download-csv').addEventListener('click', () => exportBatch('csv'));
$('issue').addEventListener('click', issue);
$('term-search').addEventListener('input', terms);
main();
