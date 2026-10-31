// Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
// I do not own Gintama or the original game. No affiliation or endorsement is implied.
// Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
export function draftKey(namespace, hash, id) {
  return `${namespace}:${hash}:${id}`;
}

export function readDraft(storage, namespace, hash, id) {
  const current = storage.getItem(draftKey(namespace, hash, id));
  if (current !== null) return current;

  // Earlier editors used a release number in the key. Leave those drafts intact.
  const prefix = `${namespace}-v`;
  const suffix = `:${hash}:${id}`;
  let newest = -1;
  let previous = null;
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (!key || !key.startsWith(prefix) || !key.endsWith(suffix)) continue;
    const version = key.slice(prefix.length, -suffix.length);
    if (!/^\d+$/.test(version)) continue;
    const number = Number(version);
    if (Number.isSafeInteger(number) && number > newest) {
      newest = number;
      previous = key;
    }
  }
  return previous === null ? null : storage.getItem(previous);
}
