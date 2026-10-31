// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { draftKey, readDraft } from '../../web/drafts.mjs';

function storage(entries) {
  const data = new Map(entries);
  return {
    get length() {
      return data.size;
    },
    key(index) {
      return [...data.keys()][index] ?? null;
    },
    getItem(key) {
      return data.get(key) ?? null;
    },
  };
}

test('earlier dialogue and image drafts remain readable without rewriting storage', () => {
  for (const namespace of ['gintama-draft', 'gintama-image']) {
    const saved = storage([
      [`${namespace}-v7:hash:entry`, 'older'],
      [`${namespace}-v9:hash:entry`, 'latest'],
    ]);
    assert.equal(readDraft(saved, namespace, 'hash', 'entry'), 'latest');
    assert.equal(saved.length, 2);
    assert.equal(saved.getItem(draftKey(namespace, 'hash', 'entry')), null);
  }
});

test('current key takes precedence, including an empty value', () => {
  const saved = storage([
    ['gintama-draft-v9:hash:entry', 'old'],
    ['gintama-draft:hash:entry', ''],
  ]);
  assert.equal(readDraft(saved, 'gintama-draft', 'hash', 'entry'), '');
});

test('draft lookup keeps namespaces, source hashes and entry IDs separate', () => {
  const saved = storage([
    ['gintama-image-v9:hash:entry', 'image'],
    ['gintama-draft-v9:other:entry', 'another ROM'],
    ['gintama-draft-v9:hash:entry2', 'another entry'],
    ['gintama-draft-vbad:hash:entry', 'invalid version'],
    [`gintama-draft-v${Number.MAX_SAFE_INTEGER + 1}:hash:entry`, 'unsafe number'],
  ]);
  assert.equal(readDraft(saved, 'gintama-draft', 'hash', 'entry'), null);
  assert.equal(readDraft(saved, 'gintama-image', 'hash', 'entry'), 'image');
});
