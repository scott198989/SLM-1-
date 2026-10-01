"""Fetch only three pinned, hash-checked text assets; no model weights."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'config.json','tokenizer.json','tokenizer_config.json'}
def main(destination):
    manifest=json.loads((ROOT/'manifests/qwen-tokenizer-assets.json').read_text())
    if manifest['model']!='Qwen/Qwen3-30B-A3B-Base' or {x['path'] for x in manifest['assets']}!=ALLOWED:raise ValueError('unexpected_asset_allowlist')
    destination.mkdir(parents=True,exist_ok=True)
    for asset in manifest['assets']:
        url=f"https://huggingface.co/{manifest['model']}/resolve/{manifest['revision']}/{asset['path']}"
        with urllib.request.urlopen(url,timeout=60) as response:data=response.read(asset['bytes']+1)
        if len(data)!=asset['bytes'] or hashlib.sha256(data).hexdigest()!=asset['sha256']:raise ValueError('asset_size_or_hash_mismatch')
        target=destination/asset['path'];temporary=target.with_suffix(target.suffix+'.partial')
        temporary.write_bytes(data);temporary.replace(target)
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);main(parser.parse_args().destination)
