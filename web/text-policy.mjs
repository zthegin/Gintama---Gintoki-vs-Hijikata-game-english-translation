// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import entities from './inspection-entities.mjs';
const maxEntityLength = Math.max(...Object.keys(entities).map((name) => name.length));
const schemes =
  'http https hxxp hxxps ftp ftps sftp ssh smb javascript vbscript mailto telnet magnet ws wss ipfs intent ms-msdt'.split(
    ' ',
  );
const scheme = new RegExp(
  '(?<![a-z0-9_])(?:' + schemes.map((word) => [...word].join('\\s*')).join('|') + ')\\s*:',
  'i',
);
const domain = /(?<![\p{L}\p{N}_-])[\p{L}\p{N}_-]+(?:[ \t]*\.[ \t]*[\p{L}\p{N}_-]+)+/giu;
const suffixes = new Set(
  'com net org io gg ru xyz dev app info biz co uk me ly link site online top zip mov onion click news shop pro club live mobi world'.split(
    ' ',
  ),
);
const shorteners = new Set([
  'tiny.one',
  'short.io',
  'rebrand.ly',
  'rb.gy',
  'is.gd',
  'v.gd',
  'tiny.cc',
  't.co',
  't.ly',
  'bit.ly',
  'cutt.ly',
  'shorturl.at',
  'lnkd.in',
  'goo.gl',
  'youtu.be',
]);
const linkSyntax =
  /(?:^|[\s(\[<])\/\/[a-z0-9\[]|!?\[[^\]\n]*\]\(\s*\S|\[(?=[a-f0-9:]*:[a-f0-9:]*:)[a-f0-9:]+\]/i;
const roleMarker =
  /<\|(?:im_start|im_end|system|assistant|user|developer|eot_id|start_header_id|end_header_id|endoftext)\|>|\[\/?(?:INST|SYS|SYSTEM|DEVELOPER|ASSISTANT|TOOL)\]|<\/?(?:system|developer|assistant|tool|function_call|tool_call)(?:\s[^>]*)?>|<<\s*\/?\s*SYS\s*>>/i;

const contextUri =
  /(?:(?<![a-z0-9_])data\s*:\s*(?:[a-z][a-z0-9.+-]*\/[^,\s]+|;[^,\s]*|),|(?<![a-z0-9_])file\s*:\s*(?:[/\\]|[a-z]:|[^\s]*[./\\][^\s]+)|(?<![a-z0-9_])blob\s*:\s*(?:https?:|null\/|[a-f0-9]{8}-))/i;
const markup =
  /<\s*\/?\s*(?:script|iframe|a|img|object|embed|form|meta|style|svg|link|base|video|audio)\b/i;
const secrets =
  /(?:github_pat_[A-Za-z0-9_]{16,}|gh[pousr]_[A-Za-z0-9]{18,}|glpat-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{16,}|AIza[A-Za-z0-9_-]{30,}|(?:AKIA|ASIA)[A-Z0-9]{16}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY-----|ssh-(?:rsa|ed25519)\s+[A-Za-z0-9+/]{32,}={0,2}|eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,})/;
const hidden = /[\p{Cc}\p{Cf}\p{Cs}\u034f\u180b-\u180f\ufe00-\ufe0f\u{e0100}-\u{e01ef}]/u;
const signatures = [
  [80, 75, 3, 4],
  [80, 75, 5, 6],
  [55, 122, 188, 175, 39, 28],
  [82, 97, 114, 33],
  [31, 139],
  [66, 90, 104],
  [127, 69, 76, 70],
  [77, 90],
  [137, 80, 78, 71],
  [71, 73, 70, 56],
  [82, 73, 70, 70],
  [79, 103, 103, 83],
  [102, 76, 97, 67],
  [37, 80, 68, 70, 45],
];
const hasHidden = (value) => hidden.test(value.replace(/[\n\f]/g, ''));
const colorMarker = /\[(blue|red|\/color)\]/gi;
const colorLikeMarker = /\[(\/?(?:blue|red|color)|ff[0-9a-f]{2})(?=[\]\s]|$)[^\]]*\]?/gi;

function parseColors(value) {
  if (typeof value !== 'string') throw new Error('Dialogue markup must be text');
  for (const match of value.matchAll(colorLikeMarker)) {
    const token = match[0];
    if (!/^\[(?:blue|red|\/color)\]$/i.test(token))
      throw new Error('Malformed color marker');
  }
  let text = '', cursor = 0, opened = false;
  let spanStart = -1;
  const codes = [];
  for (const match of value.matchAll(colorMarker)) {
    text += value.slice(cursor, match.index);
    const marker = match[1].toLowerCase();
    if (marker === '/color') {
      if (!opened) throw new Error('Color close marker has no matching open marker');
      if (!value.slice(spanStart, match.index).trim())
        throw new Error('Color span must contain visible text');
      codes.push(0xff84);
      opened = false;
    } else {
      if (opened) throw new Error('Color markers cannot be nested');
      codes.push(marker === 'blue' ? 0xff82 : 0xff81);
      opened = true;
      spanStart = match.index + match[0].length;
    }
    cursor = match.index + match[0].length;
  }
  text += value.slice(cursor);
  if (opened) throw new Error('Color open marker has no matching close marker');
  return { text, codes };
}

export function stripColors(value) {
  return parseColors(value).text;
}

export function stripColorMarkers(value) {
  if (typeof value !== 'string') throw new Error('Dialogue markup must be text');
  return value.replace(colorMarker, '');
}

export function colorControls(value) {
  return parseColors(value).codes;
}

export function normalizeForInspection(value) {
  let result = value.normalize('NFKC').replace(/[\u3002\uff61]/g, '.');
  for (let i = 0; i < 3; i++) {
    if (hasHidden(result)) throw new Error('forbidden hidden/control character');
    // Decode valid percent bytes in runs; malformed escapes remain visible.
    result = result.replace(/(?:%[0-9a-f]{2})+/gi, (token) => {
      try {
        return decodeURIComponent(token);
      } catch {
        return token.replace(/%([0-7][0-9a-f])/gi, (_, n) => String.fromCharCode(parseInt(n, 16)));
      }
    });
    result = result
      .replace(/&(#x[0-9a-f]+;?|#\d+;?|[A-Za-z][A-Za-z0-9]*;?)/gi, (whole, name) => {
        if (name[0] === '#') {
          if (name.slice(1).replace(/;$/, '').length > 9) throw new Error('Invalid numeric entity');
          const n =
            name[1].toLowerCase() === 'x'
              ? parseInt(name.slice(2), 16)
              : parseInt(name.slice(1), 10);
          if (n <= 0x10ffff && hasHidden(String.fromCodePoint(n)))
            throw new Error('forbidden encoded control character');
          return n <= 0x10ffff && n > 0 && !(n >= 0xd800 && n <= 0xdfff)
            ? String.fromCodePoint(n)
            : '\ufffd';
        }
        if (Object.hasOwn(entities, name)) return entities[name];
        // HTML accepts a few legacy entities without a semicolon, including
        // prefixes such as &ampcolon; => &colon; on the next decoding pass.
        for (let n = Math.min(name.length - 1, maxEntityLength); n > 0; n--) {
          const prefix = name.slice(0, n);
          if (Object.hasOwn(entities, prefix)) return entities[prefix] + name.slice(n);
        }
        return whole;
      })
      .normalize('NFKC')
      .replace(/[\u3002\uff61]/g, '.');
  }
  return result
    .replace(/[\[({]\s*(?:colon|:)\s*[\])}]/gi, ':')
    .replace(/[\[({]\s*(?:dot|\.)\s*[\])}]/gi, '.');
}

function hasLink(value) {
  const compact = value.replace(/\s+/g, '');
  if (
    scheme.test(value) ||
    contextUri.test(value) ||
    contextUri.test(compact) ||
    linkSyntax.test(value)
  )
    return true;
  for (const match of value.matchAll(domain)) {
    const raw = match[0],
      host = raw.replace(/[ \t]/g, '').toLowerCase(),
      labels = host.split('.');
    const contiguous = raw.toLowerCase() === host,
      spacedDot = /[ \t]+\./.test(raw);
    const before = value[match.index - 1],
      after = value[match.index + raw.length];
    const fileReference =
      ['py', 'md', 'js', 'mjs', 'sh', 'ts', 'cs', 'json', 'csv', 'txt', 'html', 'css'].includes(labels.at(-1)) &&
      (['/', '\\'].includes(before) || (before === '`' && after === '`'));
    if (labels[0] === 'www' || suffixes.has(labels.at(-1)) || shorteners.has(host)) return true;
    if (
      (contiguous || spacedDot) &&
      !fileReference &&
      (/^[a-z]{2,63}$/.test(labels.at(-1)) ||
        labels.at(-1).startsWith('xn--') ||
        /[^\x00-\x7f]/.test(labels.at(-1)))
    )
      return true;
    if (labels.length === 4 && labels.every((part) => /^\d+$/.test(part) && Number(part) <= 255))
      return true;
    if (['/', ':'].includes(value[match.index + raw.length])) return true;
  }
  return false;
}
export function encodedPayload(value) {
  if (/(?<!\w)(?:(?:0x)?[0-9a-f]{2}(?:\s*,\s*|\s+)){63}(?:0x)?[0-9a-f]{2}(?!\w)/i.test(value))
    return true;
  const wrapped = [...value.matchAll(/^[ \t]*([A-Za-z0-9+/_-]{48,}={0,2})[ \t]*$/gm)];
  if (wrapped.reduce((n, m) => n + m[1].length, 0) >= 128) return true;
  const tokens = value.matchAll(
    /(?<![A-Za-z0-9+/=_-])(?:[A-Za-z0-9+/]{6,}={0,2}|[A-Za-z0-9_-]{32,})(?![A-Za-z0-9+/=_-])/g,
  );
  for (const [token] of tokens) {
    if (token.length >= 128) return true;
    const candidates = [];
    if (token.length % 2 === 0 && /^[0-9a-f]+$/i.test(token))
      candidates.push(Uint8Array.from(token.match(/../g), (b) => parseInt(b, 16)));
    try {
      const b = atob(
        token.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - (token.length % 4)) % 4),
      );
      candidates.push(Uint8Array.from(b, (c) => c.charCodeAt(0)));
    } catch {}
    if (candidates.some((data) => signatures.some((sig) => sig.every((b, i) => data[i] === b))))
      return true;
    for (const data of candidates) {
      if (data.every((byte) => byte < 128)) {
        let decodedText = String.fromCharCode(...data);
        if (token.length < 16)
          decodedText = [...decodedText].filter((c) => !hasHidden(c)).join('');
        const decoded = normalizeForInspection(decodedText);
        if (hasLink(decoded) || roleMarker.test(decoded) || markup.test(decoded) || secrets.test(decoded))
          return true;
      }
    }
  }
  return false;
}

export function checkSafeText(value, label = 'Text', limit = 2500) {
  if (value === null) return;
  if (typeof value !== 'string' || !value.trim() || [...value].length > limit)
    throw new Error(`${label}: expected nonempty text of at most ${limit} characters or null`);
  const stripped = stripColorMarkers(value);
  for (const candidate of new Set([value, stripped])) {
    const inspected = normalizeForInspection(candidate);
    for (const visible of new Set([inspected, stripColorMarkers(inspected)])) {
      if (hasHidden(candidate) || hasHidden(visible))
        throw new Error(`${label}: forbidden hidden/control character`);
      if (hasLink(visible) || markup.test(visible))
        throw new Error(`${label}: links/active markup are not allowed`);
      if (roleMarker.test(visible)) throw new Error(`${label}: reserved instruction/role marker`);
      if (secrets.test(visible)) throw new Error(`${label}: possible credential material`);
      if (encodedPayload(visible)) throw new Error(`${label}: possible encoded binary/data payload`);
      if (visible.includes('⟦0x')) throw new Error(`${label}: unresolved source glyph marker`);
    }
  }
}

export function checkRecordText(record) {
  checkSafeText(record.english, `${record.id}.english`);
  if (record.english !== null) stripColors(record.english);
  checkSafeText(record.translator_note, `${record.id}.translator_note`, 500);
}

export function finiteJson(_key, value) {
  if (typeof value === 'number' && !Number.isFinite(value))
    throw new Error('Non-finite JSON number');
  return value;
}

export function parseStrictJson(text, maxBytes = 2000000) {
  if (typeof text !== 'string' || new TextEncoder().encode(text).length > maxBytes)
    throw new Error('Oversized JSON input');
  const value = JSON.parse(text, finiteJson),
    stack = [];
  // JSON.parse has already checked grammar; this second pass only tracks keys.
  for (const [token] of text.matchAll(
    /"(?:\\[\s\S]|[^"\\])*"|[{}\[\]:,]|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g,
  )) {
    if (token === '{') stack.push({ keys: new Set(), key: true });
    else if (token === '[') stack.push(null);
    else if (token === '}' || token === ']') stack.pop();
    else if (token === ',' && stack.at(-1)) stack.at(-1).key = true;
    else if (token[0] === '"' && stack.at(-1)?.key) {
      const current = stack.at(-1),
        key = JSON.parse(token);
      if (current.keys.has(key)) throw new Error(`Duplicate JSON key: ${key}`);
      current.keys.add(key);
      current.key = false;
    }
  }
  return value;
}
