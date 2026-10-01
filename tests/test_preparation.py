import dataclasses,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from forge_data.promotion import Proof,Stage,EvidenceState,blockers,promote
from forge_tools import engineering
from forge_tools.router import execute,verify_numeric_claim
from forge_tools.statistics import welch_ttest,anova_oneway,linear_regression,factorial_design,spc_known_sigma

class FiniteStatisticsTests(unittest.TestCase):
    def test_overflow_rejected(self):
        with self.assertRaises((ValueError,FloatingPointError,OverflowError)):
            welch_ttest([1e308,-1e308],[1e308,0])
        with self.assertRaises(ValueError):spc_known_sigma([1],1e308,1e308)
class PromotionTests(unittest.TestCase):
    def good(self):
        return Proof(lineage=True,immutable_source_hash=True,exact_location=True,privacy_pass=True,source_complete=True,provenance=EvidenceState.VERIFIED,rights=EvidenceState.VERIFIED,rights_evidence_ref='attestation+terms',source_evidence_ref='source',fidelity_pass=True,fidelity_review_ref='comparison',visual_dependencies_resolved=True,family_isolation_pass=True,family_manifest_ref='families')
    def test_unknown_rights_never_promoted(self):
        p=dataclasses.replace(self.good(),rights=EvidenceState.UNKNOWN)
        with self.assertRaises(ValueError):promote(Stage.REVIEW,Stage.VALIDATED,p)
    def test_parser_not_answer_proof(self):
        with self.assertRaises(ValueError):promote(Stage.VALIDATED,Stage.SFT_READY,self.good())
    def test_rag_does_not_require_solved_answers(self):
        p=dataclasses.replace(self.good(),citation_hash_offsets_verified=True)
        self.assertEqual(promote(Stage.VALIDATED,Stage.RAG_READY,p),Stage.RAG_READY)
    def test_missing_diagram_is_not_ready(self):
        p=dataclasses.replace(self.good(),visual_dependencies_resolved=False,citation_hash_offsets_verified=True)
        self.assertIn('VISUAL_DEPENDENCIES_RESOLVED',blockers(Stage.VALIDATED,Stage.RAG_READY,p))
    def test_no_state_skipping_or_string_flags(self):
        with self.assertRaises(ValueError):promote(Stage.RAW,Stage.RELEASED,self.good())
        with self.assertRaises(ValueError):Proof(privacy_pass='false')
    def test_release_rechecks_proofs(self):
        p=dataclasses.replace(self.good(),citation_hash_offsets_verified=True)
        self.assertIn('RELEASE_ARTIFACT_HASH_VERIFIED',blockers(Stage.RAG_READY,Stage.RELEASED,p))
    def test_eval_answers_private(self):
        p=dataclasses.replace(self.good(),question_complete=True,answer_verified=True,units_assumptions_checked=True,independent_heldout=True,grader_verified=True,answer_review_ref='adjudicated')
        self.assertIn('PRIVATE_TEST_DESTINATION',blockers(Stage.VALIDATED,Stage.EVAL_READY,p))
class ToolTests(unittest.TestCase):
    def test_welch_uses_satterthwaite(self):
        result=welch_ttest([1,2,3],[10,12,14,16,18]);self.assertAlmostEqual(result['df'],98/19);self.assertNotEqual(result['df'],6)
        self.assertAlmostEqual(result['difference'],-12);self.assertAlmostEqual(result['t'],-12/math.sqrt(7/3))
        self.assertLess(result['ci'][0],-12);self.assertGreater(result['ci'][1],-12)
    def test_regression_orientation_and_two_predictors(self):
        x=[[0,0],[1,0],[0,1],[1,1],[2,1]];y=[1+2*a+3*b for a,b in x];r=linear_regression(x,y)
        self.assertAlmostEqual(r['intercept'],1);self.assertAlmostEqual(r['coefficients'][0],2);self.assertAlmostEqual(r['coefficients'][1],3)
        with self.assertRaises(ValueError):linear_regression([[1,2,3],[4,5,6]],y)
    def test_anova_contract(self):
        r=anova_oneway([[1,2,3],[4,5,6]]);self.assertAlmostEqual(r['f'],13.5);self.assertEqual(r['df_within'],4)
    def test_factorial_orthogonality(self):
        matrix=factorial_design(['a','b','c'])['matrix'];self.assertEqual(len(matrix),8)
        self.assertTrue(all(sum(row[i] for row in matrix)==0 for i in range(3)))
        self.assertEqual(sum(row[0]*row[1] for row in matrix),0)
    def test_spc_known_limits(self):
        r=spc_known_sigma([9,10,11,14],10,1);self.assertEqual((r['lcl'],r['ucl']),(7,13));self.assertEqual(r['outside_3sigma_indices'],[3])
    def test_no_numeric_claim_not_a_pass(self):self.assertEqual(verify_numeric_claim(actual=None,reference=1)['state'],'NOT_APPLICABLE')
    def test_units_independent_dimensional_cases(self):
        self.assertAlmostEqual(engineering.convert_units(1,'N/mm^2','MPa'),1)
        self.assertAlmostEqual(engineering.convert_units(0,'degC','K'),273.15)
        with self.assertRaises(engineering.EngineeringError):engineering.convert_units(1,'Hz','rad/s')
        with self.assertRaises(engineering.EngineeringError):engineering.convert_units(1,'degC','delta_degC')
    def test_axial_stress_and_refusal(self):
        q=lambda v,u:{'value':v,'unit':u}
        r=execute('axial_stress',{'force':q(1000,'N'),'area':q(10,'mm^2'),'allowable_strength':q(200,'MPa')})['result']
        self.assertAlmostEqual(r['stress']['value'],1e8);self.assertAlmostEqual(r['factor_of_safety']['value'],2)
        with self.assertRaises(ValueError):execute('__import__',{})
    def test_stable_quadratic_residuals(self):
        roots=engineering.quadratic_roots(a=1,b=1e8,c=1)['real_roots'];self.assertAlmostEqual(roots[0]*roots[1],1)
        for x in roots:self.assertLess(abs(x*x+1e8*x+1)/max(1,abs(x*x),abs(1e8*x)),1e-12)
