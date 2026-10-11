"""Pinned local catalog/fan-out over accepted single-chunk reference packages.

No merged index, model, network, numerical execution or shortened citation.
The frozen launcher supplies the only trusted catalog anchor.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import types


class CatalogError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_pinned(descriptor):
    if not isinstance(descriptor, dict):
        raise CatalogError('invalid_pin_descriptor')
    path = Path(descriptor['path'])
    if not path.is_absolute() or path.is_symlink():
        raise CatalogError('invalid_pinned_path')
    data = path.read_bytes()
    if digest(data) != descriptor['sha256'] or len(data) != descriptor['bytes']:
        raise CatalogError('pinned_file_changed:' + str(path))
    return data


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CatalogError('duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise CatalogError('nonfinite_json_constant')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def captured_runtime(descriptors):
    """Compile only the captured, pinned bytes; never hash then import a path."""
    if set(descriptors) != {'__init__', 'citation_pilot', 'reference_excerpt'}:
        raise CatalogError('runtime_module_set')
    captured = {key: read_pinned(value) for key, value in descriptors.items()}
    if captured['__init__'] != b'':
        raise CatalogError('unexpected_runtime_initializer')
    name = '_forge_accepted_reference_' + digest(captured['citation_pilot'])[:16]
    package = types.ModuleType(name)
    package.__path__ = []
    sys.modules[name] = package
    for key in ['citation_pilot', 'reference_excerpt']:
        module_name = name + '.' + key
        module = types.ModuleType(module_name)
        module.__package__ = name
        module.__file__ = descriptors[key]['path']
        sys.modules[module_name] = module
        exec(compile(captured[key], module.__file__, 'exec'), module.__dict__)
    return sys.modules[name + '.reference_excerpt'].request


def validate_query(query, *, allow_empty=False):
    if not isinstance(query, str) or len(query) > 2000 or any(ord(c) < 32 for c in query):
        raise CatalogError('invalid_query')
    if not allow_empty and not query.strip():
        raise CatalogError('empty_query')


def prepare(catalog_path, expected_sha256):
    """Verify all nine packages before any user-visible result, including catalog."""
    path = Path(catalog_path)
    if path.is_symlink():
        raise CatalogError('catalog_symlink')
    payload = path.read_bytes()
    if digest(payload) != expected_sha256:
        raise CatalogError('catalog_anchor_drift')
    catalog = strict_json(payload)
    if catalog.get('schema') != 'forge.nine-reference-catalog.v1' or len(catalog.get('entries', [])) != 9:
        raise CatalogError('catalog_schema_or_count')
    for pin in catalog['acceptance_evidence']:
        read_pinned(pin)
    request = captured_runtime(catalog['runtime'])
    prepared = []
    ids = set()
    for entry in catalog['entries']:
        identifier = entry['id']
        if not re.fullmatch(r'[a-z][a-z0-9-]{1,63}', identifier) or identifier in ids:
            raise CatalogError('catalog_identifier')
        ids.add(identifier)
        for pin in entry['dependency_pins']:
            read_pinned(pin)
        root = Path(entry['data_root'])
        manifest_path = Path(entry['manifest']['path'])
        index_path = Path(entry['index']['path'])
        if not root.is_absolute() or any(not p.resolve().is_relative_to(root.resolve()) for p in [manifest_path, index_path, Path(entry['approved_chunk']['path'])]):
            raise CatalogError('package_path_scope')
        manifest = strict_json(read_pinned(entry['manifest']))
        read_pinned(entry['index'])
        chunk = strict_json(read_pinned(entry['approved_chunk']))
        if (Path(manifest['source_root']).resolve() != root.resolve()
                or manifest['chunk_ids'] != [entry['chunk_id']]
                or chunk['id'] != entry['chunk_id']):
            raise CatalogError('package_identity')
        response = request(index_path, manifest_path,
                           expected_manifest_sha256=entry['manifest']['sha256'],
                           task='quote_reference', chunk_id=entry['chunk_id'])
        expected_citation = {k: v for k, v in chunk.items() if k != 'text'}
        if (response.get('status') != 'EXACT_SOURCE_QUOTE'
                or response.get('quote') != chunk['text']
                or response.get('citation') != expected_citation
                or response.get('answer') is not None
                or response.get('generator_used') is not False
                or response.get('training') is not False):
            raise CatalogError('complete_reference_context_mismatch')
        if entry['reviewed_annotation_required']:
            note = response['citation'].get('scientific_assumptions', {})
            if (note.get('type') != 'SEPARATE_REVIEWED_ANNOTATION_NOT_SOURCE_QUOTATION'
                    or not note.get('markdown') or not note.get('corroborating_sources')
                    or digest(note['markdown'].encode()) != entry['annotation_sha256']):
                raise CatalogError('reviewed_annotation_missing_or_changed')
        prepared.append((entry, response))
    return catalog, request, prepared


def lookup(catalog_path, expected_sha256, action='catalog', query='', reference_id=None):
    if action not in {'catalog', 'find', 'quote'}:
        raise CatalogError('unsupported_reference_action')
    validate_query(query, allow_empty=action != 'find')
    if action == 'quote' and (query or not isinstance(reference_id, str)):
        raise CatalogError('quote_requires_only_catalog_id')
    catalog, request, packages = prepare(catalog_path, expected_sha256)
    base = {'tool': 'FORGE academic reference lookup', 'answer': None,
            'generator_used': False, 'training': False, 'calculation_performed': False,
            'packages_verified': len(packages), 'capabilities': catalog['capabilities'],
            'acceptance': catalog['acceptance'], 'citation_context_required': True}
    if action == 'catalog':
        terms = re.findall(r'\w+', query.casefold())
        entries = []
        for entry, _ in packages:
            summary = {k: entry[k] for k in ['id', 'label', 'topics', 'scope', 'source_title', 'page', 'reviewed_annotation_required']}
            haystack = json.dumps(summary, ensure_ascii=False).casefold()
            if all(term in haystack for term in terms):
                entries.append(summary)
        return dict(base, status='REFERENCE_CATALOG', query=query, entries=entries,
                    search_rule='Catalog metadata substring filter; no source answer is inferred.')
    if action == 'quote':
        matches = [(entry, response) for entry, response in packages if entry['id'] == reference_id]
        if not matches:
            raise CatalogError('unknown_reference_id')
        entry, response = matches[0]
        return dict(base, status='EXACT_REFERENCE_WITH_COMPLETE_CONTEXT',
                    catalog_id=entry['id'], label=entry['label'], package_result=response)
    results = []
    for entry, verified_quote in packages:
        response = request(entry['index']['path'], entry['manifest']['path'],
                           expected_manifest_sha256=entry['manifest']['sha256'],
                           task='find_reference', query=query)
        if (response.get('answer') is not None or response.get('generator_used') is not False
                or response.get('training') is not False):
            raise CatalogError('unexpected_reference_capability')
        hits = response.get('references', [])
        if response['status'] not in {'NO_ANSWER', 'REFERENCE_CANDIDATES'}:
            raise CatalogError('unexpected_reference_status')
        if hits:
            if (len(hits) != 1 or hits[0]['id'] != entry['chunk_id']
                    or hits[0]['text'] != verified_quote['quote']
                    or hits[0]['citation'] != verified_quote['citation']):
                raise CatalogError('search_context_changed_or_shortened')
            results.append({'catalog_id': entry['id'], 'label': entry['label'], 'package_result': response})
    return dict(base, status='REFERENCE_CANDIDATES' if results else 'NO_REFERENCE_MATCH',
                query=query, results=results,
                search_rule='Separate accepted lexical OR searches; stable catalog order, no merged index or cross-index score ranking. Candidates are not answers.')


def render_text(result):
    lines = ['FORGE academic references - lookup only',
             'Calculation prototype: separate eight-function structured tool. General Qwen generation: unavailable here.', '']
    if result['status'] == 'REFERENCE_CATALOG':
        lines.append(f"{len(result['entries'])} catalog matches; all {result['packages_verified']} packages verified.")
        for entry in result['entries']:
            lines.extend([f"{entry['id']} | {entry['label']} | page {entry['page']}",
                          '  ' + entry['scope']])
        lines.extend(['', 'Use find <terms> to search all nine, or quote <catalog-id> for the complete reference.'])
    else:
        items = result.get('results', []) if 'results' in result else [result]
        for item in items:
            response = item['package_result']
            hits = response.get('references', []) if 'references' in response else [{'text': response['quote'], 'citation': response['citation']}]
            for hit in hits:
                citation = hit['citation']
                lines.extend([item['catalog_id'] + ' | ' + item['label'],
                              'ORIGINAL SOURCE EXCERPT - unaltered reviewed transcription:', hit['text'],
                              'SCOPE / QUALIFICATION:', citation.get('scientific_scope_note', '')])
                science = citation.get('scientific_assumptions')
                if science:
                    lines.extend(['SEPARATE REVIEWED ANNOTATION / CONTEXT - not original source wording:',
                                  science.get('markdown', json.dumps(science, ensure_ascii=False, indent=2))])
                lines.append('')
        if not items:
            lines.append('No lexical reference match. No answer or calculation was produced.')
    # A readable view never substitutes for or strips the accepted complete record.
    lines.extend(['', 'COMPLETE JSON RECORD - all original citation, annotation, qualification and provenance fields:',
                  json.dumps(result, ensure_ascii=False, indent=2)])
    return '\n'.join(lines) + '\n'


def main(catalog_path, expected_sha256, argv=None):
    parser = argparse.ArgumentParser(description='Discover/search nine pinned academic references. No calculation or Qwen generation.')
    parser.add_argument('--json', action='store_true', help='Return the complete JSON record without the readable preface.')
    commands = parser.add_subparsers(dest='action')
    catalog = commands.add_parser('catalog', help='List all references or filter catalog metadata.')
    catalog.add_argument('query', nargs='?', default='')
    search = commands.add_parser('find', help='Search all nine independently; results are references, not answers.')
    search.add_argument('query')
    quote = commands.add_parser('quote', help='Show one exact excerpt with complete context.')
    quote.add_argument('reference_id')
    args = parser.parse_args(argv)
    try:
        result = lookup(catalog_path, expected_sha256, action=args.action or 'catalog',
                        query=getattr(args, 'query', ''), reference_id=getattr(args, 'reference_id', None))
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n' if args.json else render_text(result)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print('Reference lookup refused: ' + str(exc), file=sys.stderr)
        return 2
    print(output, end='')
    return 0
