"""Generate aggregate-only phase manifests; never copy private source text."""
import collections,dataclasses,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from forge_data.promotion import Proof,EvidenceState,Stage,ALLOWED
def write(path,value):
    (ROOT/path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def main():
    properties={}
    for field in dataclasses.fields(Proof):
        properties[field.name]={'type':'string','enum':[v.value for v in EvidenceState]} if field.name in {'provenance','rights'} else {'type':'boolean'} if isinstance(field.default,bool) else {'type':'string'}
    write('schemas/promotion-proof.schema.json',{'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','additionalProperties':False,'required':list(properties),'properties':properties})
    write('configs/promotion-transitions.json',{'stages':[s.value for s in Stage],'allowed':{s.value:sorted(t.value for t in targets) for s,targets in ALLOWED.items()},'evidence_states':[s.value for s in EvidenceState],'executable_policy':'src/forge_data/promotion.py'})
    asset=json.loads((ROOT.parent/'.cache/qwen-tokenizer-only/manifest.json').read_text())
    write('manifests/qwen-tokenizer-assets.json',asset)
    engineering=ROOT/'src/forge_tools/engineering.py';source=ROOT/'.audit-sources/SLM-1-other/src/forge1/engineering.py'
    if engineering.read_bytes()!=source.read_bytes():raise ValueError('unexpected_engineering_transplant_change')
    write('manifests/tool-source-evidence.json',{'engineering':{'repository':'scott198989/SLM-1-','commit':'6ecf683b7d993f47730d34d07cb2e9c8dd9397d0','path':'src/forge1/engineering.py','sha256':hashlib.sha256(engineering.read_bytes()).hexdigest(),'transplant':'byte_identical','tested':'independent_dimensional_numeric_and_refusal_cases','code_rights':'user_owned_repository_use_authorized_in_task; no upstream license inferred'},'statistics':{'implementation':'new explicit contracts inspired by legacy audit','repairs':['Welch_Satterthwaite_df_and_CI','oneway_ANOVA_groups_contract','multicolumn_OLS_not_X0_placeholder','nonfinite_output_rejection'],'limits':['no_causal_proof','SPC_known_baseline_sigma_only','no_estimated_XbarR_or_WECO_claim']},'router':{'numeric_claim_absent':'NOT_APPLICABLE','arbitrary_code_execution':False,'result_status':'COMPUTED_not_answer_certification'}})
    expert=ROOT.parent/'.cache/qwen-moe-v4576-inspection.py.txt'
    write('manifests/qwen-runtime-source-evidence.json',{'transformers_revision':'v4.57.6','path':'src/transformers/models/qwen3_moe/modeling_qwen3_moe.py','source_sha256':hashlib.sha256(expert.read_bytes()).hexdigest(),'observed_lines':{'gate_up_down_nnLinear':[203,204,205],'experts_ModuleList':222},'runtime_quantization_tested':False,'required_post_load_audit':'all_expert_storage_quantized; no_FP16_expert_fallback','references':['https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/qwen3_moe/modeling_qwen3_moe.py','https://pytorch.org/blog/pytorch-2-7/']})
    audit=json.loads((ROOT.parent/'reports/academic-final-ledger-audit-20261001.json').read_text(encoding='utf-8'))
    subjects=collections.defaultdict(collections.Counter);mimes=collections.defaultdict(collections.Counter);total=collections.Counter()
    for item in audit['file_cube_additive']:
        subjects[item['subject']][item['file_status']]+=item['files'];mimes[item['mime']][item['file_status']]+=item['files'];total[item['file_status']]+=item['files']
    if sum(total.values())!=1947:raise ValueError('academic_aggregate_does_not_reconcile')
    public={'snapshot':audit['at'],'academic_scope_only':True,'files_total':1947,'status_totals':dict(total),'subjects':dict(subjects),'mime_counts':dict(mimes),'private_paths_ids_text_assets_omitted':True,'approved_sft_examples':0,'production_rag_approved':False,'family_analysis_and_review_rag':'see_private_final_receipts_not_approved_by_this_aggregate'}
    write('reports/academic-aggregate-final-extraction.json',public)
    lines=['# Academic subject/status ledger','','Aggregate counts only. Private file IDs, paths and text are omitted. Extraction is not training approval.','','| Subject | Extracted | Duplicate | Blocked | Excluded |','|---|---:|---:|---:|---:|']
    for subject,c in sorted(subjects.items()):lines.append(f"| {subject} | {c['extracted_needs_review']} | {c['duplicate']} | {c['blocked']} | {c['excluded']} |")
    (ROOT/'reports/ACADEMIC_AGGREGATE_COUNTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    write('manifests/data-role-allocation.json',{'current':{'unique_legacy_staging':34463,'review_selection':json.loads((ROOT/'reports/forge-v01-curriculum.json').read_text())['selected_review_candidates'],'approved_sft':0,'sealed_eval':0,'production_rag':0},'proposed':{'SFT':'complete verified engineering examples; source_supported_Drive_QA_assembly_pending','RAG':'faithful approved academic reference chunks and visual dependencies','EVAL':'independent_private_gold_families_design_not_task_data','TOOLS':'deterministic_units_numeric_statistics_DOE_SPC_with_independent_tests','QUARANTINE':'damage_unknown_answers_rights_split_visual_dependencies','ARCHIVE':'irrelevant_admin_duplicate_aliases_historical_cores_unavailable_format_receipts'},'Drive_engineering_subject':'heterogeneous508_sources_content_classification_needed','generic_conversations':'18391_low_priority_not_selected','private_Drive_artifacts_public':False})
    print(json.dumps({'generated':'phase_manifests_and_schemas','academic_status':dict(total)}))
if __name__=='__main__':main()
