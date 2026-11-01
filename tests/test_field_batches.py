# Unofficial fan project. I do not own Gintama or the original game; see RIGHTS.md.
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from dialogue_writer import load_records
from sync_csv import render


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class FieldBatchCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.coverage = read(ROOT / 'reference/field_batch_coverage.json')
        cls.index = {row['id']: row for row in read(ROOT / 'reference/record_index.json')['records'] if row.get('kind') != 'graphic'}

    def test_every_field_record_has_one_queue(self):
        seen = set()
        for path in (ROOT / 'translations/ready').glob('*.json'):
            for row in read(path)['records']:
                self.assertNotIn(row['id'], seen)
                seen.add(row['id'])
        for batch in self.coverage['new_batches']:
            if batch['editable']:
                continue
            for row in read(ROOT / batch['file'])['records']:
                self.assertNotIn(row['id'], seen)
                seen.add(row['id'])
        self.assertEqual(seen, set(self.index))
        self.assertEqual(len(seen), self.coverage['indexed_field_records'])

    def test_new_batches_match_manifest_and_source_hashes(self):
        assignments = {row['id']: row for row in self.coverage['records']}
        self.assertEqual(len(assignments), len(self.coverage['records']))
        seen = set()
        counts = {True: 0, False: 0}
        for batch in self.coverage['new_batches']:
            path = ROOT / batch['file']
            data = read(path)
            self.assertEqual(data['batch_id'], path.stem)
            self.assertEqual(len(data['records']), batch['count'])
            self.assertLessEqual(batch['count'], 200)
            self.assertEqual((ROOT / batch['csv']).read_text(encoding='utf-8'), render(data))
            expected_folder = ROOT / ('translations/ready' if batch['editable'] else 'review/field')
            self.assertEqual(path.parent, expected_folder)
            for row in data['records']:
                self.assertNotIn(row['id'], seen)
                seen.add(row['id'])
                self.assertEqual(row['source_words_sha256'], self.index[row['id']]['source_words_sha256'])
                assignment = assignments[row['id']]
                self.assertEqual(assignment['batch'], batch['batch'])
                self.assertEqual(assignment['editable'], batch['editable'])
                if batch['editable']:
                    self.assertNotIn('review_reasons', assignment)
                    self.assertEqual(self.index[row['id']]['decode_status'], 'mapped')
                else:
                    self.assertTrue(assignment['review_reasons'])
                if 'duplicate_of' in assignment:
                    self.assertEqual(row['source_words_sha256'], self.index[assignment['duplicate_of']]['source_words_sha256'])
                counts[batch['editable']] += 1
        self.assertEqual(seen, set(assignments))
        self.assertEqual(counts[True], self.coverage['new_editable_records'])
        self.assertEqual(counts[False], self.coverage['review_records'])

    def test_review_batches_cannot_enter_writer(self):
        blocked = set()
        for batch in self.coverage['new_batches']:
            if batch['editable']:
                continue
            path = ROOT / batch['file']
            blocked.update(row['id'] for row in read(path)['records'])
            with self.assertRaisesRegex(ValueError, 'Unsupported dialogue batch'):
                load_records(root=ROOT, batch=path)
        self.assertTrue(blocked.isdisjoint(row['id'] for row in load_records(root=ROOT)))


if __name__ == '__main__':
    unittest.main()
