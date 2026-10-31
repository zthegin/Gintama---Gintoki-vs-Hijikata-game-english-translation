// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { draftKey, readDraft } from './drafts.mjs';
import { encodeLabel, readImages, readImage } from './graphics-codec.mjs';
import { encodeCsv, formatBatch } from './export.mjs';
import { checkRecordText, parseStrictJson } from './text-policy.mjs';
import { translationSuggestion } from './suggestions.mjs';
const $ = (id) => document.getElementById(id),
  state = {
    catalog: null,
    batch: null,
    rows: null,
    game: null,
    active: 0,
    version: 0,
    valid: false,
    gameVersion: 0,
    drafts: new Map(),
  };
const status = (s, error = false) => {
  $('image-status').textContent = s;
  $('image-status').classList.toggle('error', error);
};
const key = (id) => draftKey('gintama-image', state.catalog.source_rom_sha256, id);
function working(entry) {
  const current = state.drafts.get(key(entry.id));
  if (current) return { ...entry, ...current };
  try {
    const raw = readDraft(localStorage, 'gintama-image', state.catalog.source_rom_sha256, entry.id);
    const d = raw && parseStrictJson(raw, 16000);
    if (
      d &&
      typeof d.english === 'string' &&
      (d.translator_note === null || typeof d.translator_note === 'string')
    )
      return { ...entry, english: d.english, translator_note: d.translator_note };
  } catch {}
  return { ...entry };
}
function draw(id, pixels, colors) {
  const canvas = $(id),
    ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 64, 16);
  if (!pixels) return;
  const image = ctx.createImageData(64, 16);
  pixels.forEach((p, i) => {
    const c = colors[p];
    image.data.set([...c, 255], i * 4);
  });
  ctx.putImageData(image, 0, 0);
}
function zoom() {
  const size = Number($('image-zoom').value);
  for (const id of ['image-source', 'image-english']) $(id).style.width = `${64 * size}px`;
}
function list() {
  if (!state.batch) return;
  const q = $('image-search').value.toLowerCase().trim(),
    ol = $('image-entries');
  ol.replaceChildren();
  let count = 0;
  state.catalog.entries.forEach((e, i) => {
    if (
      q &&
      !`${e.id} ${e.canonical_english} ${working(state.batch.records[i]).english}`
        .toLowerCase()
        .includes(q)
    )
      return;
    const li = document.createElement('li'),
      b = document.createElement('button');
    b.type = 'button';
    b.textContent = e.canonical_english;
    b.classList.toggle('active', i === state.active);
    b.addEventListener('click', () => show(i));
    li.append(b);
    ol.append(li);
    count++;
  });
  $('image-progress').textContent = `${count} labels`;
}
function preview() {
  const e = state.catalog.entries[state.active];
  state.valid = false;
  try {
    const encoded = encodeLabel($('image-text').value, e, state.rows),
      colors =
        state.game?.colors ||
        Array.from({ length: 16 }, (_, i) =>
          i === 15 ? [255, 255, 255] : i === 11 ? [49, 49, 49] : [0, 0, 0],
        );
    draw('image-english', encoded.pixels, colors);
    $('image-record-status').textContent =
      `Fits: ${encoded.packed.length} / ${e.compressed_capacity} compressed bytes. ${state.game ? 'Uses your original palette.' : 'Load the ROM to check the source palette.'}`;
    $('image-record-status').classList.remove('error');
    state.valid = true;
  } catch (e) {
    $('image-record-status').textContent = e.message;
    $('image-record-status').classList.add('error');
    draw('image-english');
  }
}
async function show(i) {
  if (!state.batch || i < 0 || i >= state.batch.records.length) return;
  state.active = i;
  const token = ++state.version,
    e = state.catalog.entries[i],
    r = working(state.batch.records[i]);
  $('image-title').textContent = e.canonical_english;
  $('image-id').textContent = e.id;
  $('image-text').value = r.english || '';
  $('image-note').value = r.translator_note || '';
  $('image-previous').disabled = i === 0;
  $('image-next').disabled = i === state.batch.records.length - 1;
  list();
  preview();
  draw('image-source');
  if (state.game) {
    try {
      const pixels = await readImage(state.game, e);
      if (token === state.version) draw('image-source', pixels, state.game.colors);
    } catch (err) {
      if (token === state.version) status(err.message, true);
    }
  }
}
function save() {
  if (!state.batch) return;
  const entry = state.batch.records[state.active],
    draft = { english: $('image-text').value, translator_note: $('image-note').value || null };
  state.drafts.set(key(entry.id), draft);
  try {
    localStorage.setItem(key(entry.id), JSON.stringify(draft));
  } catch {
    status(
      'Browser storage is unavailable. Edits stay in this tab; export before closing it.',
      true,
    );
  }
  preview();
}
function checkText(r) {
  checkRecordText(r);
}
function download(format) {
  try {
    const records = state.batch.records.map(working);
    let edits = 0;
    records.forEach((r, i) => {
      checkText(r);
      encodeLabel(r.english, state.catalog.entries[i], state.rows);
      if (r.english !== state.batch.records[i].english) edits++;
      else if (r.translator_note !== state.batch.records[i].translator_note)
        throw new Error('Notes must accompany an English change.');
    });
    if (!edits) throw new Error('No changed image labels to export.');
    const content = format === 'json' ? formatBatch(state.batch, records) : encodeCsv(records),
      blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv' }),
      url = URL.createObjectURL(blob),
      a = document.createElement('a');
    a.href = url;
    a.download = `gin_tama_names.${format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('image-export-status').textContent =
      `${edits} English changes. Submit both formats together; no source art is included.`;
  } catch (e) {
    $('image-export-status').textContent = e.message;
  }
}
async function suggest() {
  try {
    if (!state.batch) throw new Error('Wait for the image index to load.');
    const original = state.batch.records[state.active], record = working(original);
    const body = translationSuggestion(record, original);
    encodeLabel(record.english, state.catalog.entries[state.active], state.rows);
    const response = await fetch('assets/catalog.json');
    if (!response.ok) throw new Error('Could not load the contribution repository.');
    const { repository } = await response.json();
    if (typeof repository !== 'string' || !/^[a-z\d_-]+\/[a-z\d_.-]+$/i.test(repository))
      throw new Error('Invalid contribution repository.');
    const url = `https://github.com/${repository}/issues/new?title=${encodeURIComponent('Translation: ' + record.id)}&body=${encodeURIComponent(body)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
    const link = document.createElement('a');
    link.href = url;
    link.rel = 'noreferrer';
    link.textContent = 'Open the prepared suggestion.';
    $('image-export-status').textContent = 'Review and submit the English-only issue. A maintainer imports accepted labels and records your GitHub credit. ';
    $('image-export-status').append(link);
  } catch (error) {
    $('image-export-status').textContent = error.message;
  }
}
$('image-rom').addEventListener('change', async (event) => {
  const f = event.target.files?.[0];
  if (!f) return;
  const version = ++state.gameVersion;
  ++state.version;
  state.game = null;
  draw('image-source');
  if (state.batch) preview();
  status('Checking your local original ROM…');
  try {
    if (!state.catalog) throw new Error('Wait for the image index to load.');
    if (f.size > 512 * 1024 * 1024) throw new Error('File exceeds the 512 MiB limit.');
    const game = await readImages(new Uint8Array(await f.arrayBuffer()), state.catalog);
    if (version !== state.gameVersion) return;
    state.game = game;
    status('Original ROM verified. Source pictures stay in this browser tab.');
    await show(state.active);
  } catch (e) {
    if (version !== state.gameVersion) return;
    status(e.message, true);
    show(state.active);
  }
});
$('image-search').addEventListener('input', list);
$('image-text').addEventListener('input', save);
$('image-note').addEventListener('input', save);
$('image-zoom').addEventListener('change', zoom);
$('image-previous').addEventListener('click', () => show(state.active - 1));
$('image-next').addEventListener('click', () => show(state.active + 1));
$('image-json').addEventListener('click', () => download('json'));
$('image-csv').addEventListener('click', () => download('csv'));
$('image-suggest').addEventListener('click', suggest);
try {
  const [catalog, font, batch] = await Promise.all(
    ['catalog.json', 'pixel_font.json', 'translations.json'].map(async (name) => {
      const r = await fetch('assets/graphics/' + name);
      if (!r.ok) throw new Error('Missing image data: ' + name);
      return r.json();
    }),
  );
  state.catalog = catalog;
  state.batch = batch;
  state.rows = font.rows;
  zoom();
  await show(0);
  status(
    'Select your original legally obtained ROM to compare the Japanese artwork. English labels can be edited without it.',
  );
} catch (e) {
  status(e.message, true);
}
