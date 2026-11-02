// Unofficial fan project. I do not own Gintama or the original game; see RIGHTS.md.
import test from 'node:test';
import assert from 'node:assert/strict';
import { stripColors, colorControls } from '../../web/text-policy.mjs';
import { checkDialogue, fieldControlSequence } from '../../web/export.mjs';
import { readRecord, sha256 } from '../../web/rom.mjs';
const row = (english) => ({id:'msb_00000010', source_words_sha256:'a'.repeat(64), english, translator_note:null});

test('verified inline controls remain ordered through page and color spans', () => {
  const text = '[ctrl:FFA1]Hi [ctrl:FF83]there[/color].\f[ctrl:FFB1]Bye.[ctrl:FFB2]';
  const sequence = [0xffa1,0xff83,0xff84,0xff72,0xffb1,0xffb2];
  assert.equal(stripColors(text), 'Hi there.\fBye.');
  assert.deepEqual(colorControls(text), [0xff83,0xff84]);
  assert.deepEqual(fieldControlSequence(text), sequence);
  const meta = {page_breaks:1, control_sequence:sequence};
  assert.doesNotThrow(() => checkDialogue(row(text), meta));
  for (const bad of [text.replace('[ctrl:FFA1]',''), text.replace('[ctrl:FFB1]','[ctrl:FFA2]')])
    assert.throws(() => checkDialogue(row(bad), meta), /source colors/);
  assert.throws(() => checkDialogue(row(text), {page_breaks:1,color_controls:[0xff83,0xff84]}), /matching game file/);
});

test('unsupported and unbalanced control markup fails rather than becoming text', () => {
  for (const text of ['[ctrl:FF91]x', '[ctrl:FFFF]x', '[ctrl:FFA1', '[ctrl FFA1]x',
    '[ctrl:FF83]x', '[ctrl:FF83][/color]', '[blue][ctrl:FF83]x[/color][/color]'])
    assert.throws(() => stripColors(text));
  assert.equal(stripColors('[red]Hi[/color]'), 'Hi');
});

test('local reader recognizes only verified single-word native controls', async () => {
  const words=[0xffa1,0xff83,1,0xff84,0xff72,0xffb1,1,0xffb2,0xff71,0];
  const raw=new Uint8Array(16+words.length*2);
  words.forEach((word,i)=>{raw[16+i*2]=word&255;raw[17+i*2]=word>>>8;});
  const metadata={id:'msb_00000010',offset_hex:'0x10',source_words_sha256:await sha256(raw.subarray(16,raw.length-2))};
  const result=await readRecord(raw,metadata,{codes:{'0x0001':'A'}});
  assert.equal(result.text,'[ctrl:FFA1][ctrl:FF83]A[/color]\f[ctrl:FFB1]A[ctrl:FFB2]');
  assert.deepEqual(result.unknown,[]);
  assert.deepEqual(result.controlSequence,[0xffa1,0xff83,0xff84,0xff72,0xffb1,0xffb2]);
});

test('NUL prefixes hash their terminator and never read adjacent choice data', async () => {
  for (const suffix of [[], [0xff81]]) {
    const words=[1, ...suffix, 0];
    const raw=new Uint8Array(16+words.length*2+6);
    words.forEach((w,i)=>{raw[16+i*2]=w&255;raw[17+i*2]=w>>>8;});
    raw.set([0x53,0x53,0,0,2,0],16+words.length*2);
    const meta={id:'msb_00000010',offset_hex:'0x10',termination:'nul',trailing_controls:suffix,
      source_words_sha256:await sha256(raw.subarray(16,16+words.length*2))};
    const result=await readRecord(raw,meta,{codes:{'0x0001':'A'}});
    assert.equal(result.text,'A');
    assert.deepEqual(result.unknown,[]);
    assert.deepEqual(result.controlSequence,[]);
    await assert.rejects(readRecord(raw,{...meta,source_words_sha256:'0'.repeat(64)},{codes:{'0x0001':'A'}}), /mismatch/);
    await assert.rejects(readRecord(raw,{...meta,termination:'invalid'},{codes:{'0x0001':'A'}}), /termination/);
  }
});

test('NUL reader refuses empty, unterminated or mismatched protected tails', async () => {
  const empty=new Uint8Array(20);
  await assert.rejects(readRecord(empty,{offset_hex:'0x10',termination:'nul'},{codes:{}}), /terminator/);
  const missing=new Uint8Array(24);missing.set([1,0,1,0,1,0,1,0],16);
  await assert.rejects(readRecord(missing,{offset_hex:'0x10',termination:'nul'},{codes:{'0x0001':'A'}}), /terminator/);
  const wrongTail=new Uint8Array(22);wrongTail.set([1,0,0x82,0xff,0,0],16);
  await assert.rejects(readRecord(wrongTail,{offset_hex:'0x10',termination:'nul',trailing_controls:[0xff81]},{codes:{'0x0001':'A'}}), /suffix/);
  assert.throws(()=>checkDialogue(row('A'),{page_breaks:0,termination:'invalid'}), /termination/);
});

test('flat native color transitions use raw tags while aliases stay balanced', async () => {
  const words=[0xffa3,0xff70,0xff81,0xff82,1,0xff84,1,0xff84,0xff71,0];
  const raw=new Uint8Array(16+words.length*2);
  words.forEach((w,i)=>{raw[16+i*2]=w&255;raw[17+i*2]=w>>>8;});
  const sequence=[0xffa3,0xff81,0xff82,0xff84,0xff84];
  const metadata={id:'msb_00000010',offset_hex:'0x10',raw_color_controls:true,page_breaks:0,
    control_sequence:sequence,source_words_sha256:await sha256(raw.subarray(16,raw.length-2))};
  const result=await readRecord(raw,metadata,{codes:{'0x0001':'A'}});
  assert.equal(result.text,'[ctrl:FFA3]\n[ctrl:FF81][ctrl:FF82]A[ctrl:FF84]A[ctrl:FF84]');
  assert.deepEqual(result.unknown,[]);
  assert.deepEqual(result.controlSequence,sequence);
  assert.doesNotThrow(()=>checkDialogue(row(result.text),metadata));
  assert.throws(()=>checkDialogue(row(result.text.replace('[ctrl:FF81]','')),metadata),/source colors/);
  assert.throws(()=>stripColors('[red][blue]A[/color][/color]'),/nested/);
  assert.throws(()=>stripColors('[ctrl:FF85]A'),/Unsupported/);
  assert.throws(()=>checkDialogue(row('ht[ctrl:FF81]tps://example.com'),metadata));
  await assert.rejects(readRecord(raw,{...metadata,raw_color_controls:'yes'},{codes:{'0x0001':'A'}}),/flag/);
});

test('NUL menu export keeps explicit source line limits while dialogue stays three-line capable', () => {
  const menu={termination:'nul',page_breaks:0,line_breaks:0,control_sequence:[]};
  assert.doesNotThrow(()=>checkDialogue(row('One line.'),menu));
  assert.throws(()=>checkDialogue(row('One.\nTwo.'),menu),/menu line count/);
  assert.throws(()=>checkDialogue(row('One line.'),{termination:'nul',page_breaks:0,control_sequence:[]}),/metadata/);
  assert.doesNotThrow(()=>checkDialogue(row('One.\nTwo.'),{...menu,line_breaks:1}));
  assert.doesNotThrow(()=>checkDialogue(row('One.\nTwo.\nThree.'),{page_breaks:0,line_breaks:0,control_sequence:[]}));
});
