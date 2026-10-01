"""Compact the audit and conservatively recover explicitly labelled conversations.
This produces review candidates, never approved training exports.
"""
import collections,gzip,json,re,sys
from pathlib import Path
from audit_repositories import canonical,dump,flags,record_hash
ROOT=Path(__file__).resolve().parents[1]
def legacy_messages(text):
    if not isinstance(text,str):raise ValueError('text_not_string')
    matches=list(re.finditer(r'(?m)^(System|User|HAVOC|Assistant):[ \t]*',text))
    if not matches or matches[0].start()!=0:raise ValueError('missing_explicit_role_boundary')
    result=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(text)
        role='system' if m[1]=='System' else 'user' if m[1]=='User' else 'assistant'
        # Remove precisely the separating newline, not internal whitespace.
        value=text[m.end():end]
        if i+1<len(matches) and value.endswith('\n'):value=value[:-1]
        result.append({'role':role,'content':value})
    result,error=canonical({'messages':result})
    if error:raise ValueError(error)
    return result

def main():
    original=ROOT/'data/sft/staging/repository-candidates.jsonl'
    records={}
    for line in original.open(encoding='utf-8'):
        record=json.loads(line);records[record_hash(record['messages'])]=record
    source_manifest=json.loads((ROOT/'manifests/repository-datasets.json').read_text())
    recovered=collections.Counter()
    for source in source_manifest:
        if source['repository']!='scott198989/SLM':continue
        path=ROOT/'.audit-sources/SLM'/source['path']
        for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip():continue
            row=json.loads(line);messages=legacy_messages(row['text']);key=record_hash(messages)
            origin={k:v for k,v in source.items() if k not in ('rows','valid_rows','issues')}
            origin.update(line=number,legacy_split='unspecified',url=f'https://github.com/{source["repository"]}/blob/{source["commit"]}/{source["path"]}#L{number}')
            recovered['rows']+=1
            if key in records:records[key]['provenance']['origins'].append(origin);recovered['exact_duplicate_rows']+=1;continue
            p={'origins':[origin],'origin_kind':'unverified_legacy_or_synthetic','generator':None,'technical_correctness':'unverified','review_status':'quarantined','issue_codes':flags(messages)+['LEGACY_LABEL_BOUNDARIES_REQUIRE_REVIEW','LEGACY_HAVOC_PERSONA_REQUIRE_REVIEW'],'source_family_status':'unresolved','prompt_group':record_hash([m for m in messages if m['role']=='user']),'split':'unassigned','legacy_metadata':{}}
            records[key]={'id':'repo-'+key[:24],'messages':messages,'provenance':p};recovered['unique_records_added']+=1
    data_dir=ROOT/'data/sft/staging/consolidated-20261001-v2';data_dir.mkdir(parents=True,exist_ok=False)
    prompts=collections.defaultdict(list);near=collections.defaultdict(list)
    for r in records.values():
        prompts[r['provenance']['prompt_group']].append(r)
        import unicodedata
        folded=[dict(m,content=' '.join(unicodedata.normalize('NFKC',m['content']).casefold().split())) for m in r['messages']]
        near[record_hash(folded)].append(r)
    conflicts=[]
    for key,group in prompts.items():
        if len(group)>1:
            conflicts.append({'prompt_group':key,'record_ids':[r['id'] for r in group]})
            for r in group:
                if 'PROMPT_COLLISION_REVIEW' not in r['provenance']['issue_codes']:r['provenance']['issue_codes'].append('PROMPT_COLLISION_REVIEW')
                r['provenance']['review_status']='quarantined'
    cohort_count=0
    for r in records.values():
        origins=r['provenance']['origins']
        if origins and all(o['repository']=='scott198989/Completions' and o['path']=='core_world_model.jsonl' for o in origins):
            r['provenance']['issue_codes'].append('SOURCE_COHORT_OPERATOR_LOSS_REVIEW')
            r['provenance']['review_status']='quarantined';cohort_count+=1
    with (data_dir/'candidates.jsonl').open('w',encoding='utf-8',newline='\n') as out, gzip.GzipFile(filename='',mode='wb',fileobj=(data_dir/'provenance.jsonl.gz').open('wb'),mtime=0) as metadata:
        for r in records.values():
            out.write(json.dumps({'id':r['id'],'messages':r['messages']},ensure_ascii=False,separators=(',',':'))+'\n')
            metadata.write((json.dumps({'id':r['id'],**r['provenance']},ensure_ascii=False,separators=(',',':'))+'\n').encode())
    report=json.loads((ROOT/'reports/repository-audit.json').read_text());total=sum(r.get('rows',0) for r in report['repositories'].values());invalid=sum(r['code']=='INVALID_JSON' for r in json.loads((ROOT/'reports/row-issues.json').read_text()))
    report.update(unique_candidate_records=len(records),legacy_role_recovery=dict(recovered),valid_row_occurrences=total-invalid,invalid_json_row_occurrences=invalid,exact_duplicate_row_occurrences=total-invalid-len(records),statuses=dict(collections.Counter(r['provenance']['review_status'] for r in records.values())),issue_counts=dict(collections.Counter(c for r in records.values() for c in r['provenance']['issue_codes'])),total_dataset_row_occurrences=total,prompt_collision_groups=len(conflicts),normalized_near_twin_groups=sum(len(g)>1 for g in near.values()),canonical_staging_path=data_dir.relative_to(ROOT).as_posix(),manual_cohort_review_records=cohort_count,complete_technical_usable_percentage=None)
    for name,n,d in [('parseable_row_percentage',total-invalid,total),('unique_retained_row_percentage',len(records),total),('unflagged_unique_candidate_percentage',report['statuses'].get('needs_review',0),len(records))]:report[name]={'numerator':n,'denominator':d,'percentage':100*n/d}
    report['repositories']['SLM']['initial_strict_import_unsupported_rows']=report['repositories']['SLM'].pop('invalid_rows')
    report['repositories']['SLM'].update(valid_recovered_rows=recovered['rows'],unique_records_added=recovered['unique_records_added'],exact_duplicate_rows=recovered['exact_duplicate_rows'],invalid_json_rows=0)
    dump(ROOT/'reports/consolidated-audit.json',report);dump(ROOT/'reports/consolidated-prompt-conflicts.json',conflicts)
    dump(ROOT/'reports/consolidated-near-twins.json',[{'group':k,'record_ids':[r['id'] for r in g]} for k,g in near.items() if len(g)>1])
    print(json.dumps(report),flush=True)
if __name__=='__main__':main()
