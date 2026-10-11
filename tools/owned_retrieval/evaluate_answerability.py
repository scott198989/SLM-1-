"""Evaluation of explicit requests; labels are consulted only after assessment."""
from collections import Counter
from datetime import datetime, timezone
import math

from .answerability import AnswerabilityGate


def _matches(actual, expected):
    # Quantity expectations must include units. Never strip schema information
    # to accommodate older weak scalar-only labels. Those labels must fail.
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_matches(actual[k], v) for k, v in expected.items())
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_matches(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        try:
            if not math.isfinite(actual) or not math.isfinite(expected):
                return False
            if expected == 0:
                return actual == 0  # No blanket absolute tolerance near zero.
            if actual == 0 or (actual > 0) != (expected > 0):
                return False
            return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0.0)
        except OverflowError:
            return False
    return type(actual) is type(expected) and actual == expected


def evaluate(retriever, probes, *, methods=('lexical',), saved_vectors=None):
    gate = AnswerabilityGate(retriever)
    rows = []
    for probe in probes:
        for method in methods:
            vector = None
            if method != 'lexical':
                saved = saved_vectors[probe['id']]
                if saved['query'] != probe['query']:
                    raise ValueError('Saved query text mismatch')
                vector = saved['vector']
            # Labels are never supplied to ranking/gate; allowed_ids is an
            # explicit request restriction used by boundary probes only.
            result = gate.search_and_assess(probe['query'], probe.get('request'),
                method=method, query_vector=vector, top_k=3,
                allowed_ids=probe.get('allowed_ids'))
            assessment = result['assessment']
            expected = probe['expected_status']
            correct = assessment['status'] == expected
            numerical = None
            if 'expected_value' in probe:
                output = (assessment.get('supported_answer') or {}).get(probe['request']['requested'][0])
                numerical = _matches(output, probe['expected_value'])
                correct = correct and numerical
            grounding = None
            if 'grounding_clause' in probe:
                answer = assessment.get('supported_answer') or {}
                grounding = probe['grounding_clause'] in answer.get('implementation', '')
                correct = correct and grounding
            rows.append({'id': probe['id'], 'category': probe['category'], 'method': method,
                'query': probe['query'], 'expected_status': expected,
                'actual_status': assessment['status'], 'passed': correct,
                'numeric_oracle_passed': numerical, 'grounding_clause_present': grounding,
                'candidate_ids': [h['id'] for h in result['search_result']['hits']],
                'assessment': assessment})
    summary = {}
    for method in methods:
        group = [x for x in rows if x['method'] == method]
        negatives = [x for x in group if not x['expected_status'].startswith('SUPPORTED_')]
        positives = [x for x in group if x['expected_status'].startswith('SUPPORTED_')]
        summary[method] = {'probes': len(group), 'passed': sum(x['passed'] for x in group),
            'supported_expected': len(positives),
            'supported_correct': sum(x['passed'] for x in positives),
            'unsupported_or_incomplete_expected': len(negatives),
            'false_supported_results': sum(x['actual_status'].startswith('SUPPORTED_') for x in negatives),
            'statuses': dict(Counter(x['actual_status'] for x in group)),
            'by_category': {cat: {'count': sum(x['category'] == cat for x in group),
                                 'passed': sum(x['category'] == cat and x['passed'] for x in group)}
                            for cat in sorted({x['category'] for x in group})}}
    return {'at_utc': datetime.now(timezone.utc).isoformat(), 'summary': summary, 'results': rows,
            'labels_used_for_ranking_or_gate': False, 'natural_language_intent_inference_tested': False,
            'same_agent_authored': True, 'independent_expert_validation': False,
            'generator_used': False, 'new_model_inference': False}
