"""Check every staging row and its lineage, then create deterministic transport.
No candidate is promoted to approved data by this validator.
"""
import collections, gzip, hashlib, json
from pathlib import Path
from audit_repositories import canonical, record_hash
from quality_checks import inspect_sensitive
ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / 'data/sft/staging/consolidated-20261001-v2'

def validate():
    report = json.loads((ROOT/'reports/consolidated-audit.json').read_text(encoding='utf-8'))
    ids, hashes, states = set(), set(), collections.Counter()
    origins = 0
    with (STAGING/'candidates.jsonl').open(encoding='utf-8') as data, gzip.open(STAGING/'provenance.jsonl.gz', 'rt', encoding='utf-8') as lineage:
        import itertools
        for number, pair in enumerate(itertools.zip_longest(data, lineage), 1):
            a, b = pair
            if a is None or b is None:
                raise ValueError('candidate_provenance_length_mismatch')
            row, meta = json.loads(a), json.loads(b)
            if set(row) != {'id', 'messages'} or row['id'] != meta['id']:
                raise ValueError('invalid_candidate_envelope_or_join')
            messages, error = canonical(row)
            if error or messages != row['messages']:
                raise ValueError('invalid_or_noncanonical_messages')
            digest = record_hash(messages)
            if row['id'] != 'repo-'+digest[:24] or row['id'] in ids or digest in hashes:
                raise ValueError('duplicate_or_invalid_record_id')
            if inspect_sensitive(json.dumps(row, ensure_ascii=False)):
                raise ValueError('privacy_gate_failed')
            if meta['technical_correctness'] != 'unverified' or meta['split'] != 'unassigned':
                raise ValueError('unexpected_release_or_split_claim')
            if meta['review_status'] not in {'needs_review','quarantined'}:
                raise ValueError('invalid_staging_status')
            if bool(meta['issue_codes']) != (meta['review_status'] == 'quarantined'):
                raise ValueError('issue_status_mismatch')
            if not meta['origins']:
                raise ValueError('missing_lineage')
            for origin in meta['origins']:
                if origin['repository'] not in {'scott198989/Completions','scott198989/LLM','scott198989/SLM'} or not origin['sha256'] or origin['line'] < 1:
                    raise ValueError('invalid_lineage_origin')
            origins += len(meta['origins'])
            ids.add(row['id']); hashes.add(digest); states[meta['review_status']] += 1
    if len(ids) != report['unique_candidate_records'] or dict(states) != report['statuses'] or origins != report['valid_row_occurrences']:
        raise ValueError('audit_totals_mismatch')
    if report['ready_sft_records'] != 0 or report['ready_rag_chunks'] != 0:
        raise ValueError('unexpected_release_claim')
    compressed = STAGING/'candidates.jsonl.gz'
    with (STAGING/'candidates.jsonl').open('rb') as source, compressed.open('wb') as dest:
        with gzip.GzipFile(filename='', fileobj=dest, mode='wb', mtime=0) as gz:
            import shutil
            shutil.copyfileobj(source, gz)
    files=[]
    for path in (STAGING/'candidates.jsonl', compressed, STAGING/'provenance.jsonl.gz'):
        files.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()})
    receipt = {'validation':'passed','records_checked':len(ids),'origin_occurrences_checked':origins,'statuses':dict(states),'approved_records':0,'checks':['canonical_messages','record_hashes','no_exact_duplicates','privacy_screen','one_to_one_lineage_join','review_states','source_allowlist','audit_count_reconciliation'],'files':files}
    (ROOT/'reports/staging-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))
    return receipt
if __name__ == '__main__':
    validate()
