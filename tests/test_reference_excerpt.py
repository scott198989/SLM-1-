"""Synthetic release boundary checks; no course content or evaluation gold."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from forge_data.citation_pilot import build, PROSE_PROFILE, PROSE_POLICY, sha
from forge_data.reference_excerpt import request


class ReferenceExcerptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.text = 'Reviewed planning checklist.\nRead the task and state assumptions.\n'
        (self.root/'source.txt').write_bytes(self.text.encode())
        (self.root/'decision.json').write_bytes(b'{"private_reference":true}\n')
        self.chunk = {
            'id':'synthetic-selected-excerpt','family_id':'reference-family','text':self.text,
            'keywords':'synthetic-selected-excerpt',
            'source':{'path':'source.txt','sha256':sha(self.text.encode()),'slice_sha256':sha(self.text.encode()),'start_line':1,'end_line':2},
            'quality_state':'VALIDATED','rights_disposition':'PRIVATE_PROJECT_REFERENCE_AUTHORIZED',
            'visual_status':'NOT_APPLICABLE','use_policy':dict(PROSE_POLICY),
            'evidence_assets':[{'path':'decision.json','sha256':sha((self.root/'decision.json').read_bytes())}],
        }
        self.index = self.root/'index.sqlite'; self.manifest = self.root/'manifest.json'

    def release(self, chunks=None):
        build(self.root,self.index,self.manifest,chunks or [self.chunk],{'gold-family'},profile=PROSE_PROFILE)
        self.pin = sha(self.manifest.read_bytes())

    def call(self, task='quote_reference', **kw):
        return request(self.index,self.manifest,expected_manifest_sha256=self.pin,task=task,**kw)

    def test_search_does_not_answer_a_question(self):
        self.release()
        result = self.call('find_reference',query='What assumptions prove the task is correct?')
        self.assertEqual(result['status'],'REFERENCE_CANDIDATES')
        self.assertIsNone(result['answer'])
        self.assertFalse(result['generator_used'])

    def test_explicit_selection_returns_exact_cited_bytes(self):
        self.release()
        result = self.call(chunk_id=self.chunk['id'])
        self.assertEqual(result['quote'].encode(),(self.root/'source.txt').read_bytes())
        self.assertEqual(result['citation']['source'],self.chunk['source'])

    def test_absent_reference_and_unsupported_tasks_abstain(self):
        self.release()
        for task in ['calculate','answer_question','media_transcript','train']:
            self.assertEqual(self.call(task,query='planning checklist')['status'],'NO_ANSWER')
        self.assertEqual(self.call(chunk_id='unreleased')['status'],'NO_ANSWER')
        self.assertEqual(self.call('find_reference',query='zzzzquux')['status'],'NO_ANSWER')

    def test_one_chunk_limit_prevents_bulk_release(self):
        another = copy.deepcopy(self.chunk);another['id']='two'
        with self.assertRaisesRegex(ValueError,'exactly_one_chunk'):
            self.release([self.chunk,another])
        self.assertFalse(self.index.exists())

    def test_gold_family_remains_blocked(self):
        self.chunk['family_id']='gold-family'
        with self.assertRaisesRegex(ValueError,'sealed_family'):
            self.release()

    def test_training_or_missing_evidence_rejected(self):
        self.chunk['use_policy']['training']=True
        with self.assertRaisesRegex(ValueError,'policy_or_evidence'):
            self.release()
        self.chunk['use_policy']=dict(PROSE_POLICY)
        self.chunk['evidence_assets']=[]
        with self.assertRaisesRegex(ValueError,'policy_or_evidence'):
            self.release()

    def test_changed_authority_receipt_is_rejected_on_quotation(self):
        self.release();(self.root/'decision.json').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'asset_hash_or_scope_drift'):
            self.call(chunk_id=self.chunk['id'])

    def test_changed_source_or_manifest_is_rejected(self):
        self.release();(self.root/'source.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source_hash_drift'):
            self.call(chunk_id=self.chunk['id'])
        (self.manifest).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'manifest_anchor_drift'):
            self.call(chunk_id=self.chunk['id'])

    def test_index_drift_and_sidecars_rejected(self):
        self.release()
        original=self.index.read_bytes()
        self.index.write_bytes(original+b'drift')
        with self.assertRaisesRegex(ValueError,'index_drift'):
            self.call(chunk_id=self.chunk['id'])
        self.index.write_bytes(original)
        Path(str(self.index)+'-wal').write_bytes(b'sidecar')
        with self.assertRaisesRegex(ValueError,'sidecar_present'):
            self.call(chunk_id=self.chunk['id'])

    def test_legacy_calculator_profile_not_mislabeled_prose(self):
        build(self.root,self.index,self.manifest,[self.chunk],{'gold-family'})
        self.pin=sha(self.manifest.read_bytes())
        with self.assertRaisesRegex(ValueError,'prose_profile_required'):
            self.call(chunk_id=self.chunk['id'])


if __name__ == '__main__':
    unittest.main()
