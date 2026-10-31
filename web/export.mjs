// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { checkRecordText, finiteJson, stripColors, colorControls } from './text-policy.mjs';

export function fieldControlSequence(text) {
  colorControls(text);
  return [...text.matchAll(/\[(blue|red|\/color)\]|\f/gi)].map((match) =>
    match[0] === '\f' ? 0xff72 : match[1].toLowerCase() === 'blue' ? 0xff82
      : match[1].toLowerCase() === 'red' ? 0xff81 : 0xff84,
  );
}

export function checkDialogue(entry, metadata) {
  checkRecordText(entry);
  if (!entry.english || !entry.english.trim()) throw new Error(`${entry.id}: English is empty.`);
  const pages = stripColors(entry.english).split('\f');
  if (pages.length - 1 !== metadata.page_breaks)
    throw new Error(
      `${entry.id}: keep ${metadata.page_breaks} page break(s). Type \\f between dialogue pages.`,
    );
  if (pages.some((page) => !page.trim()))
    throw new Error(`${entry.id}: a dialogue page is empty. Add its text before exporting.`);
  const colors = colorControls(entry.english);
  const expected = metadata.color_controls;
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
