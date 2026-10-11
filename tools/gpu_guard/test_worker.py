"""CPU-only sleeping process tree for kill-containment tests. No GPU libraries."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument("--output",required=True)
ap.add_argument("--role",choices=["root","child","grandchild"],default="root")
ap.add_argument("--lifetime",type=float,default=30)
args=ap.parse_args()
out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
(out/(args.role+".json")).write_text(json.dumps({"pid":os.getpid(),"role":args.role}),encoding="utf-8")
if args.role!="grandchild":
    next_role="child" if args.role=="root" else "grandchild"
    subprocess.Popen([sys.executable,__file__,"--output",str(out),"--role",next_role,"--lifetime",str(args.lifetime)],
                     creationflags=subprocess.CREATE_NO_WINDOW,close_fds=True)
time.sleep(args.lifetime)
