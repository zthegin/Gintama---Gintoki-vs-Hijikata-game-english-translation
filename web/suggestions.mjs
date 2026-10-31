// Unofficial fan translation; no game ownership or endorsement is claimed. See rights.html.
import { checkRecordText } from './text-policy.mjs';

export function translationSuggestion(record, original) {
  checkRecordText(record);
  if (!/^[A-Za-z0-9_]+$/.test(record.id) || !/^[a-f0-9]{64}$/.test(record.source_words_sha256))
    throw new Error('Invalid record identity.');
  if (typeof record.english !== 'string' || !record.english.trim())
    throw new Error('Write an English suggestion first.');
  if (original && record.english === original.english)
    throw new Error('Change the English before suggesting it.');
  return `Translation suggestion\n\nID: ${record.id}\nSource SHA-256: ${record.source_words_sha256}\nEnglish (JSON escaped):\n${JSON.stringify(record.english)}\nNote: ${record.translator_note || '(none)'}\n\nNo source game text is included.`;
}
