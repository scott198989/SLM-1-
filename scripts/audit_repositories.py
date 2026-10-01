"""Pinned public repository audit. No imported code is executed; no training.
Whole-file privacy screening precedes persistence. All staging is unverified.
"""
import argparse, collections, hashlib, json, re, unicodedata, urllib.parse, urllib.request
from pathlib import Path, PurePosixPath
from quality_checks import inspect_sensitive, inspect_text, normalize_text
REPOS = ('Completions', 'SLM', 'LLM', 'SLM-1-')
OWNER = 'scott198989'
BAD_NAME = re.compile(r'(?:^|/)(?:va|military)(?:/|$)|password|passwd|credential|secret|(?:^|/)\.env(?:\.|$)|private.?key|api.?key|access.?token|bank.*(?:account|statement)|medical.?record|social.?security|dd.?214', re.I)
TEXT_EXT = {'.jsonl','.json','.txt','.md','.py','.yaml','.yml','.toml','.csv','.sh','.html','.js','.jsx','.css','.ipynb'}
def digest(data): return hashlib.sha256(data).hexdigest()
def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def classification(path):
    parts = PurePosixPath(path).parts
    if not path or PurePosixPath(path).is_absolute() or any(p in {'.','..'} or ':' in p or '\\' in p for p in parts) or BAD_NAME.search(path): return 'excluded_path'
    if path.startswith('.claude/') or '__pycache__' in path: return 'local_configuration_or_binary'
    if path.endswith(('.jsonl','.jsonl.bak')):
        return 'training_log_or_evaluation_artifact' if path.startswith('logs') else 'candidate_dataset'
    if 'tokenizer_corpus' in path: return 'tokenizer_corpus_not_sft'
    return 'documentation_config_or_code' if Path(path).suffix in TEXT_EXT or path in {'Dockerfile','.gitignore','.dockerignore','-ScottsLaptop.gitignore'} else 'unsupported_or_generated_artifact'
def canonical(row):
    if not isinstance(row,dict): return None,'ROW_NOT_OBJECT'
    if 'messages' in row: messages=row['messages']
    elif isinstance(row.get('prompt'),str) and isinstance(row.get('completion'),str):
        messages=[{'role':'user','content':row['prompt']},{'role':'assistant','content':row['completion']}]
    elif isinstance(row.get('instruction'),str) and isinstance(row.get('output'),str):
        prompt=row['instruction']; extra=row.get('input','')
        if not isinstance(extra,str): return None,'INPUT_NOT_TEXT'
        if extra: prompt+='\n\n'+extra
        messages=[{'role':'user','content':prompt},{'role':'assistant','content':row['output']}]
    else: return None,'UNSUPPORTED_ROW_SCHEMA'
    if not isinstance(messages,list) or len(messages)<2: return None,'INCOMPLETE_MESSAGES'
    result=[]; expected='user'
    for i,message in enumerate(messages):
        if not isinstance(message,dict): return None,'MESSAGE_NOT_OBJECT'
        if set(message)-{'role','content'}: return None,'UNSUPPORTED_MESSAGE_FIELDS'
        role=message.get('role'); text=message.get('content')
        if not isinstance(text,str) or not text.strip(): return None,'EMPTY_OR_NON_TEXT_CONTENT'
        if role=='system' and i==0: pass
        elif role!=expected: return None,'INVALID_ROLE_ORDER'
        else: expected='assistant' if expected=='user' else 'user'
        normalized,_=normalize_text(text)
        result.append({'role':role,'content':normalized})
    return (result,None) if result[-1]['role']=='assistant' else (None,'MISSING_FINAL_ASSISTANT')
def record_hash(messages): return digest(json.dumps(messages,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def flags(messages):
    codes={c['code'] for m in messages for c in inspect_text(m['content'])['checks']}
    text='\n'.join(m['content'] for m in messages)
    if '<|' in text or '[INST]' in text: codes.add('EMBEDDED_TRAINING_CONTROL_TOKENS')
    if re.search(r'\b(?:TODO|TBD|INSERT ANSWER|your answer here)\b',text,re.I): codes.add('PLACEHOLDER_RESPONSE')
    if re.search(r'(?:above|below|following|attached)\s+(?:figure|graph|diagram|image|table)|(?:figure|diagram|graph)\s+\d',text,re.I): codes.add('VISUAL_OR_TABLE_DEPENDENCY_REVIEW')
    return sorted(codes)
def fetch(repo,commit,entry):
    if repo not in REPOS or not re.fullmatch('[0-9a-f]{40}',commit): raise ValueError('invalid_identity')
    url=f'https://raw.githubusercontent.com/{OWNER}/{repo}/{commit}/'+urllib.parse.quote(entry['path'],safe='/')
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FORGE-Audit'}),timeout=60) as r: data=r.read(16*1024*1024+1)
    if len(data)!=entry['size'] or len(data)>16*1024*1024: raise ValueError('size_mismatch')
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if actual!=entry['sha']: raise ValueError('blob_hash_mismatch')
    return data

def audit(base,trees):
    target=base/'data/sft/staging/repository-candidates.jsonl'
    if target.exists(): raise FileExistsError('immutable_output_exists')
    inventory=[]; sources=[]; row_issues=[]; records={}; summaries={}
    for repo in REPOS:
        tree=json.loads((trees/f'{repo}-tree.json').read_text(encoding='utf-8-sig'))
        if tree.get('truncated'): raise ValueError('incomplete_tree')
        counts=collections.Counter()
        for entry in sorted(tree['tree'],key=lambda x:x['path']):
            if entry['type']!='blob': continue
            kind=classification(entry['path']); counts['files']+=1; counts[kind]+=1
            identity={'repository':f'{OWNER}/{repo}','commit':tree['sha'],'path':entry['path'],'blob_sha1':entry['sha'],'bytes':entry.get('size',0)}
            item={**identity,'classification':kind}; inventory.append(item)
            if kind in {'excluded_path','local_configuration_or_binary','unsupported_or_generated_artifact'}: continue
            if not entry.get('size'): item['status']='empty_stub'; counts['empty_files']+=1; continue
            try: data=fetch(repo,tree['sha'],entry); text=data.decode('utf-8-sig')
            except (OSError,ValueError,UnicodeError) as err:
                item['status']='fetch_or_decode_failed'; item['error_class']=type(err).__name__; continue
            item['sha256']=digest(data); sensitive=inspect_sensitive(text)
            # JSON decoding exposes escaped identifiers before any file write.
            if kind=='candidate_dataset':
                for line in text.splitlines():
                    try: decoded=json.loads(line)
                    except (ValueError,RecursionError): continue
                    sensitive.extend(inspect_sensitive(json.dumps(decoded,ensure_ascii=False)))
            if sensitive:
                item['status']='excluded_entire_file_privacy'; item['codes']=sorted(set(sensitive)); counts['privacy_excluded_files']+=1; continue
            snapshot=base/'.audit-sources'/repo/entry['path']; snapshot.parent.mkdir(parents=True,exist_ok=True); snapshot.write_bytes(data)
            item['status']='screened_local_snapshot'; counts['screened_files']+=1
            if kind!='candidate_dataset': continue
            source={**identity,'sha256':item['sha256'],'rows':0,'valid_rows':0,'issues':collections.Counter()}; sources.append(source)
            for number,line in enumerate(text.splitlines(),1):
                if not line.strip(): continue
                counts['rows']+=1; source['rows']+=1
                try: row=json.loads(line)
                except (ValueError,RecursionError): messages=None; error='INVALID_JSON'
                else: messages,error=canonical(row)
                if error:
                    counts['invalid_rows']+=1; source['issues'][error]+=1; row_issues.append({**identity,'line':number,'code':error}); continue
                source['valid_rows']+=1; key=record_hash(messages)
                origin={**identity,'sha256':item['sha256'],'line':number,'legacy_split':'validation' if Path(entry['path']).name=='val.jsonl' else 'unspecified','url':f'https://github.com/{OWNER}/{repo}/blob/{tree["sha"]}/'+urllib.parse.quote(entry['path'],safe='/')+f'#L{number}'}
                if key in records: records[key]['provenance']['origins'].append(origin); counts['exact_duplicate_rows']+=1; continue
                codes=flags(messages)
                provenance={'origins':[origin],'origin_kind':'unverified_legacy_or_synthetic','generator':None,'technical_correctness':'unverified','review_status':'quarantined' if codes else 'needs_review','issue_codes':codes,'source_family_status':'unresolved','prompt_group':record_hash([m for m in messages if m['role']=='user']),'split':'unassigned','legacy_metadata':{k:row[k] for k in ('difficulty','task_type','response_style') if k in row}}
                records[key]={'id':'repo-'+key[:24],'messages':messages,'provenance':provenance}; counts['unique_records_added']+=1
        summaries[repo]=dict(counts); print(json.dumps({'repository':repo,'counts':dict(counts)}),flush=True)
    prompts=collections.defaultdict(list); near=collections.defaultdict(list)
    for record in records.values():
        prompts[record['provenance']['prompt_group']].append(record)
        folded=[dict(m,content=' '.join(unicodedata.normalize('NFKC',m['content']).casefold().split())) for m in record['messages']]
        near[record_hash(folded)].append(record)
    conflicts=[]
    for key,group in prompts.items():
        if len(group)>1:
            conflicts.append({'prompt_group':key,'record_ids':[r['id'] for r in group],'reason':'same_user_turns_different_answer_or_context'})
            for r in group: r['provenance']['issue_codes'].append('PROMPT_COLLISION_REVIEW'); r['provenance']['review_status']='quarantined'
    twins=[{'group':key,'record_ids':[r['id'] for r in group]} for key,group in near.items() if len(group)>1]
    for record in records.values():
        if any(o['legacy_split']=='validation' for o in record['provenance']['origins']): record['provenance']['issue_codes'].append('LEGACY_VALIDATION_OVERLAP_REVIEW'); record['provenance']['review_status']='quarantined'
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8',newline='\n') as stream:
        for r in records.values(): stream.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    statuses=collections.Counter(r['provenance']['review_status'] for r in records.values())
    codes=collections.Counter(c for r in records.values() for c in r['provenance']['issue_codes'])
    report={'scope':'current_default_branch_snapshots_only_not_history_or_external_references','all_nonempty_fetched_candidate_rows_scanned':True,'technical_answers_independently_verified':0,'ready_sft_records':0,'ready_rag_chunks':0,'unique_candidate_records':len(records),'statuses':dict(statuses),'issue_counts':dict(codes),'repositories':summaries,'prompt_collision_groups':len(conflicts),'normalized_near_twin_groups':len(twins),'license_status':'No LICENSE files in these pinned trees; upstream rights/provenance need review'}
    for path,obj in [('manifests/repository-files.json',inventory),('manifests/repository-datasets.json',sources),('reports/repository-audit.json',report),('reports/row-issues.json',row_issues),('reports/prompt-conflicts.json',conflicts),('reports/normalized-near-twins.json',twins)]: dump(base/path,obj)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--trees',type=Path,required=True); p.add_argument('--base',type=Path,default=Path(__file__).resolve().parents[1]); args=p.parse_args(); print(json.dumps(audit(args.base.resolve(),args.trees.resolve())),flush=True)
