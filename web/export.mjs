// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { checkRecordText, finiteJson, stripColors, colorControls, fieldMarkupSequence, inlineFieldControls } from './text-policy.mjs';

export function fieldControlSequence(text) {
  return fieldMarkupSequence(text);
}

export function checkDialogue(entry, metadata) {
  checkRecordText(entry);
  if (metadata.termination !== undefined && !['end', 'nul'].includes(metadata.termination))
    throw new Error('Invalid record termination.');
  if (!entry.english || !entry.english.trim()) throw new Error(`${entry.id}: English is empty.`);
  if (metadata.raw_color_controls !== undefined && typeof metadata.raw_color_controls !== 'boolean')
    throw new Error('Invalid raw color controls flag.');
  const pages = stripColors(entry.english).split('\f');
  if (pages.length - 1 !== metadata.page_breaks)
    throw new Error(
      `${entry.id}: keep ${metadata.page_breaks} page break(s). Type \\f between dialogue pages.`,
    );
  if (metadata.termination === 'nul') {
    if (!Number.isSafeInteger(metadata.line_breaks) || metadata.line_breaks < 0)
      throw new Error(`${entry.id}: load the matching game metadata to verify menu lines.`);
    if ((stripColors(entry.english).match(/\n/g) || []).length > metadata.line_breaks)
      throw new Error(`${entry.id}: keep the original menu line count.`);
  }
  if (pages.some((page) => !page.trim()))
    throw new Error(`${entry.id}: a dialogue page is empty. Add its text before exporting.`);
  const colors = colorControls(entry.english);
  const expected = metadata.color_controls;
  if (!Array.isArray(metadata.control_sequence) && fieldControlSequence(entry.english).some((code) => inlineFieldControls.has(code)))
    throw new Error(`${entry.id}: load your matching game file to verify inline controls before exporting.`);
  if (Array.isArray(metadata.control_sequence)) {
    if (JSON.stringify(fieldControlSequence(entry.english)) !== JSON.stringify(metadata.control_sequence))
      throw new Error(`${entry.id}: keep the source colors in their original order and dialogue pages.`);
  } else if (Array.isArray(expected)) {
    if (JSON.stringify(colors) !== JSON.stringify(expected))
      throw new Error(`${entry.id}: keep the source [blue]/[red] spans and [/color] markers.`);
  } else if (colors.length || ['inline_controls_need_review', 'unresolved_glyphs'].includes(metadata.decode_status)) {
    throw new Error(`${entry.id}: load your matching game file to verify the source colors before exporting.`);
  }
}

export function encodeCsv(records) {
  const quoted = (value) =>
    /[",\r\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
  const cell = (value) => {
    if (value == null) return '';
    const escaped = JSON.stringify(value).slice(1, -1);
    return escaped.startsWith("'") || /^\s*[=+@-]/u.test(escaped.normalize('NFKC'))
      ? "'" + escaped
      : escaped;
  };
  records.forEach(checkRecordText);
  return (
    [
      'id,source_words_sha256,english,translator_note',
      ...records.map((r) =>
        [r.id, r.source_words_sha256, cell(r.english), cell(r.translator_note)]
          .map(quoted)
          .join(','),
      ),
    ].join('\n') + '\n'
  );
}
export function formatBatch(batch, records) {
  records.forEach(checkRecordText);
  return JSON.stringify({ ...batch, records }, finiteJson, 2) + '\n';
}
