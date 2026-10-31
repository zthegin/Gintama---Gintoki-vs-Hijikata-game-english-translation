// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { checkDialogue, encodeCsv, formatBatch } from '../../web/export.mjs';
const root = fileURLToPath(new URL('../../', import.meta.url));
test('CSV agrees byte-for-byte with committed synchronized view', () => {
  const batch = JSON.parse(readFileSync(root + 'translations/ready/batch_0001.json', 'utf8'));
  assert.equal(encodeCsv(batch.records), readFileSync(root + 'csv/ready/batch_0001.csv', 'utf8'));
  assert.equal(
    formatBatch(batch, batch.records),
    readFileSync(root + 'translations/ready/batch_0001.json', 'utf8'),
  );
});
test('CSV quotes commas, quotes, line and page breaks', () => {
  const text = encodeCsv([
    {
      id: 'test',
      source_words_sha256: 'abc',
      english: 'A, "quote"\nnew line\fnext page',
      translator_note: null,
    },
  ]);
  assert.equal(text, readFileSync(root + 'tests/browser/expected_csv.txt', 'utf8'));
});

test('dialogue exports reject empty pages with guidance before the local build', () => {
  const entry = (english) => ({
    id: 'example',
    source_words_sha256: 'a'.repeat(64),
    english,
    translator_note: null,
  });
  for (const text of ['Hello\f', '\fHello', 'Hello\f  \n'])
    assert.throws(() => checkDialogue(entry(text), { page_breaks: 1 }), /page is empty/);
  assert.throws(() => checkDialogue(entry('Hello'), { page_breaks: 1 }), /Type \\f/);
  assert.throws(() => checkDialogue(entry('  '), { page_breaks: 0 }), /nonempty text/);
  assert.throws(() => checkDialogue(entry(null), { page_breaks: 0 }), /English is empty/);
  assert.doesNotThrow(() => checkDialogue(entry('Hello.\fNext page.'), { page_breaks: 1 }));
  assert.doesNotThrow(() => checkDialogue(entry('Hello.\nNext line.'), { page_breaks: 0 }));
});

test('dialogue color markers must match verified source controls and pages', () => {
  const entry = (english) => ({ id: 'colored', source_words_sha256: 'a'.repeat(64),
    english, translator_note: null });
  const meta = { page_breaks: 1, color_controls: [0xff82, 0xff84],
    control_sequence: [0xff82, 0xff84, 0xff72] };
  assert.doesNotThrow(() => checkDialogue(entry('[blue]Forest Trail[/color].\fGo there.'), meta));
  for (const text of ['Forest Trail.\fGo there.', '[red]Forest Trail[/color].\fGo there.',
    'Go there.\f[blue]Forest Trail[/color].'])
    assert.throws(() => checkDialogue(entry(text), meta), /source colors/);
  assert.throws(() => checkDialogue(entry('[blue]Forest[/color]'),
    { page_breaks: 0, color_controls: [] }), /source.*spans/);
  assert.throws(() => checkDialogue(entry('[blue]Forest[/color]'), { page_breaks: 0 }),
    /matching game file/);
  assert.throws(() => checkDialogue(entry('Forest'),
    { page_breaks: 0, decode_status: 'inline_controls_need_review' }), /matching game file/);
});
