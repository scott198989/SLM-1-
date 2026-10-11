"""Bounded frozen query encoding; copy beside reviewed Windows GPU guard.

GPU mode requires the guard; explicit --cpu hides CUDA and is run with a bounded
outer timeout. No documents are re-encoded and no training, network, or answer
generation occurs. Inputs are pinned before ML import.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from gpu_telemetry import ROOT,GPU_UUID,atomic_json,utc

REV='914f7f89142e33e77833254d9c9b90c3cef7303b'
RUN=Path(sys.argv[1]).resolve()
if not RUN.is_relative_to(ROOT/'logs'):raise ValueError('Invalid output path')
CPU_ONLY=len(sys.argv)==3 and sys.argv[2]=='--cpu'
if len(sys.argv)>2 and not CPU_ONLY:raise ValueError('Unknown inference mode')
if CPU_ONLY:RUN.mkdir(parents=True,exist_ok=False)

def main():
    if not CPU_ONLY:
        owned=json.loads((RUN/'owned-workload.json').read_text('utf-8'))
        if owned['pid']!=os.getpid() or owned.get('simulation') is not False or not owned.get('job_kill_on_close'):
            raise ValueError('Guard-owned live job required')
    request=json.loads((ROOT/'query-request.json').read_text('utf-8'))
    payload=Path(request['probes']['path']).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=request['probes']['sha256']:raise ValueError('Probe drift')
    probes=json.loads(payload)
    if probes.get('content_scope')!='OWNED_CODE_ONLY' or probes.get('held_academic_content') is not False or probes.get('sealed_eval_content') is not False:
        raise ValueError('Scope violation')
    rows=probes['probes']
    if not 1<=len(rows)<=32 or len({x['id'] for x in rows})!=len(rows):raise ValueError('Query bound violated')
    if any(not isinstance(x['query'],str) or not 1<=len(x['query'])<=2048 for x in rows):raise ValueError('Text bound violated')
    old=Path(request['verified_runtime_root']).resolve();modeldir=old/'model'/REV
    receipt_path=old/'evidence/model-download.json'
    if hashlib.sha256(receipt_path.read_bytes()).hexdigest()!=request['model_receipt_sha256']:raise ValueError('Model receipt drift')
    receipt=json.loads(receipt_path.read_text('utf-8'))
    if receipt.get('status')!='VERIFIED_PINNED_ARTIFACTS' or receipt['revision']!=REV:raise ValueError('Model not qualified')
    for row in receipt['files']:
        with (modeldir/row['path']).open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:raise ValueError('Model artifact drift')
    os.environ.update(CUDA_VISIBLE_DEVICES='-1' if CPU_ONLY else GPU_UUID,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false',HF_HOME=str(old/'hf-cache'))
    import torch
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer
    torch.set_num_threads(4)
    if not CPU_ONLY and (not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()):raise RuntimeError('CUDA/BF16 unavailable')
    def synchronize():
        if not CPU_ONLY:torch.cuda.synchronize()
    prompts=json.loads((modeldir/'config_sentence_transformers.json').read_text('utf-8'))['prompts']
    tokenizer=AutoTokenizer.from_pretrained(str(modeldir),local_files_only=True,trust_remote_code=False)
    counts=[len(tokenizer(prompts['SearchQuery']+x['query'],truncation=False)['input_ids']) for x in rows]
    if max(counts)>1024:raise ValueError('No truncation permitted')
    started=time.perf_counter()
    model=SentenceTransformer(str(modeldir),device='cpu' if CPU_ONLY else 'cuda',local_files_only=True,trust_remote_code=False,
        config_kwargs={'vision_config':None,'audio_config':None},model_kwargs={'dtype':torch.float32 if CPU_ONLY else torch.bfloat16,'attn_implementation':'eager'})
    model.max_seq_length=1024;model.eval()
    for parameter in model.parameters():parameter.requires_grad_(False)
    synchronize();load_seconds=time.perf_counter()-started
    encoded=[];timings=[]
    with torch.inference_mode():
        for i,row in enumerate(rows):
            synchronize();started=time.perf_counter()
            vector=model.encode([row['query']],prompt_name='SearchQuery',batch_size=1,show_progress_bar=False,convert_to_tensor=True)
            synchronize();timings.append(time.perf_counter()-started)
            vector=torch.nn.functional.normalize(vector.float(),p=2,dim=-1)
            if list(vector.shape)!=[1,768] or not torch.isfinite(vector).all() or abs(vector.norm().item()-1)>1e-5:raise ValueError('Invalid embedding')
            encoded.append({'id':row['id'],'query':row['query'],'vector':vector[0].cpu().tolist()})
            atomic_json(RUN/'progress.json',{'utc':utc(),'encoded_queries':i+1,'total':len(rows)})
            time.sleep(.1)
    atomic_json(RUN/'query-vectors.json',{'model_revision':REV,'probes_sha256':request['probes']['sha256'],'queries':encoded,'device':'cpu' if CPU_ONLY else 'cuda','dtype':'float32' if CPU_ONLY else 'bfloat16'})
    atomic_json(RUN/'inference-result.json',{'status':'COMPLETED','utc':utc(),'training':False,'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),
      'model_revision':REV,'queries':len(rows),'documents_reencoded':0,'token_counts':counts,'dimensions':768,
      'model_load_seconds':load_seconds,'query_seconds':timings,'peak_allocated_bytes':0 if CPU_ONLY else torch.cuda.max_memory_allocated(),
      'peak_reserved_bytes':0 if CPU_ONLY else torch.cuda.max_memory_reserved(),'device':'cpu' if CPU_ONLY else 'cuda','dtype':'float32' if CPU_ONLY else 'bfloat16',
      'purpose':'NEW_SAME_AGENT_DEVELOPMENT_PROBES_NOT_BLIND_EVALUATION'})

if __name__=='__main__':
    with (RUN/'workload-console.txt').open('x',encoding='utf-8',buffering=1) as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        try:
            # The supervisor writes its process receipt immediately after launch.
            until=time.monotonic()+2
            while not CPU_ONLY and not (RUN/'owned-workload.json').exists() and time.monotonic()<until:time.sleep(.01)
            main()
        except BaseException as exc:
            traceback.print_exc();atomic_json(RUN/'inference-failure.json',{'utc':utc(),'error':repr(exc)})
            raise SystemExit(1)
