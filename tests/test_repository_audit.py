import json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_repositories import canonical, classification, flags, record_hash
from consolidate_review import legacy_messages
class AuditTests(unittest.TestCase):
    def test_pair_preserves_math(self):
        raw={'prompt':'Evaluate $x^2$.','completion':'$x^2 = 4$\r\nUnits retained.'}
        messages,error=canonical(raw)
        self.assertIsNone(error); self.assertEqual(messages[-1]['content'],'$x^2 = 4$\nUnits retained.')
    def test_multiturn_system(self):
        m=[{'role':'system','content':'Be precise.'},{'role':'user','content':'Hi'},{'role':'assistant','content':'Hello'},{'role':'user','content':'Thanks'},{'role':'assistant','content':'Welcome'}]
        self.assertEqual(canonical({'messages':m}),(m,None))
    def test_reject_incomplete(self):
        self.assertEqual(canonical({'messages':[{'role':'user','content':'x'},{'role':'user','content':'y'}]})[1],'INVALID_ROLE_ORDER')
        self.assertEqual(canonical({'prompt':'x','completion':''})[1],'EMPTY_OR_NON_TEXT_CONTENT')
    def test_unknown_message_fields_are_not_dropped(self):
        self.assertEqual(canonical({'messages':[{'role':'user','content':'x'},{'role':'assistant','content':'y','tool_calls':[]}]})[1],'UNSUPPORTED_MESSAGE_FIELDS')
    def test_legacy_boundaries(self):
        m=legacy_messages('System: precise\nUser: calculate\nHAVOC: First line\nsecond line\nUser: thanks\nHAVOC: Welcome')
        self.assertEqual(m[2]['content'],'First line\nsecond line')
        self.assertEqual([x['role'] for x in m],['system','user','assistant','user','assistant'])
        with self.assertRaises(ValueError):legacy_messages('unlabelled prose')
    def test_nontext(self):
        self.assertEqual(canonical({'messages':[{'role':'user','content':[]},{'role':'assistant','content':'x'}]})[1],'EMPTY_OR_NON_TEXT_CONTENT')
    def test_privacy_paths(self):
        for p in ('../secret.jsonl','Military/data.jsonl','VA/data.jsonl','a/.env','bank-statement.txt'):
            self.assertEqual(classification(p),'excluded_path')
    def test_logs_not_training(self):
        self.assertEqual(classification('logs_phase1/val_examples.jsonl'),'training_log_or_evaluation_artifact')
        self.assertEqual(classification('sft_data/tokenizer_corpus.txt'),'tokenizer_corpus_not_sft')
    def test_exact_hash_retains_punctuation(self):
        self.assertNotEqual(record_hash([{'role':'user','content':'x+1'}]),record_hash([{'role':'user','content':'x-1'}]))
    def test_arithmetic_and_visual_flags(self):
        self.assertIn('NUMERIC_EQUALITY_MISMATCH',flags([{'role':'assistant','content':'2 + 2 = 5'}]))
        self.assertIn('VISUAL_OR_TABLE_DEPENDENCY_REVIEW',flags([{'role':'user','content':'See Figure 1.'}]))
if __name__=='__main__': unittest.main()
