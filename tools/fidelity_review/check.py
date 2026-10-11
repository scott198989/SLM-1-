"""Read-only evidence validation. This tool cannot grant semantic or release approval."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from PIL import Image, ImageChops

PASS = 'FULL_PAGE_VISIBLE_FIDELITY_PASS'
PARTIAL = 'PARTIAL_UNRESOLVED'
GATES = {'development','evaluation_gold','external_publication','rag','training'}
REVIEW_CHECKS = {'full_page_inspected','reading_order_reviewed','all_semantic_groups_accounted_for',
                'figures_labels_relations_reviewed','source_discrepancies_separated','unresolved_ledger_explicit'}

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def latest_records(root):
    latest, versions = {}, {}
    for path in sorted((Path(root)/'pages').glob('*.json')):
        record = read(path)
        key = record['page_id']
        revision = record.get('review_revision', 1)
        if (key, revision) in versions:
            raise ValueError(f'duplicate revision: {key} {revision}')
        versions[key, revision] = (path, record)
        if revision > latest.get(key, (None, {}))[1].get('review_revision', 0):
            latest[key] = (path, record)
    for (key, revision), (path, record) in versions.items():
        if revision > 1:
            previous = versions.get((key, revision-1))
            if not previous or record.get('supersedes', {}).get('sha256') != digest(previous[0]):
                raise ValueError(f'broken revision chain: {path.name}')
            if not Path(record['supersedes']['path']).samefile(previous[0]):
                raise ValueError(f'wrong revision parent: {path.name}')
    return latest

def validate_record(record, source):
    """Check a single record's invariants; raise ValueError on a boundary failure."""
    def require(condition, message):
        if not condition:
            raise ValueError(f"{record.get('page_id', '?')}: {message}")
    for key in ('page_id','source_id','source_number','source_sha256','original_page'):
        require(record.get(key) == source.get(key), f'source binding {key}')
    status = record.get('visible_fidelity_status')
    require(status in {PASS, PARTIAL}, 'invalid review status')
    unresolved = record.get('unresolved_visible_content')
    require(isinstance(unresolved, list), 'missing unresolved ledger')
    require((status == PARTIAL) == bool(unresolved), 'status/unresolved mismatch')
    require(record.get('full_page_visible_fidelity_qualified') == (status == PASS), 'pass boolean mismatch')
    require(record.get('downstream_approved') is False, 'downstream approval changed')
    require(set(record.get('quarantine', {})) == GATES, 'missing quarantine gate')
    require(all(v == 'PROHIBITED' for v in record['quarantine'].values()), 'quarantine released')
    require(record['quarantine'] == source['quarantine'], 'source quarantine changed')
    require(record.get('scope') and record.get('review_method'), 'missing review scope/method')
    require(record.get('representation_convention'), 'missing representation convention')
    require(REVIEW_CHECKS <= record.get('review_checks', {}).keys() and all(record['review_checks'][k] is True for k in REVIEW_CHECKS), 'review attestation incomplete')
    require(set(record.get('reviewed_transcription', {})) == {'upper','lower'}, 'missing slide half')
    for half, text in record['reviewed_transcription'].items():
        require(isinstance(text, str) and bool(text.strip()), f'empty {half} transcript')
    def strings(node):
        if isinstance(node, str):
            require(not any(ord(c)<32 and c not in '\n\r\t' for c in node), 'unexpected control character')
        elif isinstance(node, dict):
            for value in node.values(): strings(value)
        elif isinstance(node, list):
            for value in node: strings(value)
    strings(record)
    expected = source['preserved_render']
    require(record['preserved_page']['sha256'] == expected['sha256'], 'preserved page hash binding')
    require(Path(record['preserved_page']['path']).samefile(expected['path']), 'preserved page path binding')
    ids = set()
    with Image.open(record['preserved_page']['path']) as page:
        page = page.convert('RGB')
        for figure in record.get('figures', []):
            fid = figure['figure_id']
            require(re.fullmatch('F-'+re.escape(record['page_id'])+r'-\d{2}', fid) is not None, 'foreign figure ID')
            require(fid not in ids, 'duplicate figure ID'); ids.add(fid)
            require(figure.get('downstream_approved') is False, 'figure released')
            require(figure.get('description_state') == 'REVIEWED' and figure.get('reviewed_description'), 'unreviewed figure')
            require(isinstance(figure.get('visible_labels'), list) and isinstance(figure.get('relationships'), list), 'missing figure labels/relations inventory')
            for key in ('source_id','source_sha256','original_page'):
                require(figure.get(key) == source[key], f'figure {key}')
            require(figure.get('render_sha256') == source['render']['sha256'], 'figure render binding')
            require(figure.get('pixel_frame') == list(page.size), 'figure pixel frame')
            box = figure['bbox_pixels']
            require(len(box)==4 and all(type(x) is int for x in box), 'invalid crop coordinates')
            require(0 <= box[0] < box[2] <= page.width and 0 <= box[1] < box[3] <= page.height, 'crop outside page')
            with Image.open(figure['asset']['path']) as crop:
                expected_crop = page.crop(box)
                require(crop.size == expected_crop.size, 'crop size mismatch')
                require(ImageChops.difference(crop.convert('RGB'), expected_crop).getbbox() is None, 'crop pixels differ')
    mentioned = set(re.findall(r'F-s\d{2}-p\d{2}-\d{2}', '\n'.join(record['reviewed_transcription'].values())))
    require(mentioned <= ids, 'dangling figure cross-reference')
    tables = record.get('table_references', [])
    for table_ref in tables:
        table = table_ref['reviewed_table']
        require(table_ref['table_id'] == table['table_id'], 'table ID mismatch')
        require(table['source_id'] == source['source_id'] and table['document_sha256'] == source['source_sha256'], 'table source mismatch')
        require(table['original_page'] == source['original_page'], 'table page mismatch')
        require(table['render_sha256'] == source['render']['sha256'], 'table render mismatch')
        require(table.get('downstream_approved') is False, 'table released')
        require(table.get('headers_visible') and table.get('rows_visible'), 'empty table')
        require(all(len(row)==len(table['headers_visible']) for row in table['rows_visible']), 'table column mismatch')
        require(table.get('visual_cell_review') == 'ALL_LISTED_CELLS_READ_FROM_RENDER', 'table review missing')
        require(digest(table['crop_path']) == table['crop_sha256'], 'table crop changed')
    table_mentions = set(re.findall(r's\d{2}-p\d{2}-(?:latent-heats|solid-expansion|liquid-expansion|mirror-signs|refractive-ind(?:ex|ices))', '\n'.join(record['reviewed_transcription'].values())))
    require(table_mentions <= {t['table_id'] for t in tables}, 'dangling table cross-reference')

def validate_package(root, source_ledger, expected_count=38):
    root = Path(root)
    source_data = read(source_ledger)
    sources = {p['page_id']:p for p in source_data['pages']}
    if len(sources) != expected_count or len(source_data['pages']) != expected_count:
        raise ValueError('candidate scope count/uniqueness mismatch')
    exclusions = {(r['source_number'],r['original_page']) for r in source_data.get('excluded_pages', [])}
    if exclusions & {(r['source_number'],r['original_page']) for r in sources.values()}:
        raise ValueError('excluded page in candidate scope')
    records = latest_records(root)
    if set(records) != set(sources):
        raise ValueError('missing or extra page reviews')
    checked = set()
    def check_refs(node):
        if isinstance(node, dict):
            if {'path','sha256'} <= node.keys():
                path=Path(node['path']);pair=(str(path.resolve()), node['sha256'])
                if pair not in checked:
                    if not path.is_file() or digest(path) != node['sha256']:
                        raise ValueError(f'changed/missing evidence: {path}')
                    if 'bytes' in node and path.stat().st_size != node['bytes']:
                        raise ValueError(f'byte count mismatch: {path}')
                    checked.add(pair)
            for value in node.values(): check_refs(value)
        elif isinstance(node, list):
            for value in node: check_refs(value)
    check_refs(source_data)
    figures = 0
    tables = 0
    for key,(path,record) in records.items():
        check_refs(record)
        validate_record(record,sources[key])
        figures += len(record['figures']); tables += len(record['table_references'])
    ledger=read(root/'no-silent-omission-ledger.json')
    if len(ledger['pages']) != expected_count or {r['page_id'] for r in ledger['pages']} != set(sources):
        raise ValueError('output ledger scope mismatch')
    check_refs(ledger)
    for row in ledger['pages']:
        path,record=records[row['page_id']]
        if row['record']['sha256']!=digest(path) or row['status']!=record['visible_fidelity_status'] or row['unresolved']!=record['unresolved_visible_content']:
            raise ValueError('stale output ledger')
        if row.get('downstream_approved') is not False:
            raise ValueError('ledger release changed')
    counts=dict(Counter(record['visible_fidelity_status'] for _,record in records.values()))
    if any(ledger.get('counts',{}).get(status,0) != counts.get(status,0) for status in (PASS,PARTIAL,'PENDING')):
        raise ValueError('ledger status counts mismatch')
    if ledger.get('downstream_releases') != 0 or ledger.get('figure_occurrences') != figures:
        raise ValueError('ledger totals mismatch')
    if {tuple(x) for x in ledger['excluded_pages']} != exclusions:
        raise ValueError('exclusion ledger changed')
    return {'structural_validation':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),
            'candidate_pages':len(records),'counts':counts,'figure_occurrences':figures,'table_occurrences':tables,
            'verified_unique_file_hashes':len(checked),'excluded_pages':len(exclusions),'downstream_releases':0,
            'semantic_status_origin':'Recorded single model-assisted visual review; structural validator does not grant semantic approval.',
            'source_ledger_sha256':digest(source_ledger),'omission_ledger_sha256':digest(root/'no-silent-omission-ledger.json')}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path);parser.add_argument('source_ledger',type=Path)
    parser.add_argument('--expected-count',type=int,default=38)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    result=validate_package(args.package,args.source_ledger,args.expected_count)
    encoded=json.dumps(result,indent=2)+'\n'
    if args.report:
        with args.report.open('x',encoding='utf8') as stream:stream.write(encoded)
    print(encoded)

if __name__=='__main__':main()
