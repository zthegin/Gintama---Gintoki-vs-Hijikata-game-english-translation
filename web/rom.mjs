// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
const u16 = (data, at) => data[at] | (data[at + 1] << 8);
const u32 = (data, at) =>
  (data[at] | (data[at + 1] << 8) | (data[at + 2] << 16) | (data[at + 3] << 24)) >>> 0;
const check = (condition, message) => {
  if (!condition) throw new Error(message);
};

export function ndsFiles(bytes) {
  check(bytes.length >= 0x50, 'File is too short for an NDS header.');
  const fnt = u32(bytes, 0x40),
    fntSize = u32(bytes, 0x44);
  const fat = u32(bytes, 0x48),
    fatSize = u32(bytes, 0x4c);
  check(
    fnt && fat && fntSize >= 8 && fatSize >= 8 && fatSize % 8 === 0,
    'Missing or invalid NitroFS tables.',
  );
  check(
    fnt + fntSize <= bytes.length && fat + fatSize <= bytes.length,
    'NitroFS table extends outside the file.',
  );
  const count = u16(bytes, fnt + 6);
  check(count >= 1 && count <= 4096 && count * 8 <= fntSize, 'Invalid NitroFS directory count.');
  const result = new Map(),
    visited = new Set();
  function walk(dirId, prefix) {
    check(dirId >= 0xf000 && dirId - 0xf000 < count, 'Invalid NitroFS directory ID.');
    check(!visited.has(dirId), 'Repeated NitroFS directory.');
    visited.add(dirId);
    const table = fnt + (dirId - 0xf000) * 8;
    let pos = fnt + u32(bytes, table);
    let fileId = u16(bytes, table + 4);
    check(pos >= fnt + count * 8 && pos < fnt + fntSize, 'Invalid NitroFS name table.');
    let ended = false;
    for (let steps = 0; steps < 65536 && pos < fnt + fntSize; steps++) {
      const n = bytes[pos++];
      if (n === 0) {
        ended = true;
        break;
      }
      const length = n & 0x7f;
      check(length && pos + length <= fnt + fntSize, 'Invalid NitroFS filename.');
      const name = new TextDecoder('ascii', { fatal: true }).decode(
        bytes.subarray(pos, pos + length),
      );
      check(name && !name.includes('/') && name !== '.' && name !== '..', 'Invalid NitroFS path.');
      pos += length;
      if (n & 0x80) {
        check(pos + 2 <= fnt + fntSize, 'Truncated NitroFS directory.');
        const child = u16(bytes, pos);
        pos += 2;
        walk(child, prefix + name + '/');
      } else {
        check((fileId + 1) * 8 <= fatSize, 'Invalid NitroFS file ID.');
        const start = u32(bytes, fat + fileId * 8);
        const end = u32(bytes, fat + fileId * 8 + 4);
        check(start <= end && end <= bytes.length, 'File runs outside the ROM.');
        result.set((prefix + name).toLowerCase(), bytes.subarray(start, end));
        fileId++;
      }
    }
    check(ended, 'Unterminated NitroFS name table.');
  }
  walk(0xf000, '');
  return result;
}

export function readGameFile(bytes, name) {
  const lower = name.toLowerCase();
  if (lower.endsWith('.msb')) return { msb: bytes, cdb: null };
  check(
    lower.endsWith('.nds') || lower.endsWith('.srl'),
    'Select an .nds ROM or extracted .msb file.',
  );
  const files = ndsFiles(bytes);
  const msb = files.get('field/script/fld_scr.msb');
  check(msb, 'This ROM has no field/script/fld_scr.msb. Check the game/version.');
  return { msb, cdb: files.get('field/script/fld_scr.cdb') ?? null };
}

export async function sha256(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join('');
}
export async function verifyGame(game, reference) {
  check(
    game.msb.length >= 16 &&
      game.msb[0] === 115 &&
      game.msb[1] === 99 &&
      game.msb[2] === 114 &&
      game.msb[3] === 26,
    'Not the expected MSB format.',
  );
  check(
    (await sha256(game.msb)) === reference.source_msb_sha256,
    'MSB SHA-256 does not match the supported game version.',
  );
  if (game.cdb)
    check(
      (await sha256(game.cdb)) === reference.source_cdb_sha256,
      'CDB SHA-256 does not match the supported game version.',
    );
  return true;
}

export async function readRecord(msb, record, codes) {
  const offset = Number.parseInt(record.offset_hex, 16);
  check(
    Number.isSafeInteger(offset) && offset >= 16 && offset % 2 === 0 && offset < msb.length,
    'Invalid record offset.',
  );
  let end = offset,
    terminator = false,
    text = '',
    unknown = [],
    colorControls = [],
    controlSequence = [];
  const decoder = codes.codes;
  for (; end + 1 < msb.length; end += 2) {
    const code = u16(msb, end);
    if (code === 0xff71) {
      end += 2;
      terminator = true;
      break;
    }
    if (code === 0xff70) text += '\n';
    else if (code === 0xff72) {
      text += '\f';
      controlSequence.push(code);
    }
    else if (code === 0xff81) {
      text += '[red]';
      colorControls.push(code);
      controlSequence.push(code);
    } else if (code === 0xff82) {
      text += '[blue]';
      colorControls.push(code);
      controlSequence.push(code);
    } else if (code === 0xff84) {
      text += '[/color]';
      colorControls.push(code);
      controlSequence.push(code);
    } else if (code === 0 || code === 0x5353) {
      text += `⟦STRUCT:0x${code.toString(16).padStart(4, '0')}⟧`;
      unknown.push(code);
    } else if (code >= 0xff00) {
      text += `⟦CTRL:0x${code.toString(16).padStart(4, '0')}⟧`;
      unknown.push(code);
    } else {
      const char = decoder['0x' + code.toString(16).toUpperCase().padStart(4, '0')];
      if (char === undefined) {
        text += `⟦0x${code.toString(16).toUpperCase().padStart(4, '0')}⟧`;
        unknown.push(code);
      } else text += char;
    }
    check(end - offset <= 10000, 'Record exceeds maximum expected size.');
  }
  check(terminator && end + 2 <= msb.length && u16(msb, end) === 0, 'Malformed record terminator.');
  check(
    (await sha256(msb.subarray(offset, end))) === record.source_words_sha256,
    `Source text mismatch for ${record.id}.`,
  );
  return { text, unknown, colorControls, controlSequence, pageBreaks: text.split('\f').length - 1 };
}
