"""Meaningful preview/confirmation boundaries and scripted wizard workflows."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.owned_retrieval import answerability, harness
from tools.owned_retrieval import test_answerability as source_fixture
from .cli import RequestSession, print_preview, save_new, sha_value, wizard


class RequestInterfaceTests(unittest.TestCase):
    def setUp(self):
        # Reuse source-only synthetic receipt setup, not private probe labels.
        self.fixture = source_fixture.AnswerabilityTests(methodName='runTest')
        self.fixture.setUp()
        self.root = self.fixture.root
        gate = self.fixture.gate
        target = {'review_commit': 'synthetic-test-target', 'review_status': 'TEST_ONLY',
                  'manifest': {'path': str(gate.retriever.path), 'sha256': gate.retriever.manifest_sha},
                  'gate_files': {n: harness.digest(Path(answerability.__file__).parent/n) for n in ['answerability.py', 'harness.py', 'numerical_policy.py']},
                  'catalog_sha256': sha_value(gate.catalog()), 'numerical_policy_sha256': sha_value(gate.numerical_policy())}
        self.target, pin = save_new(self.root/'target.json', target)
        self.session = RequestSession(self.target, pin)

    def tearDown(self):
        self.fixture.tearDown()

    def test_preview_never_executes_and_template_never_assumes_conditions(self):
        draft = self.session.template('axial_stress', 'calculate')
        self.assertTrue(all(v is None for v in draft['conditions'].values()))
        with patch.object(self.session.gate._calculator, 'execute_tool', side_effect=AssertionError('Must not calculate during preview')):
            self.assertEqual(self.session.preview(draft)['preflight_status'], 'CLARIFY')
            ready = self.session.preview(self.fixture.request())
            self.assertEqual(ready['preflight_status'], 'REVIEW_REQUIRED')
            self.assertFalse(ready['calculation_executed'])
            self.assertEqual(ready['evidence_citation']['source_sha256'], harness.SOURCE_SHA)

    def test_exact_preview_confirmation_and_request_echo(self):
        request = self.fixture.request()
        path, pin = save_new(self.root/'preview.json', self.session.preview(request))
        with self.assertRaises(harness.IntegrityError):
            self.session.execute(path, '0'*64)
        result = self.session.execute(path, pin)
        self.assertEqual(result['status'], 'SUPPORTED_CALCULATION')
        self.assertEqual(result['confirmed_request'], request)
        self.assertEqual(result['assessment']['supported_answer']['stress']['value'], 10000)

    def test_edited_preview_or_source_requires_new_review(self):
        p = self.session.preview(self.fixture.request())
        p['request']['arguments']['force']['value'] = 200
        path, pin = save_new(self.root/'edited.json', p)
        with self.assertRaises(harness.IntegrityError):
            self.session.execute(path, pin)
        path, pin = save_new(self.root/'fresh.json', self.session.preview(self.fixture.request()))
        self.fixture.source.write_text('changed', encoding='utf-8')
        with self.assertRaises(harness.IntegrityError):
            self.session.execute(path, pin)

    def test_review_target_change_is_detected_in_long_session(self):
        self.target.write_text('{}', encoding='utf-8')
        with self.assertRaises(harness.IntegrityError):
            self.session.preview(self.fixture.request())

    def test_clear_missing_conflicting_and_extreme_scope_without_calculation(self):
        cases = []
        r = self.fixture.request(); r['arguments']['area']['unit'] = ''; cases.append((r, 'CLARIFY'))
        r = self.fixture.request(); r['conditions']['static_loading'] = False; cases.append((r, 'UNSUPPORTED'))
        r = self.fixture.request(); r['arguments']['force']['value'] = 1e300; cases.append((r, 'UNSUPPORTED'))
        r = self.fixture.request(); r['requested'] = ['fatigue_life']; cases.append((r, 'UNSUPPORTED'))
        with patch.object(self.session.gate._calculator, 'execute_tool', side_effect=AssertionError('Must not calculate incomplete request')):
            for i, (request, expected) in enumerate(cases):
                p = self.session.preview(request)
                self.assertEqual(p['preflight_status'], expected)
                path, pin = save_new(self.root/f'blocked-{i}.json', p)
                self.assertEqual(self.session.execute(path, pin)['status'], expected)

    def test_malformed_request_renders_without_crash(self):
        for request in [None, [], {'capability': []}, {'capability': {}, 'mode': []}]:
            p = self.session.preview(request)
            self.assertEqual(p['preflight_status'], 'UNSUPPORTED')
            with contextlib.redirect_stdout(io.StringIO()):
                print_preview(p)

    def test_scripted_wizard_request_preview_then_run(self):
        # Scripted test input is not recorded as independent human review.
        responses = ['3', '1', '1', 'no', '100', 'N', '.01', 'm^2', '1000000', 'Pa', 'yes', 'yes', 'yes', 'RUN']
        output = io.StringIO()
        with patch('builtins.input', side_effect=responses), contextlib.redirect_stdout(output):
            code = wizard(self.session, self.root/'wizard.preview.json')
        self.assertEqual(code, 0)
        transcript = output.getvalue()
        self.assertLess(transcript.index('REQUEST PREVIEW'), transcript.index('CONFIRMED STRUCTURED REQUEST'))
        self.assertIn('SUPPORTED_CALCULATION', transcript)
        self.assertIn('arguments.force: 100.0 N', transcript)
        self.assertIn('conditions.static_loading: true', transcript)

    def test_scripted_wizard_declining_run_does_not_calculate(self):
        responses = ['3', '2', '4', 'no', '']
        with patch('builtins.input', side_effect=responses), contextlib.redirect_stdout(io.StringIO()), patch.object(self.session.gate._calculator, 'execute_tool', side_effect=AssertionError('Unconfirmed')):
            code = wizard(self.session, self.root/'saved.preview.json')
        self.assertEqual(code, 0)
        self.assertFalse((self.root/'saved.preview.result.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
