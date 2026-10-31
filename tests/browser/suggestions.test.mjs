// Unofficial fan translation; see RIGHTS.md.
import test from 'node:test';
import assert from 'node:assert/strict';
import { translationSuggestion } from '../../web/suggestions.mjs';

const record = { id: 'msb_00000010', source_words_sha256: 'a'.repeat(64), english: 'Hello!\nReady?', translator_note: null };
test('suggestions preserve JSON line breaks and source identity without an author claim', () => {
  const text = translationSuggestion(record, { ...record, english: 'Old.' });
  assert.ok(text.includes('English (JSON escaped):\n"Hello!\\nReady?"'));
  assert.ok(text.includes('Source SHA-256: ' + 'a'.repeat(64)));
  assert.ok(!text.includes('Author:'));
});
test('suggestions reject unchanged, blank, unsafe or forged record fields', () => {
  assert.throws(() => translationSuggestion(record, record));
  for (const changed of [{ english: '' }, { english: 'https://example.invalid' }, { id: '../outside' }, { source_words_sha256: 'wrong' }])
    assert.throws(() => translationSuggestion({ ...record, ...changed }));
});
