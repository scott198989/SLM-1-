"""Content-free consistent SQLite snapshot of the authorized academic job."""
import argparse,collections,csv,datetime,json,sqlite3
from pathlib import Path

def snapshot(database, inventory, destination, catalog):
    c=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('BEGIN')
    output_count=c.execute('SELECT COUNT(*) FROM outputs').fetchone()[0]
    if output_count: raise RuntimeError('approved_output_counts_require_explicit_reconciliation')
    rows=list(c.execute('SELECT * FROM files'));status=collections.Counter(r['status'] for r in rows);roots=collections.defaultdict(collections.Counter)
    for r in rows:
        if r['status']!='excluded':roots[r['path'].replace('\\','/').split('/')[0]][r['status']]+=1
    units=[dict(r) for r in c.execute("SELECT u.status,COUNT(*) count,SUM(u.chars) chars FROM units u JOIN files f ON f.id=u.file_id WHERE f.status='extracted_needs_review' AND u.status<>'superseded' AND u.version=substr(f.content_hash,1,20) GROUP BY u.status")]
    report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':dict(status),'total_inventory_entries':len(rows),'root_nonexcluded_statuses':dict(roots),'active_units':units,'file_mimes':[dict(r) for r in c.execute('SELECT mime,status,COUNT(*) count FROM files GROUP BY mime,status')],'blockers':[dict(r) for r in c.execute("SELECT reason,COUNT(*) count FROM files WHERE status='blocked' GROUP BY reason")],'subjects':[dict(r) for r in c.execute("SELECT subject,status,COUNT(*) count FROM files WHERE status<>'excluded' GROUP BY subject,status")],'ready_sft_records':0,'ready_rag_chunks':0,'academic_folders':len(json.loads(inventory.read_text(encoding='utf-8'))['folders']),'attempts':c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],'readiness_basis':'No approved outputs exist in the recorded job; review RAG pilot is not production approved.'}
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    fields=['id','title','path','mime','subject','status','reason','content_hash']
    with catalog.open('w',encoding='utf-8-sig',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        for r in rows:writer.writerow({k:(r[k] if r['status']!='excluded' or k in ['id','status','reason'] else '[excluded]') for k in fields})
    c.close();return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);a=p.parse_args();r=snapshot(a.database,a.inventory,a.output,a.catalog);print(json.dumps({k:v for k,v in r.items() if k not in ['file_mimes','subjects']},indent=2))
