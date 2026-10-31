// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { ndsFiles, readGameFile, readRecord, verifyGame, sha256 } from '../../web/rom.mjs';
const u16 = (buffer, at, n) => {
  buffer[at] = n & 255;
  buffer[at + 1] = (n >>> 8) & 255;
};
const u32 = (buffer, at, n) => {
  for (let i = 0; i < 4; i++) buffer[at + i] = (n >>> (8 * i)) & 255;
};
function fixture() {
  const b = new Uint8Array(0x900);
  const msb = Uint8Array.from([
    115, 99, 114, 26, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0x70, 0xff, 2, 0, 0x71, 0xff, 0, 0,
  ]);
  const cdb = Uint8Array.from([1, 2, 3, 4]);
  u32(b, 0x40, 0x200);
  u32(b, 0x48, 0x300);
  u32(b, 0x4c, 16);
  let p = 0x200 + 24;
  const writeName = (name, dir, id) => {
    b[p++] = name.length | (dir ? 0x80 : 0);
    for (const ch of name) b[p++] = ch.charCodeAt(0);
    if (dir) {
      u16(b, p, id);
      p += 2;
    }
  };
  const root = p;
  writeName('field', true, 0xf001);
  b[p++] = 0;
  const field = p;
  writeName('script', true, 0xf002);
  b[p++] = 0;
  const script = p;
  writeName('fld_scr.msb');
  writeName('fld_scr.cdb');
  b[p++] = 0;
  for (const [i, offset, first, parent] of [
    [0, root, 0, 3],
    [1, field, 0, 0xf000],
    [2, script, 0, 0xf001],
  ]) {
    const at = 0x200 + 8 * i;
    u32(b, at, offset - 0x200);
    u16(b, at + 4, first);
    u16(b, at + 6, parent);
  }
  u32(b, 0x44, p - 0x200);
  u32(b, 0x300, 0x500);
  u32(b, 0x304, 0x500 + msb.length);
  u32(b, 0x308, 0x600);
  u32(b, 0x30c, 0x600 + cdb.length);
  b.set(msb, 0x500);
  b.set(cdb, 0x600);
  return { b, msb, cdb };
}
test('NitroFS path resolution and local file slicing', () => {
  const { b, msb, cdb } = fixture();
  const files = ndsFiles(b);
  assert.deepEqual(files.get('field/script/fld_scr.msb'), msb);
  assert.deepEqual(readGameFile(b, 'original.nds').cdb, cdb);
  assert.deepEqual(readGameFile(msb, 'fld_scr.msb').msb, msb);
  assert.throws(() => readGameFile(b, 'some.zip'), /Select an/);
});
test('source hash and original record hash check', async () => {
  const { b, msb, cdb } = fixture();
  const game = readGameFile(b, 'original.nds');
  const reference = { source_msb_sha256: await sha256(msb), source_cdb_sha256: await sha256(cdb) };
  assert.equal(await verifyGame(game, reference), true);
  const record = {
    id: 'msb_00000010',
    offset_hex: '0x10',
    source_words_sha256: await sha256(msb.subarray(16, 24)),
  };
  const result = await readRecord(msb, record, { codes: { '0x0001': 'a', '0x0002': 'b' } });
  assert.equal(result.text, 'a\nb');
  await assert.rejects(
    () => verifyGame(game, { ...reference, source_msb_sha256: 'bad' }),
    /MSB SHA-256/,
  );
  await assert.rejects(
    () => readRecord(msb, { ...record, source_words_sha256: 'bad' }, { codes: {} }),
    /mismatch/,
  );
});
test('readRecord exposes verified color controls as markup and control inventory', async () => {
  const msb = Uint8Array.from([
    115, 99, 114, 26, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0x82, 0xff, 1, 0, 0x84, 0xff, 0x72, 0xff, 0x71, 0xff, 0, 0,
  ]);
  const record = {
    id: 'colored',
    offset_hex: '0x10',
    source_words_sha256: await sha256(msb.subarray(16, 26)),
  };
  const result = await readRecord(msb, record, { codes: { '0x0001': 'A' } });
  assert.equal(result.text, '[blue]A[/color]\f');
  assert.deepEqual(result.colorControls, [0xff82, 0xff84]);
  assert.deepEqual(result.controlSequence, [0xff82, 0xff84, 0xff72]);
  assert.deepEqual(result.unknown, []);
});
test('rejects corrupt NitroFS pointers and terminators', async () => {
  const { b, msb } = fixture();
  const broken = b.slice();
  u32(broken, 0x300, 0xffff);
  assert.throws(() => ndsFiles(broken), /outside/);
  const altered = msb.slice();
  altered[22] = 0;
  await assert.rejects(
    () =>
      readRecord(
        altered,
        { id: 'test', offset_hex: '0x10', source_words_sha256: 'x' },
        { codes: {} },
      ),
    /terminator/,
  );
});
test('actual MSB matches public reference and glyph map', async (t) => {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const index = JSON.parse(readFileSync(root + 'reference/record_index.json', 'utf8'));
  const map = JSON.parse(readFileSync(root + 'reference/glyph_codes_public.json', 'utf8'));
  const path = process.env.GINTAMA_TEST_MSB;
  if (!path || !existsSync(path)) {
    t.skip('Set GINTAMA_TEST_MSB for the private real-file audit.');
    return;
  }
  const msb = new Uint8Array(readFileSync(path));
  assert.equal(await verifyGame({ msb, cdb: null }, index), true);
  for (const row of index.records.filter((x) => x.decode_status === 'mapped').slice(0, 20)) {
    const result = await readRecord(msb, row, map);
    assert.equal(result.unknown.length, 0);
    assert.equal(result.pageBreaks, row.page_breaks);
  }
});
