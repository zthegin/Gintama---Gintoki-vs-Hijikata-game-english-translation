// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import { ndsFiles, sha256 } from './rom.mjs';
const need = (ok, message) => {
  if (!ok) throw new Error(message);
};
export function lz10(data, start = 0) {
  need(start >= 0 && start + 4 < data.length && data[start] === 0x10, 'Missing LZ10 header.');
  const size = data[start + 1] | (data[start + 2] << 8) | (data[start + 3] << 16);
  need(size > 0 && size <= 1048576, 'Invalid decoded image size.');
  const out = new Uint8Array(size);
  let used = 0,
    pos = start + 4;
  while (used < size) {
    need(pos < data.length, 'Truncated LZ flags.');
    const flags = data[pos++];
    for (let bit = 7; bit >= 0 && used < size; bit--) {
      if (flags & (1 << bit)) {
        need(pos + 2 <= data.length, 'Truncated LZ match.');
        const token = (data[pos++] << 8) | data[pos++],
          length = (token >>> 12) + 3,
          distance = (token & 4095) + 1;
        need(distance <= used, 'Invalid LZ backreference.');
        for (let i = 0; i < length && used < size; i++) {
          out[used] = out[used - distance];
          used++;
        }
      } else {
        need(pos < data.length, 'Truncated LZ literal.');
        out[used++] = data[pos++];
      }
    }
  }
  return { data: out, end: pos };
}
export function unpackObj(data) {
  need(data.length === 512, 'Expected 64×16 label.');
  const pixels = new Uint8Array(1024);
  let p = 0;
  for (const cx of [0, 32])
    for (let ty = 0; ty < 2; ty++)
      for (let tx = 0; tx < 4; tx++)
        for (let y = 0; y < 8; y++)
          for (let x = 0; x < 8; x += 2) {
            const at = (ty * 8 + y) * 64 + cx + tx * 8 + x,
              b = data[p++];
            pixels[at] = b & 15;
            pixels[at + 1] = b >>> 4;
          }
  return pixels;
}
export function packObj(pixels) {
  need(
    pixels.length === 1024 && pixels.every((x) => Number.isInteger(x) && x >= 0 && x < 16),
    'Invalid label pixels.',
  );
  const data = new Uint8Array(512);
  let p = 0;
  for (const cx of [0, 32])
    for (let ty = 0; ty < 2; ty++)
      for (let tx = 0; tx < 4; tx++)
        for (let y = 0; y < 8; y++)
          for (let x = 0; x < 8; x += 2) {
            const at = (ty * 8 + y) * 64 + cx + tx * 8 + x;
            data[p++] = pixels[at] | (pixels[at + 1] << 4);
          }
  return data;
}
export function renderLabel(text, rows, background = 'original_transparent', dx = 0, dy = 0) {
  need(
    typeof text === 'string' && text.trim() && text.length <= 80,
    'Write a short English label.',
  );
  const lines = text.toUpperCase().split('\n');
  need(lines.length <= 2, 'At most two lines fit.');
  const ink = new Set();
  lines.forEach((line, i) => {
    need(
      line && [...line].every((c) => Object.hasOwn(rows, c)),
      'Unsupported character or empty line.',
    );
    const width = [...line].reduce((n, c) => n + rows[c][0].length + 1, 0) - 1;
    let x = Math.floor((64 - width) / 2) + dx;
    const y = (lines.length === 1 ? 4 : i * 9) + dy;
    need(
      width <= 62 && x >= 1 && x + width <= 63 && y >= 0 && y + 7 <= 16,
      'Label is too wide; use a shorter display name.',
    );
    for (const c of line) {
      rows[c].forEach((row, yy) =>
        [...row].forEach((v, xx) => {
          if (v === '#') ink.add((y + yy) * 64 + x + xx);
        }),
      );
      x += rows[c][0].length + 1;
    }
  });
  const pixels = new Uint8Array(1024);
  if (background === 'native_dark_backplate') pixels.fill(11);
  for (const at of ink) {
    const x = at % 64,
      y = Math.floor(at / 64);
    for (let yy = Math.max(0, y - 1); yy < Math.min(16, y + 2); yy++)
      for (let xx = Math.max(0, x - 1); xx < Math.min(64, x + 2); xx++) pixels[yy * 64 + xx] = 11;
  }
  for (const at of ink) pixels[at] = 15;
  return pixels;
}
export function compress(data) {
  const n = data.length,
    occurrences = new Map(),
    key = (p) => `${data[p]},${data[p + 1]},${data[p + 2]}`;
  for (let p = 0; p < n - 2; p++) {
    const k = key(p);
    if (!occurrences.has(k)) occurrences.set(k, []);
    occurrences.get(k).push(p);
  }
  const matches = [];
  for (let p = 0; p < n; p++) {
    const distances = new Map(),
      candidates = occurrences.get(key(p)) || [],
      limit = Math.min(18, n - p);
    for (let i = candidates.length - 1; i >= 0; i--) {
      const q = candidates[i];
      if (q > p - 2) continue;
      const distance = p - q;
      if (distance > 4096) break;
      let length = 3;
      while (length < limit && data[p + length] === data[p + length - distance]) length++;
      for (let size = 3; size <= length; size++)
        if (!distances.has(size)) distances.set(size, distance);
      if (length === limit) break;
    }
    matches.push([...distances].sort((a, b) => b[0] - a[0]));
  }
  const costs = Array.from({ length: n + 1 }, () => new Int32Array(8)),
    choices = Array.from({ length: n }, () => []);
  for (let p = n - 1; p >= 0; p--)
    for (let mod = 0; mod < 8; mod++) {
      const flag = mod === 0 ? 1 : 0,
        next = (mod + 1) % 8;
      let best = flag + 1 + costs[p + 1][next],
        choice = [1, 0];
      for (const [size, distance] of matches[p]) {
        const value = flag + 2 + costs[p + size][next];
        if (value < best) {
          best = value;
          choice = [size, distance];
        }
      }
      costs[p][mod] = best;
      choices[p][mod] = choice;
    }
  const out = [0x10, n & 255, (n >>> 8) & 255, (n >>> 16) & 255];
  let p = 0;
  while (p < n) {
    const at = out.length;
    out.push(0);
    let flags = 0;
    for (let mod = 0; mod < 8 && p < n; mod++) {
      const [size, distance] = choices[p][mod];
      if (distance) {
        flags |= 1 << (7 - mod);
        const token = ((size - 3) << 12) | (distance - 1);
        out.push(token >>> 8, token & 255);
      } else out.push(data[p]);
      p += size;
    }
    out[at] = flags;
  }
  return new Uint8Array(out);
}
export function encodeLabel(text, entry, rows) {
  const centered = renderLabel(text, rows, entry.background);
  const width = Math.max(
    ...text
      .toUpperCase()
      .split('\n')
      .map((line) => [...line].reduce((total, char) => total + rows[char][0].length + 1, -1)),
  );
  const left = Math.floor((64 - width) / 2);
  const shifts = [[0, 0]];
  for (const x of [0, -1, 1, -2, 2]) {
    if (left + x < 1 || left + x + width > 63) continue;
    for (const y of text.includes('\n') ? [0] : [0, -1, 1, -2, 2]) if (x || y) shifts.push([x, y]);
  }
  let best;
  for (const [x, y] of shifts) {
    const pixels = x || y ? renderLabel(text, rows, entry.background, x, y) : centered;
    const data = packObj(pixels),
      packed = compress(data);
    if (!best || packed.length < best.packed.length) best = { pixels, data, packed, shift: [x, y] };
    if (packed.length <= entry.compressed_capacity) break;
  }
  need(
    best.packed.length <= entry.compressed_capacity,
    `Needs ${best.packed.length} bytes; slot holds ${entry.compressed_capacity}. Shorten the label.`,
  );
  return best;
}
export async function readImages(bytes, catalog) {
  need(
    (await sha256(bytes)) === catalog.source_rom_sha256,
    'ROM SHA-256 does not match the supported original.',
  );
  const container = ndsFiles(bytes).get(catalog.source_container);
  need(
    container && (await sha256(container)) === catalog.source_container_sha256,
    'Image container hash mismatch.',
  );
  const palette = lz10(container, catalog.palette_offset).data;
  need(palette.length === 32, 'Invalid name palette.');
  const colors = [];
  for (let p = 0; p < 32; p += 2) {
    const v = palette[p] | (palette[p + 1] << 8);
    colors.push([0, 5, 10].map((s) => Math.floor((((v >>> s) & 31) * 255) / 31)));
  }
  return { container, colors };
}
export async function readImage(game, entry) {
  const raw = lz10(game.container, entry.offset);
  need(
    raw.end - entry.offset === entry.compressed_capacity &&
      (await sha256(raw.data)) === entry.source_words_sha256,
    'Source image fingerprint mismatch.',
  );
  return unpackObj(raw.data);
}
