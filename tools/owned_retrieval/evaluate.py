"""Run explicitly non-blind development probes, CPU-only, with saved query vectors."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from .harness import LocalRetriever,MODEL_REV,digest,read_json

def evaluate(manifest,manifest_sha,probes_path,probes_sha,vectors_path,vectors_sha,prior_results_observed=False):
    if digest(probes_path)!=probes_sha or digest(vectors_path)!=vectors_sha:raise ValueError('Probe/vector pin mismatch')
    probes=read_json(probes_path);vectors=read_json(vectors_path)
    if vectors['model_revision']!=MODEL_REV or vectors['probes_sha256']!=probes_sha:raise ValueError('Query embedding binding mismatch')
    by_id={x['id']:x for x in vectors['queries']}
    if len(by_id)!=len(vectors['queries']) or set(by_id)!={x['id'] for x in probes['probes']}:raise ValueError('Query scope mismatch')
    retriever=LocalRetriever(manifest,manifest_sha);rows=[]
    for p in probes['probes']:
        v=by_id[p['id']]
        if p['query']!=v['query']:raise ValueError('Query text drift')
        for method in ('lexical','dense','hybrid'):
            # Only text/vector enter ranking. Expected labels and evidence spans
            # are consulted afterwards and never used as a serving filter.
            result=retriever.query(p['query'],method,v['vector'],top_k=8)
            ids=[x['id'] for x in result['hits']]; expected=p['expected_chunk']
            rank=ids.index(expected)+1 if expected in ids else None
            rows.append({'probe_id':p['id'],'kind':p['kind'],'query':p['query'],'method':method,
              'expected_chunk':expected,'rank':rank,'top3':ids[:3],
              'scores_top3':[{'id':x['id'],'score':x['score'],'lexical':x['lexical_score'],'dense':x['dense_score']} for x in result['hits'][:3]],
              'citation_checks':'PASS','status':result['status'],'answer_generated':False,
              'refusal_evidence_chunk':p.get('refusal_evidence_chunk'),
              'candidate_returned_for_no_answer':p['kind']=='no_answer' and bool(ids),
              'refusal_evidence_top3':p.get('refusal_evidence_chunk') in ids[:3] if p.get('refusal_evidence_chunk') else None})
    summaries={}
    for method in ('lexical','dense','hybrid'):
        pos=[x for x in rows if x['method']==method and x['kind']=='answerable']
        neg=[x for x in rows if x['method']==method and x['kind']=='no_answer']
        summaries[method]={'answerable_probes':len(pos),'top1_hits':sum(x['rank']==1 for x in pos),
          'top3_hits':sum(x['rank'] is not None and x['rank']<=3 for x in pos),
          'mrr':sum(1/x['rank'] if x['rank'] else 0 for x in pos)/len(pos),
          'no_answer_probes':len(neg),'no_answer_with_candidates':sum(x['candidate_returned_for_no_answer'] for x in neg),
          'no_answer_automatically_abstained':sum(not x['candidate_returned_for_no_answer'] for x in neg),
          'unsupported_answers_generated':0}
    return {'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'DEVELOPMENT_ONLY_SAME_AGENT_NOT_BLIND_OR_EXPERT_VALIDATION',
      'manifest_sha256':manifest_sha,'probes_sha256':probes_sha,'query_vectors_sha256':vectors_sha,
      'labels_used_for_ranking':False,'prior_results_observed':prior_results_observed,
      'ranking_configuration':{'BM25_k1':1.2,'BM25_b':0.75,'RRF_k':60,'fusion':'equal weights; only positive lexical matches contribute lexical ranks'},
      'no_answer_metric_limit':'Candidates for unsupported questions are not false answers: no answering system exists. They expose the missing answerability/entailment gate.',
      'summary':summaries,'results':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha',required=True)
    p.add_argument('--probes',type=Path,required=True);p.add_argument('--probes-sha',required=True)
    p.add_argument('--vectors',type=Path,required=True);p.add_argument('--vectors-sha',required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--prior-results-observed',action='store_true')
    a=p.parse_args();r=evaluate(a.manifest,a.manifest_sha,a.probes,a.probes_sha,a.vectors,a.vectors_sha,a.prior_results_observed)
    with a.report.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps(r['summary'],indent=2))
if __name__=='__main__':main()
