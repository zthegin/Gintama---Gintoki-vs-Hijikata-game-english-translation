// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { ndsFiles, sha256, verifyGame } from './rom.mjs';
import { checkSafeText, finiteJson } from './text-policy.mjs';
import { scanScript } from './script-records.mjs';

const controls = new Set([0xffa1, 0xffa2, 0xffa3, 0xffa5, 0xff81, 0xff84, 0xffb1, 0xffb2]);
const check = (ok, message) => {
  if (!ok) throw new Error(message);
};
const hexHash = (value) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const sameKeys = (value, keys) =>
  value && typeof value === 'object' && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));

export const sceneId = (row) => 's01_' + row.offset.toString(16).padStart(8, '0');

export function checkParts(parts, expectedCount) {
  check(Array.isArray(parts) && parts.length === expectedCount, 'Keep every original text part.');
  check(parts.some((part) => typeof part === 'string' && part.trim()), 'The message is empty.');
  check(parts.every((part) => typeof part === 'string'), 'Each text part must be English text.');
  check(parts.reduce((n, part) => n + part.length, 0) <= 2500, 'Message exceeds 2500 characters.');
  for (const part of parts) {
    check(/^[\x20-\x7e\n]*$/.test(part), 'Use English letters, ordinary punctuation and line breaks.');
    if (part) checkSafeText(part, 'Cutscene English', 2500);
  }
  checkSafeText(parts.join(''), 'Cutscene English', 2500);
}

export function checkScene(scene) {
  check(sameKeys(scene, ['format', 'script', 'scope', 'source_msb_sha256', 'source_cdb_sha256', 'notes', 'messages']), 'Invalid opening scene data.');
  check(scene.format === 'gintama-cutscene-v1' && scene.script === 'adventure/script/s01.msb', 'Only the opening s01 cutscene is supported.');
  check(hexHash(scene.source_msb_sha256) && hexHash(scene.source_cdb_sha256), 'Invalid cutscene source hash.');
  check(typeof scene.scope === 'string' && Array.isArray(scene.notes) && scene.notes.every((note) => typeof note === 'string'), 'Invalid scene description.');
  check(Array.isArray(scene.messages) && scene.messages.length > 0 && scene.messages.length <= 2000, 'Invalid cutscene message list.');
  const seen = new Set();
  for (const row of scene.messages) {
    check(sameKeys(row, ['offset', 'source_words_sha256', 'parts']), 'Invalid cutscene entry.');
    check(Number.isSafeInteger(row.offset) && row.offset >= 16 && row.offset % 2 === 0 && !seen.has(row.offset), 'Invalid or repeated cutscene offset.');
    seen.add(row.offset);
    check(hexHash(row.source_words_sha256), 'Invalid cutscene record hash.');
    check(Array.isArray(row.parts) && row.parts.length > 0 && row.parts.length <= 64, 'Missing cutscene text parts.');
    checkParts(row.parts, row.parts.length);
  }
  return scene;
}

export function formatScene(scene, messages, originals = scene.messages) {
  checkScene(scene);
  const indexed = new Map(originals.map((row) => [row.offset, row]));
  check(Array.isArray(messages) && scene.messages.every((old) => messages.some((row) => row.offset === old.offset)), 'Keep every opening entry.');
  let previous = 0;
  messages.forEach((row) => {
    const original = indexed.get(row.offset);
    check(original && sameKeys(row, ['offset', 'source_words_sha256', 'parts']) && row.offset > previous && row.source_words_sha256 === original.source_words_sha256, 'Source offsets, hashes and order must stay unchanged.');
    checkParts(row.parts, original.parts.length);
    previous = row.offset;
  });
  return JSON.stringify(checkScene({ ...scene, messages }), finiteJson, 2) + '\n';
}

export async function readSceneGame(bytes, name, scene) {
  checkScene(scene);
  let game;
  if (/\.msb$/i.test(name)) game = { msb: bytes, cdb: null };
  else {
    check(/\.(nds|srl)$/i.test(name), 'Select your legally obtained original .nds ROM or its extracted s01.msb.');
    const files = ndsFiles(bytes);
    game = { msb: files.get(scene.script), cdb: files.get('adventure/script/s01.cdb') };
    check(game.msb && game.cdb, 'This ROM has no supported opening script.');
  }
  await verifyGame(game, scene);
  const indexed = scanScript(game.msb, { minimumOffset: 16, label: 'opening script' });
  const bundled = new Map(scene.messages.map((row) => [row.offset, row]));
  const rows = await Promise.all(indexed.filter((row) => row.partCount > 0).map(async (row) => {
    const digest = await sha256(game.msb.subarray(row.offset, row.end));
    const original = bundled.get(row.offset);
    check(!original || (original.source_words_sha256 === digest && original.parts.length === row.partCount), 'Bundled opening record differs from the source.');
    return { offset: row.offset, source_words_sha256: digest, parts: original ? [...original.parts] : Array(row.partCount).fill('') };
  }));
  check(scene.messages.every((row) => rows.some((r) => r.offset === row.offset)), 'Unsupported bundled opening record.');
  return { ...game, rows, unsupported: indexed.length - rows.length };
}

export async function readSceneMessage(msb, row, glyphs, { minimumOffset = 16 } = {}) {
  const start = row.offset;
  check(Number.isSafeInteger(start) && start >= minimumOffset && start % 2 === 0 && start + 2 <= msb.length, 'Invalid cutscene record offset.');
  const view = new DataView(msb.buffer, msb.byteOffset, msb.byteLength);
  const parts = [], unknown = [];
  let part = null, end = start, terminated = false;
  for (; end + 1 < msb.length && end - start <= 10000; end += 2) {
    const code = view.getUint16(end, true);
    if ((code >= 1 && code <= 6953) || code === 0xff70) {
      part ??= '';
      if (code === 0xff70) part += '\n';
      else {
        const letter = glyphs.codes['0x' + code.toString(16).toUpperCase().padStart(4, '0')];
        if (letter === undefined) {
          part += `⟦0x${code.toString(16).toUpperCase().padStart(4, '0')}⟧`;
          unknown.push(code);
        } else part += letter;
      }
    } else {
      check(code === 0xff71 || controls.has(code), 'Unsupported cutscene control.');
      if (part !== null) parts.push(part);
      part = null;
      if (code === 0xff71) {
        end += 2;
        terminated = true;
        break;
      }
    }
  }
  check(terminated && end + 2 <= msb.length && view.getUint16(end, true) === 0, 'Malformed cutscene record.');
  check(await sha256(msb.subarray(start, end)) === row.source_words_sha256, 'Cutscene record hash does not match.');
  check(parts.length === row.parts.length, 'Cutscene formatting parts do not match.');
  return { parts, unknown };
}

export function sceneSuggestion(scene, original, parts) {
  checkParts(parts, original.parts.length);
  check(parts.some((part, i) => part !== original.parts[i]), 'Change the English before suggesting it.');
  return `Opening cutscene translation suggestion\n\nID: ${sceneId(original)}\nScript: ${scene.script}\nSource SHA-256: ${original.source_words_sha256}\nEnglish parts (JSON):\n${JSON.stringify(parts)}\n\nKeep the parts in this order. No source game text is included.\nThis suggestion needs maintainer review and a local ROM build.`;
}
