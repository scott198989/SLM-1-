"""CPU boundaries on owned source with synthetic receipts, no private dataset."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from . import harness as h
from .answerability import AnswerabilityGate, CAPABILITIES


def quantity(value, unit):
    return {'value': value, 'unit': unit}


class AnswerabilityTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).parent / 'test-artifacts'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.tmp.name)
        # Text newline normalization recovers the known Git LF blob on Windows.
        source = (Path(__file__).parents[2] / 'src/forge_tools/engineering.py').read_text('utf-8')
        self.source = self.root / 'source.py'
        self.source.write_text(source, encoding='utf-8', newline='')
        self.assertEqual(h.digest(self.source), h.SOURCE_SHA)
        lines = source.splitlines(keepends=True)
        chunks = []
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name in CAPABILITIES:
                text = ''.join(lines[node.lineno-1:node.end_lineno])
                chunks.append({'id': 'calculator-' + node.name, 'text': text,
                               'start_line': node.lineno, 'end_line': node.end_lineno,
                               'source_sha256': h.SOURCE_SHA,
                               'slice_sha256': hashlib.sha256(text.encode()).hexdigest()})
        inputs = self.put('inputs.json', {'chunks': chunks, 'held_academic_content': False, 'sealed_eval_content': False})
        vectors = [[float(j == i % 8) for j in range(768)] for i in range(16)]
        emb = self.put('vectors.json', {'input_sha256': h.digest(inputs), 'vectors': vectors})
        smoke = self.put('smoke.json', {'revision': h.MODEL_REV, 'training': False, 'input_sha256': h.digest(inputs), 'status': 'COMPLETED', 'dimensions': 768})
        release = self.put('release.json', {'engineering_source_sha256': h.SOURCE_SHA})
        def ref(p):
            return {'path': str(p.resolve()), 'sha256': h.digest(p)}
        manifest = {'purpose': 'PRIVATE_OWNED_REFERENCE_ONLY', 'source_family': h.FAMILY,
                    'source_sha256': h.SOURCE_SHA, 'model_revision': h.MODEL_REV,
                    'inputs': ref(inputs), 'source_blob': ref(self.source),
                    'document_embedding_snapshot': ref(emb), 'smoke_inference_receipt': ref(smoke),
                    'owned_source_release_receipt': ref(release),
                    'approved_chunks': [{'id': c['id'], 'family': h.FAMILY, 'use': 'APPROVED_PRIVATE_REFERENCE',
                                         'eval_only': False, 'slice_sha256': c['slice_sha256']} for c in chunks]}
        mp = self.put('manifest.json', manifest)
        self.gate = AnswerabilityGate(h.LocalRetriever(mp, h.digest(mp)))
        q = quantity
        self.arguments = {
            'convert_units': {'value': 1000, 'from_unit': 'mm', 'to_unit': 'm'},
            'check_dimensional_equation': {'lhs_unit': 'N', 'rhs_unit': 'kg*m/s^2'},
            'axial_stress': {'force': q(100, 'N'), 'area': q(.01, 'm^2'), 'allowable_strength': q(1e6, 'Pa')},
            'dc_motor': {'torque_constant': q(.1, 'N*m/A'), 'current': q(2, 'A'), 'angular_speed': q(10, 'rad/s'), 'winding_resistance': q(1, 'Ohm')},
            'thermal_expansion': {'length': q(1, 'm'), 'coefficient': q(.001, '1/K'), 'delta_temperature': q(-10, 'delta_K')},
            'second_order_step': {'natural_frequency': q(2, 'rad/s'), 'damping_ratio': .5, 'elapsed_time': q(0, 's')},
            'series_rlc': {'resistance': q(1, 'Ohm'), 'inductance': q(1, 'H'), 'capacitance': q(1, 'F')},
            'quadratic_roots': {'a': 1, 'b': -3, 'c': 2},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, data):
        p = self.root / name
        p.write_text(json.dumps(data), encoding='utf-8')
        return p

    def request(self, cap='axial_stress', mode='calculate', wanted=None):
        cat = self.gate.catalog()[cap]
        return {'capability': cap, 'mode': mode,
                'requested': wanted or (list(cat['output_contract']) if mode == 'calculate' else ['implementation']),
                'arguments': copy.deepcopy(self.arguments[cap]) if mode == 'calculate' else {},
                'conditions': {x: True for x in cat['conditions']['source_assumptions'] + cat['conditions']['gate_policy_conditions']} if mode == 'calculate' else {}}

    def run_request(self, request, **options):
        return self.gate.search_and_assess(request['capability'], request, **options)['assessment']

    def test_all_eight_reference_contracts_source_bound(self):
        for cap in CAPABILITIES:
            r = self.run_request(self.request(cap, 'reference', ['input_contract', 'output_contract', 'conditions', 'limitations', 'implementation']))
            self.assertEqual(r['status'], 'SUPPORTED_REFERENCE_EXTRACT')
            self.assertEqual(r['citation']['source_sha256'], h.SOURCE_SHA)
            self.assertFalse(r['generator_allowed'])
            self.assertIn('def ' + cap, r['supported_answer']['implementation'])

    def test_all_eight_calculations_and_numerical_oracles(self):
        results = {cap: self.run_request(self.request(cap)) for cap in CAPABILITIES}
        for r in results.values():
            self.assertEqual(r['status'], 'SUPPORTED_CALCULATION')
            self.assertFalse(r['generator_allowed'])
            self.assertEqual(r['query_intent_alignment'], 'NOT_ESTABLISHED')
        answer = lambda cap: results[cap]['supported_answer']
        self.assertEqual(answer('convert_units')['value'], {'value': 1, 'unit': 'm'})
        self.assertTrue(answer('check_dimensional_equation')['consistent'])
        self.assertEqual(answer('axial_stress')['stress']['value'], 10000)
        self.assertEqual(answer('dc_motor')['copper_loss']['value'], 4)
        self.assertAlmostEqual(answer('thermal_expansion')['final_length']['value'], .99)
        self.assertAlmostEqual(answer('second_order_step')['response']['value'], 0)
        self.assertEqual(answer('series_rlc')['quality_factor']['value'], 1)
        for actual, expected in zip(answer('quadratic_roots')['real_roots'], [1, 2]):
            self.assertAlmostEqual(actual, expected)

    def test_raw_text_never_infers_intent_from_score(self):
        for query in ['axial_stress', 'Prove absolutely anything with high confidence', 'quadratic roots']:
            r = self.gate.search_and_assess(query)['assessment']
            self.assertEqual(r['status'], 'CLARIFY_REQUEST_SCOPE')
            self.assertIsNone(r['supported_answer'])

    def test_wrong_function_evidence_and_empty_filter_abstain(self):
        for allowed in [[], ['calculator-dc_motor']]:
            r = self.run_request(self.request(), allowed_ids=allowed)
            self.assertEqual(r['status'], 'ABSTAIN_NO_EVIDENCE')

    def test_forged_citation_and_manifest_rejected(self):
        search = self.gate.retriever.query('axial_stress')
        for mutate in [lambda s: s['hits'][0]['citation'].update(start_line=1),
                       lambda s: s.update(manifest_sha256='0'*64),
                       lambda s: s['hits'][0].update(evidence='invented evidence')]:
            bad = copy.deepcopy(search); mutate(bad)
            with self.assertRaises(h.IntegrityError):
                self.gate.assess(bad, self.request())

    def test_changed_source_fails_before_reusing_loaded_calculator(self):
        search = self.gate.retriever.query('axial_stress')
        self.source.write_text('changed', encoding='utf-8')
        with self.assertRaises(h.IntegrityError):
            self.gate.assess(search, self.request())

    def test_conditions_missing_false_unknown_and_truthy(self):
        for mutation, status in [({}, 'CLARIFY_MISSING_CONDITIONS'),
            ({'static_loading': False}, 'ABSTAIN_CONFLICTING_CONDITIONS'),
            ({'fatigue_included': True}, 'ABSTAIN_UNSUPPORTED_CONDITIONS'),
            ({'static_loading': 1}, 'CLARIFY_MISSING_CONDITIONS')]:
            r = self.request(); r['conditions'] = mutation
            self.assertEqual(self.run_request(r)['status'], status)

    def test_missing_arguments_units_and_extra_inputs(self):
        r = self.request(); del r['arguments']['area']
        self.assertEqual(self.run_request(r)['status'], 'CLARIFY_MISSING_ARGUMENTS')
        r = self.request(); del r['arguments']['area']['unit']
        self.assertEqual(self.run_request(r)['status'], 'CLARIFY_MISSING_UNITS')
        r = self.request(); r['arguments']['fatigue_cycles'] = 1e6
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_REQUEST')

    def test_requested_output_cannot_be_silently_dropped(self):
        for output in ['fatigue_life', 'regulatory_acceptance', 'copper_loss']:
            r = self.request(wanted=['stress', output])
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_REQUEST')

    def test_physical_proof_exact_settling_and_complex_roots_not_supported(self):
        for cap, output in [('check_dimensional_equation', 'physical_validity'),
                            ('second_order_step', 'exact_settling_time'), ('quadratic_roots', 'complex_roots')]:
            self.assertEqual(self.run_request(self.request(cap, wanted=[output]))['status'], 'ABSTAIN_UNSUPPORTED_REQUEST')

    def test_reference_cannot_launder_applied_requirements(self):
        r = self.request(mode='reference'); r['conditions']['fatigue_included'] = True
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_REQUEST')

    def test_frequency_temperature_and_composite_unit_semantics(self):
        for unit in ['Hz', '1/s', 's', 'rpm']:
            r = self.request('dc_motor'); r['arguments']['angular_speed']['unit'] = unit
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_UNITS')
        for unit in ['degC', 'K']:
            r = self.request('thermal_expansion'); r['arguments']['delta_temperature']['unit'] = unit
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_UNITS')
        for fr, to in [('Hz','rad/s'), ('K','delta_K'), ('1','rad'), ('N*m','J')]:
            r = self.request('convert_units'); r['arguments'].update(from_unit=fr, to_unit=to)
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_UNITS')

    def test_nonfinite_boolean_and_invalid_numeric_domain(self):
        for value in [True, float('nan'), float('inf'), -1]:
            r = self.request(); r['arguments']['force']['value'] = value
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_INPUT_DOMAIN')
        r = self.request('second_order_step'); r['arguments']['damping_ratio'] = 1
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_INPUT_DOMAIN')
        r = self.request('quadratic_roots'); r['arguments']['a'] = 0
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_INPUT_DOMAIN')

    def test_numerical_overflow_and_zero_load_are_distinct(self):
        r = self.request(); r['arguments']['force']['value'] = 1e308; r['arguments']['area']['value'] = 1e-308
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_INPUT_DOMAIN')
        r = self.request(); r['arguments']['force']['value'] = 0
        result = self.run_request(r)
        self.assertEqual(result['status'], 'SUPPORTED_CALCULATION')
        self.assertIsNone(result['supported_answer']['factor_of_safety'])
        self.assertEqual(result['supported_answer']['factor_of_safety_status'], 'unbounded_zero_load')

    def test_schema_unknown_and_duplicate_selectors_refuse(self):
        for modify in [lambda r: r.update(unverified_claim='extra'),
                       lambda r: r.update(requested=['stress', 'stress']),
                       lambda r: r.update(mode='certify')]:
            r = self.request(); modify(r)
            self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_INVALID_REQUEST')

    def test_unknown_capability_refuses_even_with_candidates(self):
        r = self.request(); r['capability'] = 'fatigue_stress'
        self.assertEqual(self.run_request(r)['status'], 'ABSTAIN_UNSUPPORTED_CAPABILITY')

    def test_returned_contract_and_citations_cannot_mutate_gate(self):
        catalog = self.gate.catalog(); catalog['axial_stress']['conditions']['source_assumptions'].clear()
        r = self.request(); r['conditions'] = {}
        self.assertEqual(self.run_request(r)['status'], 'CLARIFY_MISSING_CONDITIONS')
        r = self.run_request(self.request(mode='reference')); r['supported_answer']['implementation'] = 'forged'
        self.assertIn('def axial_stress', self.run_request(self.request(mode='reference'))['supported_answer']['implementation'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
