"""Synthetic-only tests for the pinned nine-reference catalog wrapper."""
import copy
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('catalog_under_test',REPO/'tools/academic_references/reference_catalog.py')
catalog=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalog)


class ReferenceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);runtime=self.root/'accepted';runtime.mkdir()
        for name in ['citation_pilot','reference_excerpt']:
            shutil.copyfile(REPO/'src/forge_data'/(name+'.py'),runtime/(name+'.py'))
        (runtime/'__init__.py').write_bytes(b'')
        self.runtime={name:self.pin(runtime/(name+'.py')) for name in ['__init__','citation_pilot','reference_excerpt']}
        request=catalog.captured_runtime(self.runtime)
        cp=sys.modules[request.__module__.rsplit('.',1)[0]+'.citation_pilot']
        self.entries=[]
        (self.root/'acceptance.json').write_text('{"accepted":true}\n',encoding='utf-8')
        for i in range(9):
            folder=self.root/str(i);folder.mkdir();text=f'Synthetic exact source {i}.\n'
            (folder/'source.txt').write_text(text,encoding='utf-8',newline='')
            (folder/'evidence.json').write_text('{"synthetic":true}\n',encoding='utf-8')
            chunk={'id':f'chunk-{i}','family_id':'reference-family','text':text,'keywords':f'chunk-{i} topic{i} shared',
              'source':{'path':'source.txt','sha256':self.pin(folder/'source.txt')['sha256'],'slice_sha256':self.pin(folder/'source.txt')['sha256'],'start_line':1,'end_line':1},
              'quality_state':'VALIDATED','rights_disposition':'PRIVATE_PROJECT_REFERENCE_AUTHORIZED','visual_status':'NOT_APPLICABLE',
              'use_policy':dict(cp.PROSE_POLICY),'evidence_assets':[{'path':'evidence.json','sha256':self.pin(folder/'evidence.json')['sha256']}],
              'scientific_scope_note':'Synthetic qualification must survive.'}
            note={'type':'SEPARATE_REVIEWED_ANNOTATION_NOT_SOURCE_QUOTATION','markdown':f'Separate annotation {i}; retain limits.',
                  'corroborating_sources':[{'title':'Synthetic source','url':'https://example.invalid/source'}]}
            if i>=5:chunk['scientific_assumptions']=note
            (folder/'approved.json').write_text(json.dumps(chunk),encoding='utf-8')
            cp.build(folder,folder/'index.sqlite',folder/'manifest.json',[chunk],{'sealed-gold'},profile=cp.PROSE_PROFILE)
            self.entries.append({'id':f'ref-{i}','label':f'Reference {i}','scope':'Synthetic scope','topics':[f'topic{i}'],'source_title':'Synthetic','page':i+1,
               'data_root':str(folder),'chunk_id':chunk['id'],'manifest':self.pin(folder/'manifest.json'),'index':self.pin(folder/'index.sqlite'),
               'approved_chunk':self.pin(folder/'approved.json'),'dependency_pins':[],
               'reviewed_annotation_required':i>=5,'annotation_sha256':hashlib.sha256(note['markdown'].encode()).hexdigest() if i>=5 else None})
        self.data={'schema':'forge.nine-reference-catalog.v1','entries':self.entries,'runtime':self.runtime,
           'acceptance_evidence':[self.pin(self.root/'acceptance.json')],'acceptance':{'status':'SYNTHETIC'},'capabilities':{'calculation_prototype':'separate','general_qwen_generation':'unavailable'}}
        self.path=self.root/'catalog.json';self.repin()

    def pin(self,path):
        b=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}

    def repin(self):
        self.path.write_text(json.dumps(self.data),encoding='utf-8');self.anchor=self.pin(self.path)['sha256']

    def call(self,action='catalog',**kwargs):
        return catalog.lookup(self.path,self.anchor,action,**kwargs)

    def test_catalog_and_metadata_filter(self):
        self.assertEqual(len(self.call()['entries']),9)
        self.assertEqual([e['id'] for e in self.call(query='topic4')['entries']],['ref-4'])
        self.assertEqual(self.call(query='no-match')['entries'],[])

    def test_search_fans_out_without_merging_or_answering(self):
        all_hits=self.call('find',query='shared')
        self.assertEqual([r['catalog_id'] for r in all_hits['results']],[f'ref-{i}' for i in range(9)])
        self.assertIsNone(all_hits['answer']);self.assertFalse(all_hits['calculation_performed'])
        self.assertEqual([r['catalog_id'] for r in self.call('find',query='topic7')['results']],['ref-7'])
        self.assertEqual(self.call('find',query='zzzzquux')['status'],'NO_REFERENCE_MATCH')

    def test_quote_and_json_display_keep_entire_payload(self):
        result=self.call('quote',reference_id='ref-8');original=json.loads((self.root/'8/approved.json').read_text('utf-8'))
        response=result['package_result']
        self.assertEqual(response['quote'],original['text'])
        self.assertEqual(response['citation'],{k:v for k,v in original.items() if k!='text'})
        shown=catalog.render_text(result);marker='COMPLETE JSON RECORD - all original citation, annotation, qualification and provenance fields:\n'
        self.assertEqual(json.loads(shown.split(marker)[1]),result)
        self.assertIn('ORIGINAL SOURCE EXCERPT',shown);self.assertIn('not original source wording',shown)

    def test_catalog_anchor_and_runtime_drift_fail_closed(self):
        initial=self.path.read_bytes();self.path.write_bytes(initial+b' ')
        with self.assertRaisesRegex(ValueError,'catalog_anchor_drift'):self.call()
        self.path.write_bytes(initial);p=Path(self.runtime['reference_excerpt']['path']);p.write_bytes(p.read_bytes()+b'\n# changed\n')
        with self.assertRaisesRegex(ValueError,'pinned_file_changed'):self.call()

    def test_unselected_package_source_drift_blocks_whole_operation(self):
        (self.root/'8/source.txt').write_text('changed',encoding='utf-8')
        for action,kw in [('catalog',{}),('quote',{'reference_id':'ref-0'}),('find',{'query':'topic0'})]:
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'source_hash_drift'):self.call(action,**kw)

    def test_evidence_and_acceptance_drift_rejected(self):
        p=self.root/'3/evidence.json';before=p.read_bytes();p.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'asset_hash_or_scope_drift'):self.call()
        p.write_bytes(before);(self.root/'acceptance.json').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'pinned_file_changed'):self.call()

    def test_index_and_manifest_drift_rejected(self):
        for name in ['index.sqlite','manifest.json','approved.json']:
            with self.subTest(name=name):
                p=self.root/'2'/name;before=p.read_bytes();p.write_bytes(before+b'changed')
                try:
                    with self.assertRaisesRegex(ValueError,'pinned_file_changed'):self.call()
                finally:p.write_bytes(before)

    def test_all_sqlite_sidecars_rejected(self):
        for suffix in ['-wal','-shm','-journal']:
            p=self.root/'4'/('index.sqlite'+suffix);p.write_bytes(b'fake')
            try:
                with self.assertRaisesRegex(ValueError,'sidecar_present'):self.call()
            finally:p.unlink()

    def test_duplicate_ids_and_package_scope_rejected(self):
        self.data['entries'][1]['id']='ref-0';self.repin()
        with self.assertRaisesRegex(ValueError,'catalog_identifier'):self.call()
        self.data['entries'][1]['id']='ref-1';self.data['entries'][1]['data_root']=str(self.root/'7');self.repin()
        with self.assertRaisesRegex(ValueError,'package_path_scope'):self.call()

    def test_required_annotation_digest_and_complete_citation_enforced(self):
        original=self.data['entries'][7]['annotation_sha256']
        self.data['entries'][7]['annotation_sha256']='0'*64;self.repin()
        with self.assertRaisesRegex(ValueError,'reviewed_annotation_missing_or_changed'):self.call()
        self.data['entries'][7]['annotation_sha256']=original
        path=self.root/'7/approved.json';chunk=json.loads(path.read_text('utf-8'))
        chunk['scientific_scope_note']='Silently replaced qualification.'
        path.write_text(json.dumps(chunk),encoding='utf-8')
        self.data['entries'][7]['approved_chunk']=self.pin(path);self.repin()
        with self.assertRaisesRegex(ValueError,'complete_reference_context_mismatch'):self.call()

    def test_no_partial_stdout_when_late_package_fails(self):
        (self.root/'8/source.txt').write_bytes(b'bad');stdout=io.StringIO();stderr=io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            code=catalog.main(self.path,self.anchor,['find','shared'])
        self.assertEqual(code,2);self.assertEqual(stdout.getvalue(),'');self.assertIn('refused',stderr.getvalue())

    def test_unsupported_commands_ids_and_query_limits(self):
        for action in ['calculate','train','answer_question','generate']:
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'unsupported_reference_action'):self.call(action)
        for query in ['', ' '*2, 'a'*2001, 'line\nbreak']:
            with self.subTest(query=repr(query)),self.assertRaises(ValueError):self.call('find',query=query)
        with self.assertRaisesRegex(ValueError,'unknown_reference_id'):self.call('quote',reference_id='unreleased')
        with self.assertRaisesRegex(ValueError,'quote_requires_only_catalog_id'):self.call('quote',query='question',reference_id='ref-0')


if __name__=='__main__':unittest.main()
