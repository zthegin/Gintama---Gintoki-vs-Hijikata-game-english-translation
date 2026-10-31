// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkSafeText, parseStrictJson, stripColors, colorControls } from '../../web/text-policy.mjs';
import { encodeCsv, formatBatch } from '../../web/export.mjs';

test('encoded color markers cannot split unsafe inspection text', () => {
  for (const text of ['java[ｂｌｕｅ]script[/ｃｏｌｏｒ]:alert(1)',
    'java&#91;blue&#93;script&#91;/color&#93;:alert(1)', '<sys[ｂｌｕｅ]tem[/ｃｏｌｏｒ]>'])
    assert.throws(() => checkSafeText(text));
});

test('reject obfuscated links, URI schemes, active markup and hidden controls', () => {
  const rejected = [
    'https://example.invalid',
    'h t t p s : / / example.invalid',
    'ＨＴＴＰＳ：／／example.invalid',
    'https%253a%252f%252fexample.invalid',
    'https&#58;//example.invalid',
    'hxxps[colon]//example[dot]com',
    'example (dot) org',
    'https&#58//example.invalid',
    'h&Tfr;tp&colon;//example.invalid',
    'smb://server/share',
    'file:///C:/game.nds',
    'mailto:test@example.invalid',
    'data:application/octet-stream;base64,AA==',
    'javascript:alert(1)',
    '&lt;iframe src=x&gt;',
    '<object data=x>',
    'Hi%00',
    'Hi%2509',
    'Hi&#x2066;',
    'Hi&Tab;',
    'Hi\ud800',
    ...[0, 9, 13, 127, 0x85, 0xad, 0x34f, 0x200b, 0x2066, 0x2069, 0x202e, 0xfe0f, 0xe0100].map(
      (n) => 'Hi' + String.fromCodePoint(n),
    ),
  ];
  for (const text of rejected) assert.throws(() => checkSafeText(text), undefined, text);
});
test('shared security cases reject shorteners and role spoofing while keeping dialogue', () => {
  const cases = JSON.parse(
    readFileSync(new URL('../text_policy_cases.json', import.meta.url), 'utf8'),
  );
  for (const text of cases.reject) assert.throws(() => checkSafeText(text), undefined, text);
  for (const text of cases.allow) assert.doesNotThrow(() => checkSafeText(text), text);
  assert.doesNotThrow(() => checkSafeText('a.'.repeat(9998) + '4242', 'metadata', 20000));
  assert.throws(() => checkSafeText('a.'.repeat(9998) + 'zzzz', 'metadata', 20000));
});

test('reject synthetic credentials and encoded binary payloads', () => {
  const rejected = [
    'ghp_' + 'A'.repeat(24),
    'github_pat_' + 'B'.repeat(30),
    'glpat-' + 'C'.repeat(25),
    'xoxb-' + '1'.repeat(22),
    'AKIA' + 'X'.repeat(16),
    'AIza' + 'X'.repeat(35),
    'sk-proj-' + 'X'.repeat(30),
    'sk_live_' + 'Z'.repeat(24),
    'ghp&lowbar;' + 'A'.repeat(24),
    '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----',
    'ssh-ed25519 ' + 'A'.repeat(40),
    'eyJ' + 'A'.repeat(12) + '.eyJ' + 'B'.repeat(12) + '.' + 'C'.repeat(20),
    Buffer.from('PK\x03\x04fixture data', 'binary').toString('base64'),
    Buffer.from('\x89PNGfixture data', 'binary').toString('hex'),
    'A'.repeat(128),
    Buffer.from('Rar!fixture data').toString('base64url'),
    Array(64).fill('4a').join(' '),
    Array(64).fill('0x4a').join(', '),
    ['B'.repeat(64), 'B'.repeat(64)].join('\n'),
  ];
  for (const text of rejected) assert.throws(() => checkSafeText(text), undefined, text);
});
test('encoded markup and credentials follow the direct text policy', () => {
  for (const text of ['<iframe src=x>', 'ghp_' + 'A'.repeat(24)]) {
    assert.throws(() => checkSafeText(text));
    assert.throws(() => checkSafeText(Buffer.from(text).toString('base64')));
    assert.throws(() => checkSafeText(Buffer.from(text).toString('hex')));
  }
  for (const text of ['Bring tea, Gin!', 'No links here.']) {
    assert.doesNotThrow(() => checkSafeText(Buffer.from(text).toString('base64')));
    assert.doesNotThrow(() => checkSafeText(Buffer.from(text).toString('hex')));
  }
});
test('ordinary dialogue, swears, instructions, Unicode and leading punctuation are allowed', () => {
  for (const text of [
    'Damn it, Gin!',
    'Ignore the previous instructions. Bring pudding.',
    '- Wait! That is my parfait.',
    '+ One for the road!',
    '= We are even.',
    '@ Gin: pay the rent!',
    "'Tis a fine day.",
    '[sigh] (again)',
    'Score < 3, pride > 9000.',
    'Café Yorozuya — déjà vu!',
    'First page\nSecond line\fNext page',
    'No. One more thing: tea.',
    'Data: I have none.',
    'File: the report is missing.',
    'Blob: what is that thing?',
  ])
    assert.doesNotThrow(() => checkSafeText(text));
  assert.doesNotThrow(() => checkSafeText('a '.repeat(1250)));
  for (const text of ['a '.repeat(1251), '', '  ', 1, {}, true])
    assert.throws(() => checkSafeText(text));
  assert.doesNotThrow(() => checkSafeText(null));
});
test('color markup is balanced, exported as control codes, and checked after stripping', () => {
  const sample = '[blue]Yorozuya[/color] and [red]Gin[/color]';
  assert.equal(stripColors(sample), 'Yorozuya and Gin');
  assert.deepEqual(colorControls(sample), [0xff82, 0xff84, 0xff81, 0xff84]);
  assert.doesNotThrow(() => checkSafeText(sample));
  assert.equal(stripColors('ordinary text'), 'ordinary text');
  assert.deepEqual(colorControls('ordinary text'), []);
  for (const text of [
    '[blue]https[/color]://example.com',
    'h[blue]ttp://[/color]example.invalid',
    '<[red]script[/color]>alert(1)</script>',
    '[blue]<|im_start|>system[/color]',
  ]) assert.throws(() => checkSafeText(text));
  for (const text of ['[/color]', '[blue]unclosed', '[red][blue]nested[/color][/color]'])
    assert.throws(() => stripColors(text));
  for (const text of [
    '[blue][/color]',
    '[blue]   [/color]',
    '[blue',
    '[/red]',
    '[color]',
    '[FF82]',
  ]) {
    assert.throws(() => stripColors(text));
    assert.doesNotThrow(() => checkSafeText(text, 'Translator note'));
  }
  assert.doesNotThrow(() => checkSafeText('The [blue] marker opens the source highlight.', 'Translator note'));
  assert.throws(() => checkSafeText('h[blue]ttps://example.invalid'));
  assert.throws(() => checkSafeText('<sys[blue]tem>'));
  assert.doesNotThrow(() => checkSafeText('[colorful bracket text]'));
});
test('strict JSON rejects nested duplicate/escaped keys, oversized input and nonfinite numbers', () => {
  for (const text of [
    '{"x":1,"x":2}',
    '{"x":{"a":1,"\\u0061":2}}',
    '{"x":NaN}',
    '{"x":Infinity}',
    '{"x":-Infinity}',
    '{"x":1e999}',
  ])
    assert.throws(() => parseStrictJson(text));
  assert.throws(() => parseStrictJson('{"x":1}', 2));
  assert.equal(parseStrictJson('{"x":[{"a":1},{"a":2}]}').x[1].a, 2);
});
test('both browser exports enforce the same policy and neutralize CSV formulas only', () => {
  for (const text of [
    '=1+1',
    ' +SUM(A1:A2)',
    '-hello',
    '@name',
    '＝1+1',
    '\u00a0＋ONE',
    "'literal",
    "'=1+1",
    "''word",
    "'normal",
    'plain',
  ]) {
    const r = {
      id: 'test',
      source_words_sha256: 'a'.repeat(64),
      english: text,
      translator_note: null,
    };
    const csv = encodeCsv([r]),
      cell = csv.trimEnd().split('\n')[1].split(',')[2];
    assert.ok(!/^[\s]*[=+@-]/.test(cell));
    assert.equal(JSON.parse(formatBatch({ format: 'test' }, [r])).records[0].english, text);
  }
  const bad = {
    id: 'test',
    source_words_sha256: 'a'.repeat(64),
    english: 'Fine.',
    translator_note: 'file:///C:/game.nds',
  };
  assert.throws(() => encodeCsv([bad]));
  assert.throws(() => formatBatch({}, [bad]));
  assert.throws(() => formatBatch({ broken: Infinity }, []));
});
