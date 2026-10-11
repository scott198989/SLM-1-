"""CPU-only local retrieval. No network, model loading, or answer generation.

The caller supplies a trusted manifest hash out-of-band. Rankings are relevance
candidates, never an answerability or scientific-validity decision.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

SOURCE_SHA = 'ce6ab03daa581ba0dc179facd89dec2e41b2e3890c3215af5a5c75454199fd9e'
MODEL_REV = '914f7f89142e33e77833254d9c9b90c3cef7303b'
FAMILY = 'owned-engineering-calculator-complete-source-v01'
STOP = frozenset('a an the to of in is are be what which how when does do can for and or if with as it this that its both from into at by used'.split())

class IntegrityError(ValueError): pass

def digest(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def read_json(path):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise IntegrityError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(Path(path).read_text('utf-8'),object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(IntegrityError('Nonfinite JSON')))

def tokens(text):
    # Keep identifiers as exact tokens and add underscore components; retain
    # unit/sign-relevant numbers without claiming algebraic equivalence.
    out=[]
    for word in re.findall(r'[a-z_][a-z_0-9]*|\d+(?:\.\d+)?|<=|>=|<|>|\+|\-|\*|/|%',text.lower()):
        if word not in STOP: out.append(word)
        if '_' in word: out.extend(x for x in word.split('_') if x and x not in STOP)
    return out

def vector_ok(v):
    if not isinstance(v,list) or len(v)!=768: raise IntegrityError('Vector dimension mismatch')
    if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in v):
        raise IntegrityError('Invalid vector values')
    if abs(sum(x*x for x in v)-1)>1e-5: raise IntegrityError('Vector not normalized')

class LocalRetriever:
    def __init__(self, manifest, expected_sha):
        self.path=Path(manifest).resolve()
        if digest(self.path)!=expected_sha: raise IntegrityError('Untrusted manifest hash')
        self.manifest_sha=expected_sha
        self.manifest=read_json(self.path)
        m=self.manifest
        if m.get('purpose')!='PRIVATE_OWNED_REFERENCE_ONLY' or m.get('source_family')!=FAMILY:
            raise IntegrityError('Unapproved purpose or family')
        if m.get('source_sha256')!=SOURCE_SHA or m.get('model_revision')!=MODEL_REV:
            raise IntegrityError('Source/model drift')
        self.inputs_path=self._ref(m['inputs'])
        self.source_path=self._ref(m['source_blob'])
        self.embeddings_path=self._ref(m['document_embedding_snapshot'])
        smoke=read_json(self._ref(m['smoke_inference_receipt']))
        release=read_json(self._ref(m['owned_source_release_receipt']))
        if (smoke.get('revision')!=MODEL_REV or smoke.get('training') is not False
                or smoke.get('input_sha256')!=digest(self.inputs_path)
                or smoke.get('status')!='COMPLETED' or smoke.get('dimensions')!=768):
            raise IntegrityError('Unqualified saved document vectors')
        if release.get('engineering_source_sha256')!=SOURCE_SHA:
            raise IntegrityError('Owned-source release binding mismatch')
        self.inputs=read_json(self.inputs_path)
        if self.inputs.get('held_academic_content') is not False or self.inputs.get('sealed_eval_content') is not False:
            raise IntegrityError('Held/evaluation content not permitted')
        self.chunks=self.inputs['chunks']
        if len(self.chunks)!=8 or len({x['id'] for x in self.chunks})!=8:
            raise IntegrityError('Expected eight unique approved chunks')
        approved=m['approved_chunks']
        if len(approved)!=8 or {x['id'] for x in approved}!={x['id'] for x in self.chunks}:
            raise IntegrityError('Allowlist differs from input chunks')
        by_id={x['id']:x for x in approved}
        for chunk in self.chunks:
            allow=by_id[chunk['id']]
            if allow.get('use')!='APPROVED_PRIVATE_REFERENCE' or allow.get('family')!=FAMILY or allow.get('eval_only') is not False:
                raise IntegrityError('Chunk use/family/evaluation filter refused')
            if chunk['source_sha256']!=SOURCE_SHA or allow.get('slice_sha256')!=chunk['slice_sha256']:
                raise IntegrityError('Chunk allowlist hash mismatch')
        self._verify_sources()
        saved=read_json(self.embeddings_path)
        if saved['input_sha256']!=digest(self.inputs_path) or len(saved['vectors'])!=16:
            raise IntegrityError('Smoke-vector/input binding mismatch')
        self.vectors=saved['vectors'][:8] # Leave all original sixteen untouched.
        for v in saved['vectors']: vector_ok(v)
        self.terms=[Counter(tokens(c['text'])) for c in self.chunks]
        self.lengths=[sum(t.values()) for t in self.terms]
        self.average=sum(self.lengths)/len(self.lengths)
        self.df=Counter(t for terms in self.terms for t in terms)

    def _ref(self,record):
        p=Path(record['path'])
        if not p.is_absolute(): p=self.path.parent/p
        p=p.resolve()
        if not p.is_file() or digest(p)!=record['sha256']: raise IntegrityError('Missing or changed evidence: '+str(p))
        return p

    def _verify_sources(self):
        if digest(self.path)!=self.manifest_sha: raise IntegrityError('Manifest changed during use')
        for key in ('inputs','source_blob','document_embedding_snapshot','smoke_inference_receipt','owned_source_release_receipt'): self._ref(self.manifest[key])
        if digest(self.source_path)!=SOURCE_SHA: raise IntegrityError('Unapproved exact source blob')
        lines=self.source_path.read_text('utf-8').splitlines(keepends=True)
        for c in self.chunks:
            start,end=c['start_line'],c['end_line']
            if isinstance(start,bool) or not isinstance(start,int) or not isinstance(end,int) or not 1<=start<=end<=len(lines):
                raise IntegrityError('Invalid citation range')
            excerpt=''.join(lines[start-1:end])
            if excerpt!=c['text'] or hashlib.sha256(excerpt.encode()).hexdigest()!=c['slice_sha256']:
                raise IntegrityError('Citation text/range mismatch: '+c['id'])

    def lexical_scores(self,query):
        q=Counter(tokens(query)); n=len(self.chunks); k1=1.2;b=.75
        scores=[]
        for term_counts,length in zip(self.terms,self.lengths):
            score=0.0
            for term in q:
                frequency=term_counts.get(term,0)
                if not frequency: continue
                idf=math.log(1+(n-self.df[term]+.5)/(self.df[term]+.5))
                score+=idf*frequency*(k1+1)/(frequency+k1*(1-b+b*length/self.average))
            scores.append(score)
        return scores

    def query(self,query,method='lexical',query_vector=None,top_k=3,allowed_ids=None):
        if not isinstance(query,str) or not query.strip() or len(query)>2048: raise ValueError('Query must contain 1-2048 characters')
        if method not in ('lexical','dense','hybrid') or not 1<=top_k<=8: raise ValueError('Invalid retrieval request')
        self._verify_sources() # Per-request stale source/index rejection.
        allowed=set(c['id'] for c in self.chunks)
        if allowed_ids is not None: allowed &= set(allowed_ids)
        indices=[i for i,c in enumerate(self.chunks) if c['id'] in allowed]
        lexical=self.lexical_scores(query)
        dense=None
        if method!='lexical':
            vector_ok(query_vector)
            dense=[sum(a*b for a,b in zip(query_vector,v)) for v in self.vectors]
        def order(scores):return sorted(indices,key=lambda i:(-scores[i],self.chunks[i]['id']))
        if method=='lexical': scores=lexical
        elif method=='dense': scores=dense
        else:
            # RRF k=60, equal weights, fixed before new development results.
            # A zero-BM25 document is absent from the lexical result list; do
            # not award arbitrary ID-order rank credit to nonmatches.
            ranks=[{i:rank+1 for rank,i in enumerate([j for j in order(lexical) if lexical[j]>0])},
                   {i:rank+1 for rank,i in enumerate(order(dense))}]
            scores=[sum(1/(60+r[i]) for r in ranks if i in r) if i in indices else 0 for i in range(8)]
        ranked=order(scores)
        if method=='lexical': ranked=[i for i in ranked if lexical[i]>0]
        hits=[]
        for i in ranked[:top_k]:
            c=self.chunks[i]
            hits.append({'id':c['id'],'score':scores[i],'lexical_score':lexical[i],
              'dense_score':dense[i] if dense else None,'citation':{'source_sha256':SOURCE_SHA,
              'slice_sha256':c['slice_sha256'],'start_line':c['start_line'],'end_line':c['end_line'],
              'source_path':str(self.source_path)},'evidence':c['text']})
        self._verify_sources() # Validate again immediately before returning citations.
        return {'status':'EVIDENCE_CANDIDATES_NOT_AN_ANSWER' if hits else 'ABSTAIN_NO_MATCHING_APPROVED_EVIDENCE',
          'method':method,'query':query,'manifest_sha256':self.manifest_sha,'hits':hits,
          'answer_generated':False,'answerability':'NOT_ESTABLISHED_BY_RANKING',
          'limitation':'Related code may only establish a limitation; similarity is not confidence or entailment.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--expected-manifest-sha',required=True)
    p.add_argument('--query',required=True);p.add_argument('--method',choices=['lexical','dense','hybrid'],default='lexical')
    p.add_argument('--query-vector-file',type=Path);p.add_argument('--query-vector-sha');p.add_argument('--probe-id')
    a=p.parse_args();retriever=LocalRetriever(a.manifest,a.expected_manifest_sha);vec=None
    if a.method!='lexical':
        if not a.query_vector_file or not a.query_vector_sha or digest(a.query_vector_file)!=a.query_vector_sha:
            p.error('Dense/hybrid needs a trusted saved query-vector receipt hash')
        saved=read_json(a.query_vector_file)
        if saved.get('model_revision')!=MODEL_REV: raise IntegrityError('Query model mismatch')
        row=next(x for x in saved['queries'] if x['id']==a.probe_id)
        if row['query']!=a.query: raise IntegrityError('Vector does not bind this query')
        vec=row['vector']
    print(json.dumps(retriever.query(a.query,a.method,vec),indent=2))
if __name__=='__main__':main()
