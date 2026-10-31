// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import {
  packObj,
  unpackObj,
  renderLabel,
  encodeLabel,
  lz10,
  readImages,
  readImage,
} from '../../web/graphics-codec.mjs';
const root = fileURLToPath(new URL('../../', import.meta.url));
const font = JSON.parse(readFileSync(root + 'graphics/pixel_font.json', 'utf8')).rows;
const fixtures = JSON.parse(
  readFileSync(new URL('./graphics-fixtures.json', import.meta.url), 'utf8'),
);
const sha = (b) => createHash('sha256').update(b).digest('hex');
test('two OBJ cells preserve the 32-pixel boundary', () => {
  const pixels = new Uint8Array(1024);
  pixels[0] = 1;
  pixels[32] = 3;
  pixels[1023] = 4;
  const packed = packObj(pixels);
  assert.equal(packed[0], 1);
  assert.equal(packed[256], 3);
  assert.deepEqual(unpackObj(packed), pixels);
});
test('browser renderer and optimal compressor match independent Python results', () => {
  for (const f of fixtures) {
    const result = encodeLabel(f.english, f.entry, font);
    assert.equal(sha(result.data), f.decoded_sha256);
    assert.equal(sha(result.packed), f.compressed_sha256);
    assert.equal(result.packed.length, f.compressed_bytes);
    assert.deepEqual(result.shift, f.shift);
    assert.deepEqual(lz10(result.packed).data, result.data);
  }
});
test('rejects clipped, unsupported and over-capacity labels', () => {
  for (const text of ['TOO MANY LETTERS TO FIT', 'ONE\nTWO\nTHREE', '☃'])
    assert.throws(() => renderLabel(text, font));
  assert.throws(
    () =>
      encodeLabel(
        'TEST',
        { id: 'test', background: 'original_transparent', compressed_capacity: 1 },
        font,
      ),
    /slot holds/,
  );
  assert.throws(() => lz10(new Uint8Array([0x10, 255, 255, 255, 0])), /size/);
});
test('wide label search preserves the best legal placement', () => {
  const entry = { background: 'original_transparent', compressed_capacity: 145 };
  const result = encodeLabel('MMMMMMMMMII', entry, font);
  assert.deepEqual(result.shift, [0, 2]);
  assert.equal(
    sha(result.packed),
    '45f04caf22bb42f39718ddf58518aa87ee4b261ffec2a0733d5d3592d15f6ec7',
  );
  assert.throws(
    () => encodeLabel('MMMMMMMMMII', { ...entry, compressed_capacity: 144 }, font),
    /Needs 145 bytes/,
  );
});

test('all 193 original image labels resolve from a private ROM', async (t) => {
  const path = process.env.GINTAMA_TEST_ROM;
  if (!path || !existsSync(path)) {
    t.skip('Set GINTAMA_TEST_ROM for the private real-ROM audit.');
    return;
  }
  const catalog = JSON.parse(readFileSync(root + 'graphics/catalog.json', 'utf8')),
    game = await readImages(new Uint8Array(readFileSync(path)), catalog);
  for (const entry of catalog.entries) {
    const pixels = await readImage(game, entry);
    assert.equal(pixels.length, 1024);
  }
  assert.equal(catalog.entries.length, 193);
});
