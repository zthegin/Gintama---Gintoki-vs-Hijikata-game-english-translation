// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { ndsFiles, sha256, verifyGame } from './rom.mjs';
import { checkParts } from './cutscene-codec.mjs';
import { finiteJson } from './text-policy.mjs';
import { scanScript } from './script-records.mjs';

const check = (ok, text) => { if (!ok) throw new Error(text); };
const hash = (s) => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
const keys = (v, wanted) => v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === wanted.length && wanted.every((k) => Object.hasOwn(v, k));
const fields = ['script', 'source_msb_sha256', 'source_cdb_sha256', 'record_count', 'messages'];
export const battleId = (script, row) => script.script.slice(14, -4).replaceAll('/', '_') + '_' + row.offset.toString(16).padStart(8, '0');

export function checkBattle(pack) {
  check(keys(pack, ['format', 'notes', 'scripts']) && pack.format === 'gintama-battle-v1', 'Invalid battle pack.');
  check(Array.isArray(pack.notes) && pack.notes.length <= 10 && pack.notes.every((n) => typeof n === 'string' && n.length <= 1000), 'Invalid battle notes.');
  check(Array.isArray(pack.scripts) && pack.scripts.length > 0 && pack.scripts.length <= 128, 'Invalid battle script list.');
  const seen = new Set();
  for (const script of pack.scripts) {
    check(keys(script, fields) && typeof script.script === 'string' && /^battle\/script\/(character|interrupt|item|message)\/[a-z0-9_]+\.msb$/.test(script.script) && !seen.has(script.script), 'Invalid or repeated battle script.');
    seen.add(script.script);
    check(hash(script.source_msb_sha256) && hash(script.source_cdb_sha256), 'Invalid battle source hash.');
    check(Number.isSafeInteger(script.record_count) && script.record_count >= 0 && script.record_count <= 20000, 'Invalid battle count.');
    check(Array.isArray(script.messages) && script.messages.length <= script.record_count, 'Invalid battle messages.');
    const offsets = new Set();
    for (const row of script.messages) {
      check(keys(row, ['offset', 'source_words_sha256', 'parts']) && Number.isSafeInteger(row.offset) && row.offset >= 4 && row.offset % 2 === 0 && !offsets.has(row.offset), 'Invalid or repeated battle offset.');
      offsets.add(row.offset);
      check(hash(row.source_words_sha256) && Array.isArray(row.parts) && row.parts.length > 0 && row.parts.length <= 64, 'Invalid battle record.');
      checkParts(row.parts, row.parts.length);
    }
  }
  return pack;
}

export function scanBattle(data) {
  return scanScript(data, { label: 'battle script' });
}

export async function readBattleGame(bytes, name, script) {
  checkBattle({ format: 'gintama-battle-v1', notes: [], scripts: [script] });
  let game;
  if (/\.msb$/i.test(name)) game = { msb: bytes, cdb: null };
  else {
    check(/\.(nds|srl)$/i.test(name), 'Select your legally obtained original ROM or its extracted battle .msb.');
    const files = ndsFiles(bytes);
    game = { msb: files.get(script.script), cdb: files.get(script.script.slice(0, -3) + 'cdb') };
    check(game.msb && game.cdb, 'Battle script is missing from this ROM.');
  }
  await verifyGame(game, script);
  const indexed = scanBattle(game.msb);
  check(indexed.length === script.record_count, 'Battle record count changed.');
  const bundled = new Map(script.messages.map((row) => [row.offset, row]));
  const rows = await Promise.all(indexed.filter((row) => row.partCount > 0).map(async (row) => {
    const digest = await sha256(game.msb.subarray(row.offset, row.end));
    const original = bundled.get(row.offset);
    check(!original || (original.source_words_sha256 === digest && original.parts.length === row.partCount), 'Bundled battle record differs from the source.');
    return { offset: row.offset, source_words_sha256: digest, parts: original ? [...original.parts] : Array(row.partCount).fill('') };
  }));
  check(script.messages.every((row) => rows.some((r) => r.offset === row.offset)), 'Unsupported bundled battle record.');
  return { ...game, rows, unsupported: indexed.length - rows.length };
}

export function formatBattle(pack, script, messages, originals) {
  checkBattle(pack);
  const trusted = pack.scripts.find((s) => s.script === script.script);
  check(trusted && fields.filter((k) => k !== 'messages').every((k) => trusted[k] === script[k]), 'Battle metadata changed.');
  const indexed = new Map(originals.map((r) => [r.offset, r]));
  for (const row of messages) {
    const original = indexed.get(row.offset);
    check(original && original.source_words_sha256 === row.source_words_sha256, 'Battle source record changed.');
    checkParts(row.parts, original.parts.length);
  }
  const output = { ...pack, scripts: [{ ...trusted, messages }] };
  checkBattle(output);
  return JSON.stringify(output, finiteJson, 2) + '\n';
}

export function battleSuggestion(script, row, parts) {
  checkParts(parts, row.parts.length);
  check(parts.some((p, i) => p !== row.parts[i]), 'Change the English before suggesting it.');
  return `Battle translation suggestion\n\nID: ${battleId(script, row)}\nScript: ${script.script}\nOffset: ${row.offset}\nSource SHA-256: ${row.source_words_sha256}\nEnglish parts (JSON):\n${JSON.stringify(parts)}\n\nKeep the parts in order. No source game text is included.\nA maintainer must review the English and test a local build.`;
}
