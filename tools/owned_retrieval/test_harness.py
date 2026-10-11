"""Boundary tests use synthetic owned-source fixtures; no ML or GPU imports."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import harness as h

class RetrievalTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).parent/'test-artifacts';root.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.temp.name)
        self.chunks=[];lines=[]
        for i in range(8):
            text=f'def function_{i}():\n    return "unique{i} units condition"\n'
            self.chunks.append({'id':f'chunk-{i}','text':text,'start_line':2*i+1,'end_line':2*i+2,'slice_sha256':hashlib.sha256(text.encode()).hexdigest()})
            lines.append(text)
        self.source=self.root/'source.py';self.source.write_text(''.join(lines),encoding='utf-8',newline='')
        self.pin=h.digest(self.source);self.patcher=patch.object(h,'SOURCE_SHA',self.pin);self.patcher.start()
        for c in self.chunks:c['source_sha256']=self.pin
        inputs=self.put('inputs.json',{'chunks':self.chunks,'held_academic_content':False,'sealed_eval_content':False})
        vectors=[]
        for i in range(16):
            v=[0.0]*768;v[i%8]=1.0;vectors.append(v)
        emb=self.put('vectors.json',{'input_sha256':h.digest(inputs),'vectors':vectors})
        smoke=self.put('smoke.json',{'revision':h.MODEL_REV,'training':False,'input_sha256':h.digest(inputs),'status':'COMPLETED','dimensions':768})
        release=self.put('release.json',{'engineering_source_sha256':self.pin})
        def ref(p):return {'path':str(p),'sha256':h.digest(p)}
        self.manifest={'purpose':'PRIVATE_OWNED_REFERENCE_ONLY','source_family':h.FAMILY,'source_sha256':self.pin,'model_revision':h.MODEL_REV,
          'inputs':ref(inputs),'source_blob':ref(self.source),'document_embedding_snapshot':ref(emb),
          'smoke_inference_receipt':ref(smoke),'owned_source_release_receipt':ref(release),
          'approved_chunks':[{'id':c['id'],'family':h.FAMILY,'use':'APPROVED_PRIVATE_REFERENCE','eval_only':False,'slice_sha256':c['slice_sha256']} for c in self.chunks]}
        self.mp=self.put('manifest.json',self.manifest)
    def tearDown(self):self.patcher.stop();self.temp.cleanup()
    def put(self,name,obj):
        p=self.root/name;p.write_text(json.dumps(obj),encoding='utf-8');return p
    def load(self):return h.LocalRetriever(self.mp,h.digest(self.mp))
    def mutate_manifest(self,fn):fn(self.manifest);self.put('manifest.json',self.manifest)
    def test_exact_identifier_and_verified_citation(self):
        r=self.load().query('unique6','lexical');self.assertEqual(r['hits'][0]['id'],'chunk-6')
        self.assertEqual(r['hits'][0]['citation']['start_line'],13);self.assertFalse(r['answer_generated'])
    def test_stale_source_after_load_refuses(self):
        r=self.load();self.source.write_text('changed',encoding='utf-8')
        with self.assertRaises(h.IntegrityError):r.query('unique6')
    def test_stale_vector_after_load_refuses(self):
        r=self.load();(self.root/'vectors.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(h.IntegrityError):r.query('unique6')
    def test_citation_range_tamper_even_with_updated_file_pin(self):
        p=self.root/'inputs.json';d=h.read_json(p);d['chunks'][0]['start_line']=3;p.write_text(json.dumps(d),encoding='utf-8')
        self.manifest['inputs']['sha256']=h.digest(p)
        s=self.root/'smoke.json';v=h.read_json(s);v['input_sha256']=h.digest(p);s.write_text(json.dumps(v),encoding='utf-8')
        self.manifest['smoke_inference_receipt']['sha256']=h.digest(s);self.put('manifest.json',self.manifest)
        with self.assertRaises(h.IntegrityError):self.load()
    def test_hold_eval_family_filters_each_fail_closed(self):
        for field,value in [('use','HOLD'),('eval_only',True),('family','unreviewed')]:
            old=copy.deepcopy(self.manifest);self.manifest['approved_chunks'][0][field]=value;self.put('manifest.json',self.manifest)
            with self.assertRaises(h.IntegrityError):self.load()
            self.manifest=old
    def test_untrusted_manifest_pin_refuses(self):
        with self.assertRaises(h.IntegrityError):h.LocalRetriever(self.mp,'0'*64)
    def test_nonfinite_and_wrong_dimensions_refuse(self):
        r=self.load()
        for v in [[1.0], [float('nan')]*768,[False]*768,[0.0]*768]:
            with self.assertRaises(h.IntegrityError):r.query('unique1','dense',v)
    def test_access_filter_applies_before_all_rankers(self):
        r=self.load();v=[0.0]*768;v[7]=1
        for mode in ('lexical','dense','hybrid'):
            q=r.query('unique7',mode,v,allowed_ids=['chunk-1'])
            self.assertTrue(all(x['id']=='chunk-1' for x in q['hits']))
    def test_empty_allowlist_abstains_all_methods(self):
        r=self.load();v=[0.0]*768;v[0]=1
        for mode in ('lexical','dense','hybrid'):
            q=r.query('unique0',mode,v,allowed_ids=[]);self.assertEqual(q['hits'],[])
            self.assertEqual(q['status'],'ABSTAIN_NO_MATCHING_APPROVED_EVIDENCE')
    def test_unknown_text_lexical_abstains_dense_is_not_answer(self):
        r=self.load();v=[0.0]*768;v[0]=1
        self.assertEqual(r.query('xylophonically')['hits'],[])
        self.assertEqual(r.query('xylophonically','dense',v)['status'],'EVIDENCE_CANDIDATES_NOT_AN_ANSWER')
    def test_duplicate_json_and_duplicate_chunks_refuse(self):
        p=self.put('duplicate.json',{});p.write_text('{"a":1,"a":2}',encoding='utf-8')
        with self.assertRaises(h.IntegrityError):h.read_json(p)
        self.manifest['approved_chunks'][0]=self.manifest['approved_chunks'][1];self.put('manifest.json',self.manifest)
        with self.assertRaises(h.IntegrityError):self.load()
    def test_query_limits(self):
        r=self.load()
        for q in ['', ' '*3, 'x'*2049]:
            with self.assertRaises(ValueError):r.query(q)

    def test_zero_lexical_nonmatches_keep_dense_relative_order(self):
        r=self.load();v=[0.0]*768;v[7]=.7**.5;v[5]=.2**.5;v[3]=.1**.5
        result=r.query('unique7','hybrid',v,top_k=8)
        self.assertEqual([x['id'] for x in result['hits'][:3]],['chunk-7','chunk-5','chunk-3'])

if __name__=='__main__':unittest.main(verbosity=2)
