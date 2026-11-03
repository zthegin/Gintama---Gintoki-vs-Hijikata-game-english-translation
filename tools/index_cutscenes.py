# Unofficial fan tools. I do not own Gintama or the original game.
# Use only your legally obtained ROM. See RIGHTS.md.
"""Reproduce the cutscene inventory without exporting source words or Japanese."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from battle_writer import scan
from image_workflow import nds_files, read_rom, sha, require


def inventory(source):
    files = nds_files(source)
    scripts = []
    for name in sorted(files):
        if not name.startswith('adventure/script/') or not name.endswith('.msb'):
            continue
        cdb = name[:-3] + 'cdb'
        require(cdb in files, 'Cutscene script has no matching control file')
        data = source[slice(*files[name])]
        records = [row for row in scan(data) if row['offset'] >= (16 if name.endswith('/s01.msb') else 4)]
        scripts.append({'script': name, 'source_msb_sha256': sha(data),
                        'source_cdb_sha256': sha(source[slice(*files[cdb])]),
                        'records': [[row['offset'], row['end'], row['source_words_sha256'], len(row['runs'])] for row in records]})
    return {'format': 'gintama-cutscene-index-v1', 'source_rom_sha256': sha(source), 'scripts': scripts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(args.out.suffix == '.json' and not args.out.exists(), 'Choose a new JSON output path')
    data = inventory(read_rom(args.rom))
    with args.out.open('x', encoding='utf-8') as output:
        output.write(json.dumps(data, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
