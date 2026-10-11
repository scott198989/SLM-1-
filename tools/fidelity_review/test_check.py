import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from tools.fidelity_review.check import validate_record, validate_package, latest_records, PASS, PARTIAL, GATES, REVIEW_CHECKS

class EvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        # Preserve synthetic evidence; callers can choose an explicitly writable test root.
        self.root=Path(tempfile.mkdtemp(prefix='fidelity-test-',dir=os.environ.get('FORGE_TEST_ARTIFACTS')))
        page=self.root/'page.png';crop=self.root/'crop.png'
        Image.new('RGB',(8,8),'white').save(page);Image.new('RGB',(4,4),'white').save(crop)
        def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        self.source={'page_id':'s01-p02','source_id':'synthetic','source_number':1,'source_sha256':'a'*64,
                     'original_page':2,'preserved_render':ref(page),'render':ref(page),'quarantine':{k:'PROHIBITED' for k in GATES}}
        self.record={k:v for k,v in self.source.items() if k not in ('render','preserved_render')}
        self.record.update(visible_fidelity_status=PASS,full_page_visible_fidelity_qualified=True,
                           unresolved_visible_content=[],downstream_approved=False,scope='visible',review_method='synthetic',
                           representation_convention='literal',review_checks={k:True for k in REVIEW_CHECKS},
                           reviewed_transcription={'upper':'Figure F-s01-p02-01','lower':'Synthetic'},preserved_page=ref(page),table_references=[])
        self.record['figures']=[{'figure_id':'F-s01-p02-01','downstream_approved':False,'description_state':'REVIEWED',
                                'reviewed_description':'Synthetic crop','visible_labels':[],'relationships':[],
                                'source_id':'synthetic','source_sha256':'a'*64,'original_page':2,'render_sha256':ref(page)['sha256'],
                                'pixel_frame':[8,8],'bbox_pixels':[0,0,4,4],'asset':ref(crop)}]
    def check(self):validate_record(self.record,self.source)
    def rejects(self):
        with self.assertRaises(ValueError):self.check()
    def test_valid_synthetic_record(self):self.check()
    def test_unresolved_page_cannot_pass(self):
        self.record['unresolved_visible_content']=['unreadable label'];self.rejects()
    def test_partial_requires_explicit_obstacle(self):
        self.record.update(visible_fidelity_status=PARTIAL,full_page_visible_fidelity_qualified=False);self.rejects()
    def test_crop_replacement_detected_even_same_dimensions(self):
        Image.new('RGB',(4,4),'black').save(self.record['figures'][0]['asset']['path']);self.rejects()
    def test_crop_out_of_page_refused(self):
        self.record['figures'][0]['bbox_pixels']=[0,0,10,4];self.rejects()
    def test_figure_wrong_source_rejected(self):
        self.record['figures'][0]['source_id']='foreign';self.rejects()
    def test_quarantine_release_rejected(self):
        self.record['quarantine']=dict(self.record['quarantine'],training='ALLOWED');self.rejects()
    def test_control_escape_error_rejected(self):
        self.record['reviewed_transcription']['upper']='bad\vvector';self.rejects()
    def test_dangling_figure_reference_rejected(self):
        self.record['reviewed_transcription']['upper']='F-s01-p02-99';self.rejects()
    def test_duplicate_revision_refused(self):
        (self.root/'pages').mkdir()
        for name in ('a.json','b.json'):(self.root/'pages'/name).write_text(json.dumps(self.record),encoding='utf8')
        with self.assertRaises(ValueError):latest_records(self.root)
    def test_broken_revision_chain_refused(self):
        (self.root/'pages').mkdir();self.record.update(review_revision=2,supersedes={'path':'absent','sha256':'0'*64})
        (self.root/'pages/a.json').write_text(json.dumps(self.record),encoding='utf8')
        with self.assertRaises(ValueError):latest_records(self.root)
    def test_revision_parent_accepts_equivalent_dotdot_path(self):
        pages=self.root/'pages';pages.mkdir();first=pages/'s01-p02.json'
        first.write_text(json.dumps(self.record),encoding='utf8')
        second=copy.deepcopy(self.record)
        second.update(review_revision=2,supersedes={'path':str(pages/'..'/'pages'/first.name),'sha256':hashlib.sha256(first.read_bytes()).hexdigest()})
        (pages/'s01-p02.rev2.json').write_text(json.dumps(second),encoding='utf8')
        self.assertEqual(latest_records(self.root)['s01-p02'][1]['review_revision'],2)
    def test_incomplete_review_attestation_refused(self):
        self.record['review_checks'].pop('reading_order_reviewed');self.rejects()
    def make_package(self):
        (self.root/'pages').mkdir();p=self.root/'pages/s01-p02.json';p.write_text(json.dumps(self.record),encoding='utf8')
        source=self.root/'source.json';source.write_text(json.dumps({'pages':[self.source],'excluded_pages':[]}),encoding='utf8')
        ledger={'pages':[{'page_id':'s01-p02','record':{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},'status':PASS,'unresolved':[],'downstream_approved':False}],
                'counts':{PASS:1,PARTIAL:0,'PENDING':0},'downstream_releases':0,'figure_occurrences':1,'excluded_pages':[]}
        (self.root/'no-silent-omission-ledger.json').write_text(json.dumps(ledger),encoding='utf8')
        self.assertEqual(validate_package(self.root,source,1)['structural_validation'],'PASS')
        return source,ledger
    def test_excluded_page_cannot_enter_package(self):
        source,_=self.make_package();source.write_text(json.dumps({'pages':[self.source],'excluded_pages':[{'source_number':1,'original_page':2}]}),encoding='utf8')
        with self.assertRaises(ValueError):validate_package(self.root,source,1)
    def test_stale_summary_count_refused(self):
        source,ledger=self.make_package();ledger['counts'][PASS]=99
        (self.root/'no-silent-omission-ledger.json').write_text(json.dumps(ledger),encoding='utf8')
        with self.assertRaises(ValueError):validate_package(self.root,source,1)

if __name__=='__main__':unittest.main()
