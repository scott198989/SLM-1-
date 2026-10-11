"""Build, review, and explicitly run a structured request. No free-form inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

from tools.owned_retrieval import answerability, harness

LABELS = {
    'convert_units': 'Convert units of the same physical quantity',
    'check_dimensional_equation': 'Compare dimensions of two unit expressions',
    'axial_stress': 'Uniform static axial tension',
    'dc_motor': 'Ideal steady-state DC motor',
    'thermal_expansion': 'Free linear thermal expansion',
    'second_order_step': 'Underdamped second-order unit step',
    'series_rlc': 'Ideal series RLC circuit',
    'quadratic_roots': 'Real roots of a quadratic',
}
SECTIONS = ['input_contract', 'output_contract', 'conditions', 'limitations', 'implementation']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha_value(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def save_new(path, value):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return path, harness.digest(path)


def show_value(value):
    if value is None:
        return 'UNKNOWN / NOT PROVIDED'
    if isinstance(value, dict) and 'value' in value:
        return f"{show_value(value.get('value'))} {value.get('unit') or '[UNIT MISSING]'}"
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


class RequestSession:
    def __init__(self, target_path, target_sha):
        if harness.digest(target_path) != target_sha:
            raise harness.IntegrityError('Review target hash does not match the trusted launcher.')
        self.target_sha = target_sha
        self.target_path = Path(target_path).resolve()
        self.target = harness.read_json(target_path)
        self._check_code()
        source = self.target['manifest']
        self.gate = answerability.AnswerabilityGate(harness.LocalRetriever(source['path'], source['sha256']))
        self.catalog = self.gate.catalog()
        if sha_value(self.catalog) != self.target['catalog_sha256']:
            raise harness.IntegrityError('Reviewed capability contract changed.')
        if sha_value(self.gate.numerical_policy()) != self.target['numerical_policy_sha256']:
            raise harness.IntegrityError('Reviewed numerical policy changed.')

    def _check_code(self):
        if harness.digest(self.target_path) != self.target_sha:
            raise harness.IntegrityError('Review target changed during the session.')
        gate_dir = Path(answerability.__file__).parent
        if set(self.target['gate_files']) != {'answerability.py', 'harness.py', 'numerical_policy.py'}:
            raise harness.IntegrityError('A complete corrected gate review target is required.')
        for name, expected in self.target['gate_files'].items():
            if harness.digest(gate_dir / name) != expected:
                raise harness.IntegrityError('Reviewed gate changed; update its review target before using this interface.')

    def template(self, capability, mode):
        contract = self.catalog[capability]
        conditions = contract['conditions']['source_assumptions'] + contract['conditions']['gate_policy_conditions']
        arguments = {}
        if mode == 'calculate':
            for field, spec in contract['input_contract'].items():
                arguments[field] = {'value': None, 'unit': ''} if 'canonical_unit' in spec else ('' if spec['declaration'] == 'str' else None)
        return {'capability': capability, 'mode': mode,
                'requested': list(contract['output_contract']) if mode == 'calculate' else ['limitations'],
                'arguments': arguments,
                'conditions': {name: None for name in conditions} if mode == 'calculate' else {}}

    def preview(self, request):
        """Inspect completeness/scope and evidence without executing a calculator.

        This is a UI preflight, not a second answerability verdict. All domain
        validation and calculation remain the unchanged gate's responsibility.
        """
        self._check_code()
        issues = []
        def issue(kind, field, detail):
            issues.append({'kind': kind, 'field': field, 'detail': detail})
        capability = request.get('capability') if isinstance(request, dict) else None
        contract = self.catalog.get(capability) if isinstance(capability, str) else None
        mode = request.get('mode') if isinstance(request, dict) else None
        citation, query, candidates, excerpt = None, None, [], None
        if not isinstance(request, dict) or set(request) != answerability.REQUEST_FIELDS:
            issue('UNSUPPORTED', 'request', 'Use exactly capability, mode, requested, arguments and conditions.')
        if contract is None:
            issue('UNSUPPORTED', 'capability', 'Select one of the eight owned capabilities; no other domain is supported.')
        else:
            requested = request.get('requested')
            selections_ok = (isinstance(requested, list) and len(requested) <= 8
                             and all(isinstance(x, str) for x in requested))
            if not selections_ok:
                issue('UNSUPPORTED', 'requested', 'Provide a list of at most eight explicit output/section names.')
                requested = []
            elif not requested:
                issue('CLARIFY', 'requested', 'Select at least one output or reference section.')
            elif len(set(requested)) != len(requested):
                issue('UNSUPPORTED', 'requested', 'Duplicate selections are not supported.')
            if mode not in ('reference', 'calculate'):
                issue('UNSUPPORTED', 'mode', 'Choose reference or calculate.')
            else:
                allowed = SECTIONS if mode == 'reference' else contract['output_contract']
                for field in requested:
                    if field not in allowed:
                        issue('UNSUPPORTED', 'requested.' + field, 'This capability does not supply that result.')
            # Derived only from explicit fields. No natural-language query or
            # intent inference is accepted by this interface.
            query = capability + ' ' + ' '.join(requested)
            if len(query) > 2048:
                issue('UNSUPPORTED', 'requested', 'Selection text is too long.')
                query = capability
            search = self.gate.retriever.query(query, method='lexical', top_k=3)
            candidates = [hit['id'] for hit in search['hits']]
            match = next((hit for hit in search['hits'] if hit['id'] == 'calculator-' + capability), None)
            if match is None:
                issue('UNSUPPORTED', 'evidence', 'Matching authenticated function evidence was not retrieved.')
            else:
                citation, excerpt = match['citation'], match['evidence']
            args, conditions = request.get('arguments'), request.get('conditions')
            if not isinstance(args, dict) or not isinstance(conditions, dict):
                issue('UNSUPPORTED', 'arguments/conditions', 'Both must be JSON objects.')
            elif mode == 'reference':
                if args or conditions:
                    issue('UNSUPPORTED', 'reference', 'Applied quantities/conditions require calculate mode; reference only extracts source facts.')
            elif mode == 'calculate':
                required = contract['conditions']['source_assumptions'] + contract['conditions']['gate_policy_conditions']
                for field in conditions:
                    if field not in required:
                        issue('UNSUPPORTED', 'conditions.' + field, 'Additional requirements cannot be silently ignored.')
                    elif conditions[field] is False:
                        issue('UNSUPPORTED', 'conditions.' + field, 'Contradicts the supported model.')
                for field in required:
                    if conditions.get(field) is not True and conditions.get(field) is not False:
                        issue('CLARIFY', 'conditions.' + field, 'Explicit true/false is required; unknown is not assumed true.')
                for field in args:
                    if field not in contract['input_contract']:
                        issue('UNSUPPORTED', 'arguments.' + field, 'Unknown input cannot be ignored.')
                for field, spec in contract['input_contract'].items():
                    value = args.get(field)
                    if value is None:
                        issue('CLARIFY', 'arguments.' + field, 'Supply the declared input.')
                        continue
                    if 'canonical_unit' in spec:
                        if not isinstance(value, dict) or set(value) - {'value', 'unit'}:
                            issue('UNSUPPORTED', 'arguments.' + field, 'Use only value and unit.')
                            continue
                        unit = value.get('unit')
                        accepted = ['delta_K', 'delta_degC'] if spec['checks'].get('difference') else [spec['canonical_unit']]
                        if not unit:
                            issue('CLARIFY', 'arguments.' + field + '.unit', 'Supply an explicit unit: ' + ', '.join(accepted))
                        elif unit not in accepted:
                            issue('UNSUPPORTED', 'arguments.' + field + '.unit', 'Frozen gate accepts: ' + ', '.join(accepted))
                        value = value.get('value')
                    if spec['declaration'] == 'str':
                        if not value:
                            issue('CLARIFY', 'arguments.' + field, 'Supply the explicit unit expression.')
                        elif not isinstance(value, str):
                            issue('UNSUPPORTED', 'arguments.' + field, 'A unit expression must be text.')
                    elif value is None:
                        issue('CLARIFY', 'arguments.' + field, 'Supply a finite numerical value.')
                    else:
                        try:
                            finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                        except OverflowError:
                            finite = False
                        if not finite:
                            issue('UNSUPPORTED', 'arguments.' + field, 'A finite number is required.')
                range_problem = answerability.numerical_policy.range_issue(capability, args)
                if range_problem:
                    issue('UNSUPPORTED', 'numerical_range.' + range_problem['input'], range_problem['reason'])
        state = 'UNSUPPORTED' if any(i['kind'] == 'UNSUPPORTED' for i in issues) else 'CLARIFY' if issues else 'REVIEW_REQUIRED'
        return {'schema_version': 1, 'review_target_sha256': self.target_sha,
                'review_commit': self.target['review_commit'], 'request': request,
                'scope_sha256': sha_value(request), 'preflight_status': state, 'issues': issues,
                'retrieval_query': query, 'candidate_ids': candidates,
                'evidence_citation': citation, 'evidence_excerpt': excerpt,
                'contract': {k: v for k, v in contract.items() if k != 'implementation'} if contract else None,
                'calculation_executed': False, 'generator_allowed': False,
                'numerical_policy': self.gate.numerical_policy(),
                'independent_review': self.target['review_status'],
                'notice': 'Preflight checks scope/completeness only. Numerical/domain validation occurs after confirmation in the frozen gate. No free-form interpretation.'}

    def execute(self, preview_path, confirmation):
        if not confirmation or harness.digest(preview_path) != confirmation:
            raise harness.IntegrityError('Confirmation must match the exact saved preview SHA-256. Preview and review it again.')
        saved = harness.read_json(preview_path)
        if not isinstance(saved, dict) or 'request' not in saved:
            raise harness.IntegrityError('Not a saved request preview.')
        fresh = self.preview(saved['request'])
        if canonical(fresh) != canonical(saved):
            raise harness.IntegrityError('Preview or its source/contract changed; create and review a fresh preview.')
        if fresh['preflight_status'] != 'REVIEW_REQUIRED':
            return {'status': fresh['preflight_status'], 'issues': fresh['issues'],
                    'confirmed_request': fresh['request'],
                    'supported_answer': None, 'calculation_executed': False, 'generator_allowed': False}
        result = self.gate.search_and_assess(fresh['retrieval_query'], fresh['request'], method='lexical', top_k=3)
        return {'status': result['assessment']['status'], 'assessment': result['assessment'],
                'confirmed_request': fresh['request'],
                'preview_sha256': confirmation, 'scope_sha256': fresh['scope_sha256'],
                'confirmation_method': 'EXACT_PREVIEW_TOKEN_ACKNOWLEDGED_NOT_PROOF_OF_HUMAN_REVIEW',
                'operation_selection': 'EXPLICIT_STRUCTURED_FIELDS', 'generator_allowed': False}


def print_preview(preview):
    request = preview['request'] if isinstance(preview['request'], dict) else {}
    cap = request.get('capability')
    print('\nREQUEST PREVIEW - no calculation has run')
    label = LABELS.get(cap, cap) if isinstance(cap, str) else str(cap)
    print('Operation:', label, f'[{cap}]')
    print('Mode:', request.get('mode'), '| Requested:', show_value(request.get('requested')))
    for title, key in [('Quantities / unit expressions', 'arguments'), ('Explicit assumptions', 'conditions')]:
        print(title + ':')
        fields = request.get(key)
        if isinstance(fields, dict):
            for name, value in fields.items():
                print('  ' + name + ': ' + show_value(value))
            if not fields:
                print('  (none)')
        else:
            print('  INVALID: expected an object')
    citation = preview['evidence_citation']
    if citation:
        print(f"Evidence: {citation['source_path']}:{citation['start_line']}-{citation['end_line']}")
        print('Source SHA-256:', citation['source_sha256'])
        print('Slice SHA-256:', citation['slice_sha256'])
    else:
        print('Evidence: no matching approved capability')
    contract = preview['contract']
    if contract:
        print('Source limits / domain restrictions:')
        for text in dict.fromkeys(contract['limitations']['source_limitations'] + contract['limitations']['explicit_domain_errors']):
            print('  - ' + text)
        print('Required input units/checks:')
        for field, spec in contract['input_contract'].items():
            unit = 'delta_K or delta_degC' if spec.get('checks', {}).get('difference') else spec.get('canonical_unit', 'unit expression' if spec['declaration'] == 'str' else 'number')
            checks = spec.get('checks', {})
            restrictions = ('; must be positive' if checks.get('positive') else '; must be nonnegative' if checks.get('nonnegative') else '')
            print(f'  {field}: {unit}' + restrictions)
    print('Preflight:', preview['preflight_status'])
    for issue in preview['issues']:
        print(f"  {issue['kind']} {issue['field']}: {issue['detail']}")
    print(preview['notice'])
    policy = preview['numerical_policy']
    print(f"Numerical policy: nonzero inputs must have magnitude {policy['nonzero_input_absolute_min']} through {policy['nonzero_input_absolute_max']}; source sign/domain rules still apply.")
    if cap == 'second_order_step':
        print('Step policy: normalized time 0 or 1e-6..1e6; decay/overshoot exponent <=700.')
    if cap == 'convert_units':
        print(policy['conversion'])
    print('Assumptions are supplied assertions. Independent review:', preview['independent_review'])


def print_result(result):
    request = result.get('confirmed_request', {})
    print('\nCONFIRMED STRUCTURED REQUEST')
    print('Operation:', request.get('capability'), '| Mode:', request.get('mode'))
    print('Requested:', show_value(request.get('requested')))
    for group in ('arguments', 'conditions'):
        fields = request.get(group)
        if isinstance(fields, dict):
            for field, value in fields.items():
                print('  ' + group + '.' + field + ': ' + show_value(value))
    print('\nRESULT:', result['status'])
    assessment = result.get('assessment')
    if assessment:
        print(assessment['reason'])
        for name, value in (assessment.get('supported_answer') or {}).items():
            print('  ' + name + ': ' + ('no finite numerical value' if value is None else show_value(value)))
            status = assessment.get('output_status', {}).get(name)
            if status:
                print('    ' + status['status'] + (': ' + status['explanation'] if 'explanation' in status else ''))
        for key in ('missing', 'missing_or_unconfirmed', 'unsupported', 'accepted_units'):
            if key in assessment:
                print('  ' + key + ': ' + show_value(assessment[key]))
        if assessment.get('input'):
            print('  Input:', assessment['input'])
        c = assessment.get('citation')
        if c:
            print(f"Evidence: {c['source_path']}:{c['start_line']}-{c['end_line']}")
        for text in assessment.get('source_limits', {}).get('source_limitations', []):
            print('  Limit:', text)
        if request.get('capability') == 'convert_units':
            print('  Limit:', assessment.get('numerical_policy', {}).get('conversion', 'Algebraic conversion only.'))
    for issue in result.get('issues', []):
        print(f"  {issue['kind']} {issue['field']}: {issue['detail']}")
    print('Applies to the displayed structured request only. No language-model answer or generator permission.')


def choice(prompt, items):
    for i, item in enumerate(items, 1):
        print(f'  {i}. {item}')
    while True:
        answer = input(prompt + ' (number, or q to cancel): ').strip()
        if answer.lower() == 'q':
            raise KeyboardInterrupt
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return int(answer)-1
        print('Enter one of the displayed numbers.')


def wizard(session, output):
    print('FORGE owned calculator request builder\nChoose fields explicitly. Blank quantities/units and unknown assumptions stay unresolved.')
    capabilities = list(LABELS)
    cap = capabilities[choice('Operation', [LABELS[c] + ' [' + c + ']' for c in capabilities])]
    mode = ['calculate', 'reference'][choice('Use', ['Calculate values under explicit conditions', 'Read exact source facts/limitations'])]
    request = session.template(cap, mode)
    outputs = list(session.catalog[cap]['output_contract']) if mode == 'calculate' else SECTIONS
    request['requested'] = [outputs[choice('First output / section', outputs)]]
    while input('Add another output/section? [yes/no]: ').strip().lower() == 'yes':
        remaining = [o for o in outputs if o not in request['requested']]
        if not remaining:
            break
        request['requested'].append(remaining[choice('Additional output / section', remaining)])
    if mode == 'calculate':
        for field, spec in session.catalog[cap]['input_contract'].items():
            if spec['declaration'] == 'str':
                request['arguments'][field] = input(field + ' (explicit unit expression; blank=unknown): ').strip()
                continue
            while True:
                raw = input(field + ' value (finite number; blank=unknown): ').strip()
                try:
                    # Interactive numeric entry accepts familiar forms such as
                    # .01; persisted requests still use strict JSON numbers.
                    value = None if not raw else float(raw)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                        raise ValueError
                    break
                except (ValueError, OverflowError):
                    print('Enter a finite number without a unit, or leave blank.')
            if 'canonical_unit' in spec:
                unit = 'delta_K or delta_degC' if spec['checks'].get('difference') else spec['canonical_unit']
                entered = input(field + ' unit (gate accepts ' + unit + '; blank=unknown): ').strip()
                request['arguments'][field] = {'value': value, 'unit': entered}
            else:
                request['arguments'][field] = value
        for field in request['conditions']:
            while True:
                answer = input('Does ' + field + ' apply? [yes/no/unknown]: ').strip().lower()
                if answer in ('yes', 'no', 'unknown', ''):
                    request['conditions'][field] = {'yes': True, 'no': False}.get(answer)
                    break
                print('Enter yes, no or unknown. These are your assertions, not observed facts.')
    request_path, _ = save_new(output.with_suffix('.request.json'), request)
    preview = session.preview(request)
    path, pin = save_new(output, preview)
    print_preview(preview)
    print('Editable request:', request_path)
    print('Saved preview:', path)
    print('Confirmation SHA-256:', pin)
    if preview['preflight_status'] != 'REVIEW_REQUIRED':
        print('Resolve the listed fields in the request and create a fresh preview. Nothing was calculated.')
        return 2 if preview['preflight_status'] == 'CLARIFY' else 3
    if input('Review all fields above. Type RUN to execute exactly this request, or Enter to stop: ').strip() != 'RUN':
        print('Saved for review; nothing was calculated.')
        return 0
    result = session.execute(path, pin)
    result_path, _ = save_new(output.with_suffix('.result.json'), result)
    print_result(result)
    print('Saved result:', result_path)
    return status_code(result['status'])


def status_code(status):
    return 0 if status.startswith('SUPPORTED_') or status == 'REVIEW_REQUIRED' else 2 if status.startswith('CLARIFY') else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--target-sha', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='List the eight explicit operations')
    describe = sub.add_parser('describe', help='Show inputs, outputs, assumptions and source restrictions')
    describe.add_argument('operation', choices=LABELS)
    template = sub.add_parser('template', help='Create an unresolved editable JSON request; never fills assumptions')
    template.add_argument('operation', choices=LABELS)
    template.add_argument('--mode', choices=['calculate', 'reference'], default='calculate')
    template.add_argument('--out', type=Path, required=True)
    preview = sub.add_parser('preview', help='Retrieve evidence and save a reviewable scope; does not calculate')
    preview.add_argument('--request', type=Path, required=True)
    preview.add_argument('--out', type=Path, required=True)
    run = sub.add_parser('run', help='Recheck and execute the exact acknowledged preview through the frozen gate')
    run.add_argument('--preview', type=Path, required=True)
    run.add_argument('--confirm', required=True, help='SHA-256 printed when the preview was saved')
    run.add_argument('--out', type=Path)
    interactive = sub.add_parser('wizard', help='Guided operation/quantity/unit/assumption selection, preview, then RUN')
    interactive.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        session = RequestSession(args.target, args.target_sha)
        if args.command == 'list':
            for cap, label in LABELS.items():
                print(cap + ' - ' + label)
            print('Explicit structured operations only. Use describe OPERATION or wizard.')
        elif args.command == 'describe':
            p = session.preview(session.template(args.operation, 'calculate'))
            print_preview(p)
            print('Available outputs:', ', '.join(session.catalog[args.operation]['output_contract']))
        elif args.command == 'template':
            path, _ = save_new(args.out, session.template(args.operation, args.mode))
            print('Draft saved:', path)
            print('Unknown values, blank units and null assumptions must be reviewed and filled explicitly.')
        elif args.command == 'preview':
            p = session.preview(harness.read_json(args.request))
            path, pin = save_new(args.out, p)
            print_preview(p)
            print('Saved preview:', path)
            print('Confirmation SHA-256:', pin)
            if p['preflight_status'] == 'REVIEW_REQUIRED':
                print('After reviewing: run --preview "' + str(path) + '" --confirm ' + pin)
            else:
                print('Next: resolve the listed fields in ' + str(args.request.resolve()) + ' and create a fresh preview. No calculation was run.')
            return status_code(p['preflight_status'])
        elif args.command == 'run':
            result = session.execute(args.preview, args.confirm)
            print_result(result)
            if args.out:
                path, _ = save_new(args.out, result)
                print('Saved result:', path)
            return status_code(result['status'])
        else:
            output = args.out or Path('request-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.preview.json')
            return wizard(session, output)
        return 0
    except (KeyboardInterrupt, EOFError):
        print('\nCanceled. No unconfirmed calculation was run.', file=sys.stderr)
        return 130
    except (harness.IntegrityError, OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print('STOPPED: ' + str(exc), file=sys.stderr)
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
