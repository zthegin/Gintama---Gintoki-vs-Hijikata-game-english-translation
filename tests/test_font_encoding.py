# Unofficial fan project; see RIGHTS.md.
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from font_encoding import native_glyph_map

class NativeEncodingTests(unittest.TestCase):
    def test_complete_map_matches_reconstruction(self):
        codes=native_glyph_map()
        self.assertEqual(len(codes),6953)
        self.assertEqual(len(set(codes.values())),6953)
        self.assertEqual(codes,json.loads((ROOT/'reference/glyph_codes_public.json').read_text(encoding='utf8'))['codes'])

    def test_verified_boundaries_and_corrected_readings(self):
        codes=native_glyph_map()
        self.assertEqual(codes['0x0001'],'\u3000')
        self.assertEqual(codes['0x0257'],'\u4e9c')
        self.assertEqual([codes[k] for k in ['0x0512','0x05F2','0x07D3']],['\u666f','\u514b','\u8b72'])

if __name__=='__main__':unittest.main()
