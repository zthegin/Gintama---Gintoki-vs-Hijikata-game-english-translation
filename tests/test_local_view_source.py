# Unofficial fan project; see RIGHTS.md. These fixtures contain no game data.
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import local_view


def packed(words):
    return struct.pack('<' + 'H' * len(words), *words)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SourcePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'reference').mkdir()
        self.msb = self.root / 'source.msb'
        self.batch = self.root / 'batch.json'

    def fixture(self, words, *, termination='end', trailing_controls=None):
        terminator = 0 if termination == 'nul' else 0xFF71
        stop = words.index(terminator) + 1
        span = packed(words[:stop])
        raw = b'scr\x1a' + b'\0' * 12 + packed(words)
        self.msb.write_bytes(raw)
        row = {'id': 'msb_00000010', 'source_words_sha256': digest(span),
               'offset_hex': '0x10', 'decode_status': 'mapped', 'termination': termination}
        if trailing_controls is not None:
            row['trailing_controls'] = trailing_controls
        self.index = {'source_msb_sha256': digest(raw), 'records': [row]}
        self.write_index()
        (self.root / 'reference/glyph_codes_public.json').write_text(json.dumps({'codes': {'0x0001': 'A', '0x0002': 'B'}}))
        self.batch.write_text(json.dumps({'records': [{'id': row['id'],
            'source_words_sha256': row['source_words_sha256'],
            'english': 'English', 'translator_note': None}]}))

    def write_index(self):
        (self.root / 'reference/record_index.json').write_text(json.dumps(self.index))

    def collect(self):
        return local_view.collect_source(self.msb, self.batch, root=self.root)

    def test_nul_stops_before_neighbor_string_and_end_marker(self):
        self.fixture([1, 0, 2, 0xFF71, 0], termination='nul')
        self.assertEqual(self.collect()[0]['japanese'], 'A')

    def test_legacy_end_record_and_named_controls(self):
        self.fixture([1, 0xFF70, 0xFF81, 2, 0xFF84, 0xFF72, 1, 0xFF71, 0])
        self.assertEqual(self.collect()[0]['japanese'], 'A\n[red]B[/color]\fA')

    def test_supported_numeric_controls_remain_explicit(self):
        controls = [0xFF83, 0xFFA1, 0xFFA2, 0xFFA3, 0xFFA5, 0xFFB1, 0xFFB2]
        self.fixture([1] + controls + [0xFF71, 0])
        expected = 'A' + ''.join(f'[ctrl:{code:04X}]' for code in controls)
        self.assertEqual(self.collect()[0]['japanese'], expected)

    def test_native_color_transitions_can_be_shown_as_exact_raw_tags(self):
        self.fixture([0xFF81, 0xFF82, 1, 0xFF84, 2, 0xFF84, 0xFF71, 0])
        self.index['records'][0]['raw_color_controls'] = True
        self.write_index()
        self.assertEqual(self.collect()[0]['japanese'],
            '[ctrl:FF81][ctrl:FF82]A[ctrl:FF84]B[ctrl:FF84]')
        self.index['records'][0]['raw_color_controls'] = 1
        self.write_index()
        with self.assertRaisesRegex(ValueError, 'Invalid raw color control metadata'):
            self.collect()

    def test_wrong_original_file_hash_is_rejected(self):
        self.fixture([1, 0, 2], termination='nul')
        self.msb.write_bytes(self.msb.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'Original dialogue hash mismatch'):
            self.collect()

    def test_batch_and_span_hashes_both_checked(self):
        self.fixture([1, 0, 2], termination='nul')
        data = json.loads(self.batch.read_text())
        data['records'][0]['source_words_sha256'] = '0' * 64
        self.batch.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.collect()
        self.index['records'][0]['source_words_sha256'] = '0' * 64
        self.write_index()
        with self.assertRaisesRegex(ValueError, 'Source span hash mismatch'):
            self.collect()

    def test_protected_dynamic_tail_is_hashed_but_not_displayed(self):
        self.fixture([1, 0xFF70, 0xFF81, 0, 2], termination='nul', trailing_controls=[0xFF81])
        self.assertEqual(self.collect()[0]['japanese'], 'A\n')
        self.index['records'][0]['trailing_controls'] = [0xFF82]
        self.write_index()
        with self.assertRaisesRegex(ValueError, 'Unsupported protected dialogue suffix'):
            self.collect()

    def test_protected_tail_must_match_actual_source(self):
        self.fixture([1, 2, 0], termination='nul', trailing_controls=[0xFF81])
        with self.assertRaisesRegex(ValueError, 'Protected dialogue suffix changed'):
            self.collect()

    def test_unknown_glyph_and_control_are_rejected(self):
        for code in (3, 0xFF99):
            with self.subTest(code=code):
                self.fixture([code, 0xFF71, 0])
                with self.assertRaisesRegex(ValueError, 'Unresolved source glyph or control'):
                    self.collect()

    def test_legacy_zip_does_not_accept_migrated_span_hash(self):
        self.fixture([1, 0, 2], termination='nul')
        archive = self.root / 'old-extraction.zip'
        with zipfile.ZipFile(archive, 'x') as output:
            output.writestr('all_records.json', json.dumps({'records': [{
                'id': 'msb_00000010', 'source_words_sha256': 'f' * 64,
                'japanese': 'old span', 'decode_status': 'mapped'}]}))
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            local_view.collect(archive, self.batch)

    def test_cli_source_inputs_are_mutually_exclusive(self):
        result = subprocess.run([sys.executable, '-B', local_view.__file__,
            '--msb', 'a.msb', '--zip', 'a.zip', '--batch', 'batch.json', '--out', 'out.html'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('not allowed with argument', result.stderr)


if __name__ == '__main__':
    unittest.main()
