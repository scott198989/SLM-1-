"""Real SQLite replacement schedules; synthetic sources only."""
from contextlib import closing
import copy,json,sqlite3,unittest
from pathlib import Path
from unittest.mock import patch
import test_reference_excerpt as fixtures
from forge_data import citation_pilot as cp


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReferenceExcerptTests(methodName='runTest')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.release()
        self.good=self.f.index.read_bytes()
        self.fake='UNRELEASED_SYNTHETIC_SNAPSHOT_SENTINEL\n'
        (self.f.root/'unapproved.txt').write_bytes(self.fake.encode())
        bad=self.f.root/'bad.sqlite';bad.write_bytes(self.good)
        with closing(sqlite3.connect(bad)) as db:
            cite=json.loads(db.execute('SELECT citation FROM chunks').fetchone()[0])
            cite['source']={'path':'unapproved.txt','sha256':cp.sha(self.fake.encode()),
                            'slice_sha256':cp.sha(self.fake.encode()),'start_line':1,'end_line':1}
            db.execute('UPDATE chunks SET text=?,citation=?',(self.fake,json.dumps(cite)));db.commit()
        self.bad=bad.read_bytes()

    def quote(self):return self.f.call(chunk_id=self.f.chunk['id'])

    def repin_index_only(self,payload):
        self.f.index.write_bytes(payload)
        m=json.loads(self.f.manifest.read_bytes());m['index_sha256']=cp.sha(payload)
        self.f.manifest.write_text(json.dumps(m));self.f.pin=cp.sha(self.f.manifest.read_bytes())

    def test_transient_replacement_after_capture_cannot_supply_unapproved_rows(self):
        digest=cp.sha;source_slice=cp.source_slice;replaced=False;reads=[]
        original_read=Path.read_bytes
        def read(path):
            if path.resolve()==self.f.index.resolve():reads.append(str(path))
            return original_read(path)
        def schedule(data):
            nonlocal replaced
            if data==self.good and not replaced:
                replaced=True;self.f.index.write_bytes(self.bad)
            return digest(data)
        def restore(root,source):
            self.f.index.write_bytes(self.good)
            return source_slice(root,source)
        with patch.object(cp,'sha',side_effect=schedule),patch.object(cp,'source_slice',side_effect=restore),patch.object(Path,'read_bytes',read):
            result=self.quote()
        self.assertTrue(replaced)
        self.assertEqual(result['quote'],self.f.text)
        self.assertEqual(len(reads),1)
        self.assertEqual(self.f.index.read_bytes(),self.good)

    def test_changed_buffer_before_capture_rejects_even_if_path_restored(self):
        original=Path.read_bytes
        def replace(path):
            if path.resolve()==self.f.index.resolve():
                self.f.index.write_bytes(self.bad)
                captured=original(path)
                self.f.index.write_bytes(self.good)
                return captured
            return original(path)
        with patch.object(Path,'read_bytes',replace),self.assertRaisesRegex(ValueError,'index_drift'):
            self.quote()

    def test_unapproved_source_descriptor_rejects_even_with_rebound_index_pin(self):
        self.repin_index_only(self.bad)
        with self.assertRaisesRegex(ValueError,'source_descriptor_not_approved'):self.quote()

    def test_sidecar_appearing_during_capture_rejects(self):
        original=Path.read_bytes
        def sidecar(path):
            payload=original(path)
            if path.resolve()==self.f.index.resolve():Path(str(path)+'-wal').write_bytes(b'untrusted')
            return payload
        with patch.object(Path,'read_bytes',sidecar),self.assertRaisesRegex(ValueError,'sidecar_present'):self.quote()

    def test_malformed_authenticated_database_rejects_even_empty_query(self):
        for payload in [b'not sqlite',self.good[:100]]:
            with self.subTest(size=len(payload)):
                self.repin_index_only(payload)
                with self.assertRaisesRegex(ValueError,'sqlite'):
                    self.f.call('find_reference',query='')

    def test_snapshot_is_query_only(self):
        with closing(cp.open_frozen_index(self.f.index,expected_sha256=cp.sha(self.good))) as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM chunks')
        self.assertEqual(self.f.index.read_bytes(),self.good)

    def test_malformed_manifest_json_rejects(self):
        for data in [b'{"profile":"x","profile":"y"}',b'{"number":1e1000}',b'{"number":NaN}',b'[]',b'{']:
            with self.subTest(data=data):
                self.f.manifest.write_bytes(data);self.f.pin=cp.sha(data)
                with self.assertRaises(ValueError):self.quote()

    def test_duplicate_citation_json_rejects(self):
        with closing(sqlite3.connect(self.f.index)) as db:
            cite=db.execute('SELECT citation FROM chunks').fetchone()[0]
            db.execute('UPDATE chunks SET citation=?',('{"id":"shadow",'+cite[1:],));db.commit()
        self.repin_index_only(self.f.index.read_bytes())
        with self.assertRaisesRegex(ValueError,'duplicate_json_key'):self.quote()


if __name__=='__main__':unittest.main()
