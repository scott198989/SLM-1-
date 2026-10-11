"""Conservative, CPU-only boundary between search and structured supported results.

No NLP intent inference, similarity threshold, LLM, model load, or network. The
explicit request is authoritative; the search text is NOT asserted equivalent
to it. Callers must resolve that mapping before presenting a natural-language
answer. Even successful results do not authorize a generator or real-world use.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import types

from .harness import IntegrityError, LocalRetriever, SOURCE_SHA, read_json

CAPABILITIES = frozenset(('convert_units', 'check_dimensional_equation',
    'axial_stress', 'dc_motor', 'thermal_expansion', 'second_order_step',
    'series_rlc', 'quadratic_roots'))
REFERENCE_SECTIONS = frozenset(('input_contract', 'output_contract', 'conditions',
                              'limitations', 'implementation'))
REQUEST_FIELDS = frozenset(('capability', 'mode', 'requested', 'arguments', 'conditions'))

# Deliberately narrower than the underlying dimensional parser. Equal dimensions
# cannot prove semantic equivalence (angles, cycles, temperature intervals, etc.).
# Unknown/composite pairs are refused here, not guessed from dimensions.
CONVERSION_GROUPS = (
    frozenset(('kg', 'g')), frozenset(('m', 'mm', 'cm', 'km', 'in', 'ft')),
    frozenset(('s', 'ms', 'min', 'h')), frozenset(('A', 'mA')),
    frozenset(('K', 'degC')), frozenset(('delta_K', 'delta_degC')),
    frozenset(('rad', 'deg')), frozenset(('rad/s', 'rpm', 'deg/s')),
    frozenset(('Hz',)), frozenset(('1', '%')), frozenset(('N', 'kN')),
    frozenset(('Pa', 'kPa', 'MPa', 'GPa')), frozenset(('J', 'kJ')),
    frozenset(('W', 'kW')), frozenset(('V', 'mV')),
    frozenset(('Ohm', 'ohm', 'kohm')), frozenset(('H', 'mH', 'uH')),
    frozenset(('F', 'uF', 'nF')), frozenset(('mol',)),
    frozenset(('cd',)), frozenset(('C',)))

LIMITS = [
    'Support applies only to the explicit structured request; free text was not interpreted or proved equivalent.',
    'Model conditions are supplied assertions, not verified observations about a physical system.',
    'Evidence is this pinned calculator implementation, not independent scientific or engineering certification.',
    'Finite double-precision results can still contain numerical approximation or cancellation error.',
    'No calibrated probability of correctness, general-domain coverage, or generator readiness is established.',
]


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        raise IntegrityError('Expected literal source contract') from None


def _contracts(source, chunks):
    """Read declarations from the exact reviewed source, never probe labels."""
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    contracts = {}
    for name in sorted(CAPABILITIES):
        node = functions[name]
        chunk = chunks['calculator-' + name]
        if (node.lineno, node.end_lineno) != (chunk['start_line'], chunk['end_line']):
            raise IntegrityError('Capability does not match authenticated function range')
        arguments = node.args.args + node.args.kwonlyargs
        inputs = {a.arg: {'declaration': ast.unparse(a.annotation)} for a in arguments}
        outputs, assumptions, limitations, guards = {}, [], [], []
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_quantity':
                field = n.args[0].id
                inputs[field].update(canonical_unit=_literal(n.args[1]),
                                     checks={k.arg: _literal(k.value) for k in n.keywords})
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and n.exc.args:
                if isinstance(n.exc.args[0], ast.Constant):
                    guards.append(_literal(n.exc.args[0]))
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict):
                for key, value in zip(n.value.keys, n.value.values):
                    field = _literal(key)
                    if field == 'assumptions':
                        assumptions = _literal(value)
                    elif field in ('limitation', 'limitations'):
                        v = _literal(value)
                        limitations.extend(v if isinstance(v, list) else [v])
                    else:
                        outputs[field] = {'source_expression': ast.get_source_segment(source, value)}
        policy_conditions = []
        if name == 'convert_units':
            outputs = {'value': {'source_expression': 'Quantity.from_value(value, from_unit).to(to_unit)'}}
            policy_conditions = ['same_physical_quantity']
            limitations.extend(guards)
        elif name == 'check_dimensional_equation':
            policy_conditions = ['dimensions_only']
        contracts[name] = {
            'input_contract': inputs, 'output_contract': outputs,
            'conditions': {'source_assumptions': assumptions, 'gate_policy_conditions': policy_conditions},
            'limitations': {'source_limitations': limitations, 'explicit_domain_errors': guards},
            'implementation': chunk['text'],
        }
    return contracts


class AnswerabilityGate:
    def __init__(self, retriever: LocalRetriever):
        self.retriever = retriever
        retriever._verify_sources()
        source_bytes = retriever.source_path.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA:
            raise IntegrityError('Gate requires the exact reviewed owned calculator')
        self.chunks = {c['id']: c for c in retriever.chunks}
        if set(self.chunks) != {'calculator-' + x for x in CAPABILITIES}:
            raise IntegrityError('Capability allowlist mismatch')
        self._catalog = _contracts(source_bytes.decode('utf-8'), self.chunks)
        # Load ONLY this hash-pinned standalone module. Importing the repository
        # package could transitively open unrelated/sealed material.
        module_name = '_forge_verified_owned_calculator'
        module = types.ModuleType(module_name)
        module.__file__ = str(retriever.source_path)
        prior = sys.modules.get(module_name)
        sys.modules[module_name] = module  # dataclass needs this during loading
        try:
            exec(compile(source_bytes, str(retriever.source_path), 'exec'), module.__dict__)
        finally:
            if prior is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = prior
        self._calculator = module
        if set(module.tool_catalog()) != CAPABILITIES:
            raise IntegrityError('Calculator dispatch contract mismatch')
        retriever._verify_sources()

    def catalog(self):
        self.retriever._verify_sources()
        return copy.deepcopy(self._catalog)

    def search_and_assess(self, query, request=None, **retrieval_options):
        search = self.retriever.query(query, **retrieval_options)
        return {'search_result': search, 'assessment': self.assess(search, request)}

    def _check_evidence(self, search):
        self.retriever._verify_sources()
        if search.get('manifest_sha256') != self.retriever.manifest_sha:
            raise IntegrityError('Search manifest does not bind approved evidence')
        verified = {}
        if not isinstance(search.get('hits'), list):
            raise IntegrityError('Invalid search evidence')
        for hit in search['hits']:
            if not isinstance(hit, dict) or hit.get('id') not in self.chunks:
                raise IntegrityError('Unknown evidence chunk')
            c = self.chunks[hit['id']]
            expected = {k: c[k] for k in ('source_sha256', 'slice_sha256', 'start_line', 'end_line')}
            expected['source_path'] = str(self.retriever.source_path)
            if hit.get('citation') != expected or hit.get('evidence') != c['text'] or c['id'] in verified:
                raise IntegrityError('Altered or duplicate evidence citation')
            verified[c['id']] = copy.deepcopy(hit['citation'])
        return verified

    def assess(self, search, request=None):
        evidence = self._check_evidence(search)

        def finish(status, reason, **extra):
            self.retriever._verify_sources()
            return {'status': status, 'reason': reason, 'supported_answer': None,
                    'generator_allowed': False, 'natural_language_answer_generated': False,
                    'request_scope': 'EXPLICIT_STRUCTURED_REQUEST_ONLY',
                    'query_intent_alignment': 'NOT_ESTABLISHED',
                    'evidence_coverage': {'requested': 0, 'covered': 0},
                    'limitations': list(LIMITS), **extra}

        if request is None:
            return finish('CLARIFY_REQUEST_SCOPE', 'Select a capability and explicit fact or output; ranking alone is not an answer.')
        if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
            return finish('ABSTAIN_INVALID_REQUEST', 'Request requires exactly capability, mode, requested, arguments, conditions.')
        cap, mode, wanted, arguments, conditions = (request[k] for k in ('capability', 'mode', 'requested', 'arguments', 'conditions'))
        if not isinstance(cap, str) or cap not in CAPABILITIES:
            return finish('ABSTAIN_UNSUPPORTED_CAPABILITY', 'No approved capability supports this domain or function.')
        if (mode not in ('reference', 'calculate') or not isinstance(wanted, list)
                or not 1 <= len(wanted) <= 8 or any(not isinstance(x, str) for x in wanted)
                or len(set(wanted)) != len(wanted) or not isinstance(arguments, dict)
                or not isinstance(conditions, dict)):
            return finish('ABSTAIN_INVALID_REQUEST', 'Invalid mode, output selectors, arguments, or conditions.')
        contract = self._catalog[cap]
        allowed = REFERENCE_SECTIONS if mode == 'reference' else set(contract['output_contract'])
        if set(wanted) - allowed:
            return finish('ABSTAIN_UNSUPPORTED_REQUEST', 'One or more requested facts/outputs are outside this capability.', unsupported=sorted(set(wanted)-allowed))
        chunk_id = 'calculator-' + cap
        if chunk_id not in evidence:
            return finish('ABSTAIN_NO_EVIDENCE', 'Candidates do not contain authenticated evidence for the requested capability.', required_chunk=chunk_id)
        common = {'capability': cap, 'citation': evidence[chunk_id],
                  'source_limits': copy.deepcopy(contract['limitations']),
                  'conditions_contract': copy.deepcopy(contract['conditions'])}
        if mode == 'reference':
            if arguments or conditions:
                return finish('ABSTAIN_UNSUPPORTED_REQUEST', 'Reference extraction does not verify an applied scenario; use calculate with all conditions.', **common)
            return finish('SUPPORTED_REFERENCE_EXTRACT', 'Exact source declarations/excerpts cover the selected reference sections.',
                          supported_answer={s: copy.deepcopy(contract[s]) for s in wanted},
                          evidence_coverage={'requested': len(wanted), 'covered': len(wanted)}, **common)
        required = set(contract['conditions']['source_assumptions'] + contract['conditions']['gate_policy_conditions'])
        if set(conditions) - required:
            return finish('ABSTAIN_UNSUPPORTED_CONDITIONS', 'Unknown additional requirements cannot be silently ignored.', unsupported=sorted(set(conditions)-required), **common)
        if any(value is False for value in conditions.values()):
            return finish('ABSTAIN_CONFLICTING_CONDITIONS', 'A supplied condition contradicts the supported model.', **common)
        if set(conditions) != required or any(value is not True for value in conditions.values()):
            return finish('CLARIFY_MISSING_CONDITIONS', 'Each required condition must be explicitly true; values are not inferred.', missing_or_unconfirmed=sorted(x for x in required if conditions.get(x) is not True), **common)
        fields = set(contract['input_contract'])
        if set(arguments) - fields:
            return finish('ABSTAIN_UNSUPPORTED_REQUEST', 'Unknown input fields cannot be ignored.', unsupported=sorted(set(arguments)-fields), **common)
        if fields - set(arguments):
            return finish('CLARIFY_MISSING_ARGUMENTS', 'All declared inputs are required.', missing=sorted(fields-set(arguments)), **common)
        for name, spec in contract['input_contract'].items():
            if 'canonical_unit' not in spec:
                continue
            value = arguments[name]
            if not isinstance(value, dict) or 'unit' not in value or not value['unit']:
                return finish('CLARIFY_MISSING_UNITS', 'A physical input lacks explicit units.', input=name, **common)
            if set(value) != {'value', 'unit'}:
                return finish('ABSTAIN_INVALID_ARGUMENTS', 'Quantity inputs require exactly value and unit.', input=name, **common)
            accepted = {spec['canonical_unit']}
            if spec['checks'].get('difference'):
                accepted = {'delta_K', 'delta_degC'}
            if not isinstance(value['unit'], str) or value['unit'] not in accepted:
                return finish('ABSTAIN_UNSUPPORTED_UNITS', 'Use the explicit canonical unit; temperature changes require delta_K or delta_degC.', input=name, accepted_units=sorted(accepted), **common)
        if cap == 'convert_units':
            units = (arguments['from_unit'], arguments['to_unit'])
            if any(not isinstance(x, str) or not x for x in units):
                return finish('CLARIFY_MISSING_UNITS', 'Both unit strings must be explicit.', **common)
            if not any(set(units) <= group for group in CONVERSION_GROUPS):
                return finish('ABSTAIN_UNSUPPORTED_UNITS', 'This pair has no approved same-quantity unit policy; equal dimensions do not suffice.', **common)
        if cap == 'check_dimensional_equation' and any(not isinstance(v, str) or not v for v in arguments.values()):
            return finish('CLARIFY_MISSING_UNITS', 'Both dimensional expressions must be explicit strings.', **common)
        try:
            result = self._calculator.execute_tool(cap, arguments)['result']
        except self._calculator.EngineeringError as exc:
            return finish('ABSTAIN_INPUT_DOMAIN', str(exc), **common)
        if cap == 'convert_units':
            result = {'value': {'value': result, 'unit': arguments['to_unit']}}
        return finish('SUPPORTED_CALCULATION', 'Authenticated deterministic tool result under the explicit supplied conditions.',
                      supported_answer={s: result[s] for s in wanted},
                      evidence_coverage={'requested': len(wanted), 'covered': len(wanted)},
                      numerical_method='PINNED_OWNED_CALCULATOR_FLOAT64', **common)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--expected-manifest-sha', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--request', type=Path, help='Explicit reviewed structured request; omitted means clarification')
    args = parser.parse_args()
    gate = AnswerabilityGate(LocalRetriever(args.manifest, args.expected_manifest_sha))
    result = gate.search_and_assess(args.query, read_json(args.request) if args.request else None)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
