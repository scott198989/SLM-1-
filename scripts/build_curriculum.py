"""Exact review curriculum and rights overlay, preserving legacy staging."""
import collections,gzip,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from forge_data.qwen_format import QwenFormatter
DOMAINS={'D_AC_Circuits.jsonl':('circuits',350),'D_Advanced_Eng_Math.jsonl':('engineering_mathematics',200),'D_Algebra.jsonl':('algebra',250),'D_Thermodynamics.jsonl':('thermal_process_engineering',200),'D_Trigonometry.jsonl':('trigonometry',200),'D_calculus.jsonl':('calculus',350),'D_elect_components.jsonl':('electrical_components',300),'D_electrodynamics.jsonl':('electromagnetism',200),'D_material_science.jsonl':('materials_manufacturing',250),'D_physics.jsonl':('physics',250)}
TAGS={'motors_drives':r'\b(?:motor|drive|torque|back[- ]emf)\b','controls':r'\b(?:PID|feedback|transfer function|stability|damping|controller)\b','plc_ladder':r'\b(?:PLC|ladder logic|interlock|scan cycle)\b','siemens_tia':r'\b(?:Siemens|TIA|S7[- ]\d)\b','instrumentation_sensors':r'\b(?:sensor|instrumentation|transducer|thermocouple|measurement|calibration)\b','statics_strength':r'\b(?:stress|strain|beam|bending|torsion|statics|factor of safety)\b','troubleshooting':r'\b(?:troubleshoot|diagnos|fault|failure|malfunction)\w*\b','engineering_data_analysis':r'\b(?:ANOVA|regression|confidence interval|t[- ]test|SPC|DOE|standard deviation)\b','technical_problem_solving':r'\b(?:calculate|derive|solve|determine|compute|prove|explain)\b'}

def build(assets):
    stage=ROOT/'data/sft/staging/consolidated-20261001-v2';records=[];pools=collections.defaultdict(list);sources=collections.defaultdict(collections.Counter);by_domain=collections.defaultdict(collections.Counter);tags=collections.Counter();origin_aliases=collections.Counter()
    with gzip.open(stage/'candidates.jsonl.gz','rt',encoding='utf-8') as data,gzip.open(stage/'provenance.jsonl.gz','rt',encoding='utf-8') as metadata:
        for line,meta in zip(data,metadata):
            row=json.loads(line);p=json.loads(meta)
            if row['id']!=p['id']:raise ValueError('lineage_mismatch')
            topics=sorted({o['path'] for o in p['origins'] if o['repository']=='scott198989/Completions' and o['path'] in DOMAINS})
            primary=topics[0] if topics else None
            domain=DOMAINS[primary][0] if primary else 'legacy_conversations' if any(o['repository'].endswith('/SLM') for o in p['origins']) else 'operator_damaged_core' if all(o['path']=='core_world_model.jsonl' for o in p['origins']) else 'generic_conversation_low_priority'
            text='\n'.join(m['content'] for m in row['messages']);matched=[name for name,pattern in TAGS.items() if re.search(pattern,text,re.I)]
            tags.update(matched);by_domain[domain]['candidates']+=1;by_domain[domain][p['review_status']]+=1
            if primary:sources[primary]['unique_primary_candidates']+=1;sources[primary][p['review_status']]+=1
            for repo in {o['repository'] for o in p['origins']}:origin_aliases[repo]+=1
            item={'id':row['id'],'domain':domain,'primary_source':primary or p['origins'][0]['path'],'legacy_review_status':p['review_status'],'source_issue_codes':p['issue_codes'],'effective_release_state':'QUARANTINED','source_provenance':'VERIFIED_USER_ATTESTATION','rights_state':'PARTIAL_API_TERMS_UNRESOLVED','family_split_state':'UNKNOWN','answer_correctness':'UNKNOWN','capability_hints':matched,'proposed_v01_review_selection':False}
            records.append((item,row['messages']))
            if primary and not p['issue_codes'] and len(row['messages'][-1]['content'])>=80 and matched:pools[domain].append((item,row['messages']))
    manual=json.loads((ROOT/'manifests/manual-curriculum-review.json').read_text(encoding='utf-8'))
    holds={x['id']:x for x in manual['records']}
    for item,_ in records:
        if item['id'] in holds:
            item['manual_review']=holds[item['id']]
            item['source_issue_codes']=item['source_issue_codes']+['MANUAL_REVIEW_HOLD']
    for domain in pools:
        pools[domain]=[pair for pair in pools[domain] if pair[0]['id'] not in holds]
    chosen=[]
    for source,(domain,budget) in DOMAINS.items():
        pool=pools[domain];pool.sort(key=lambda pair:hashlib.sha256(('FORGE_v01_review_20261001'+pair[0]['id']).encode()).hexdigest())
        for item,messages in pool[:budget]:item['proposed_v01_review_selection']=True;chosen.append((item,messages));by_domain[domain]['proposed_review_selection']+=1;sources[source]['proposed_review_selection']+=1
    formatter=QwenFormatter(assets);tokens=collections.Counter()
    for item,messages in chosen:
        formatted=formatter.encode(messages);item['qwen_tokens']=formatted['tokens'];item['assistant_tokens']=formatted['assistant_tokens'];tokens['formatted']+=formatted['tokens'];tokens['assistant']+=formatted['assistant_tokens']
        if formatted['over_context']:raise ValueError('proposed_example_over_context')
    output=ROOT/'data/sft/staging/forge-v01-review-curriculum.jsonl.gz'
    with output.open('wb') as dest,gzip.GzipFile(filename='',fileobj=dest,mode='wb',mtime=0) as gz:
        for item,_ in records:gz.write((json.dumps(item,separators=(',',':'))+'\n').encode())
    report={'version':'FORGE_SFT_v0.1_proposed_review_curriculum','unique_legacy_candidates':len(records),'stem_origin_candidates':sum(v['candidates'] for k,v in by_domain.items() if k not in {'legacy_conversations','operator_damaged_core','generic_conversation_low_priority'}),'selection_policy':'no_current_source_issue_codes; assistant_content_at_least80characters; technical_keyword_hint; deterministic_hash_order_with_domain_caps; manual_holds_omitted; all_unverified','domain_basis':'source_filename_not_validated_semantic_classification','manual_hold_records':len(holds),'requested_review_slots':sum(b for _,b in DOMAINS.values()),'selected_review_candidates':len(chosen),'approved_train_examples':0,'ready_drive_sft_examples':0,'drive_role':'source_reference_and_source_supported_QA_assembly_pending_not_raw_text_as_SFT','domains':dict(by_domain),'primary_sources':dict(sources),'repository_alias_counts_nonadditive':dict(origin_aliases),'keyword_capability_hints_nonadditive':dict(tags),'selected_qwen_tokens':dict(tokens),'zero_current_supervised_sources':['PLC_ladder','Siemens_TIA','worked_motor_drive_troubleshooting','source_visual_interpretation','verified_tool_use'],'zero_claim_basis':'no_verified_complete_examples_assembled; keyword_hints_or_reference_sources_do_not_establish_supervised_coverage','training_authorized':False}
    (ROOT/'reports/forge-v01-curriculum.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    datasets=json.loads((ROOT/'manifests/repository-datasets-final.json').read_text(encoding='utf-8'));families=[]
    for entry in datasets:
        families.append({'repository':entry['repository'],'path':entry['path'],'commit':entry['commit'],'sha256':entry['sha256'],'row_occurrences':entry['rows'],'recoverable_rows':entry['valid_rows'],'immediate_source_state':'VERIFIED','original_generation_state':'VERIFIED','verification_basis':'direct_user_attestation_20261001_all_Completions_and198SLM;LLM_exact_duplicate_lineage','synthetic':True,'providers':['OpenAI_API','Anthropic_API'],'row_provider_attribution':'UNKNOWN','generator_models':'UNKNOWN','generation_dates':'UNKNOWN','prompt_upstream_source':'UNKNOWN','generation_script':'UNKNOWN','known_transform_script':'Completions/build_sft.py' if entry['repository'].endswith('/Completions') else 'LLM_export_relationship_by_exact_message_hash' if entry['repository'].endswith('/LLM') else 'explicit_role_label_import','repository_code_license':'Apache2_README_claim_SLM_only;no_LICENSE_file_at_pinned_source','dataset_license':'UNKNOWN_no_explicit_dataset_license','copyright_ownership_basis':'VERIFIED_USER_ATTESTATION_plus_API_output_assignment_terms','training_usage_terms':'PARTIAL_generation_contract_and_intended_use_applicability_unverified','rights_state':'PARTIAL','release_state':'QUARANTINED','confidence':{'user_authored_synthetic_origin':'HIGH_user_attestation','exact_provider_model':'UNKNOWN','training_terms_compatibility':'UNKNOWN'},'evidence':['manifests/user-provenance-attestation-20261001.json','manifests/legacy-history-evidence.json','pinned_repository_READMEs_and_scripts'],'terms_sources':['https://openai.com/policies/services-agreement/','https://www.anthropic.com/legal/commercial-terms']})
    (ROOT/'manifests/provenance-rights-matrix.json').write_text(json.dumps({'families':families,'user_attestation_applies_to_all_legacy_candidates':True,'original_staging_provenance_preserved':True,'current_terms_are_not_proof_of_historical_contract':True,'unknown_provider_models_do_not_imply_unknown_synthetic_origin':True},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':build(Path(sys.argv[1]))
