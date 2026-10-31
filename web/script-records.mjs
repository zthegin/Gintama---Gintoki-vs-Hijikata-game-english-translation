// Unofficial fan project. Use only legally obtained ROMs. See RIGHTS.md.
const controls = new Set([0xffa1, 0xffa2, 0xffa3, 0xffa5, 0xff81, 0xff84, 0xffb1, 0xffb2]);

export function scanScript(data, { minimumOffset = 4, label = 'script' } = {}) {
  if (data.length % 2 || ![115, 99, 114, 26].every((b, i) => data[i] === b)) {
    throw new Error(`Invalid ${label} header.`);
  }
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength), rows = [];
  let start = 4;
  for (let end = 4; end + 3 < data.length; end += 2) {
    if (view.getUint16(end, true) !== 0xff71) continue;
    if (view.getUint16(end + 2, true) !== 0) throw new Error(`Invalid ${label} record separator.`);
    let count = 0, inRun = false, supported = true;
    for (let at = start; at < end; at += 2) {
      const code = view.getUint16(at, true);
      if ((code >= 1 && code <= 6953) || code === 0xff70) {
        if (!inRun) count++;
        inRun = true;
      } else {
        if (!controls.has(code)) supported = false;
        inRun = false;
      }
    }
    if (start >= minimumOffset) rows.push({ offset: start, end: end + 2, partCount: supported ? count : 0 });
    start = end + 4;
    if (data[start] === 83 && data[start + 1] === 83) start += 2;
  }
  return rows;
}
