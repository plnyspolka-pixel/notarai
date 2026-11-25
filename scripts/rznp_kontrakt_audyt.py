"""RZNP ZIP inventory (no extraction, no JAR execution)."""
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
import stat

def inventory(path):
    path = Path(path)
    if path.stat().st_size > 20*1024**2:
        raise ValueError("ZIP too large")
    rows, names = [], set()
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos)>128 or sum(i.file_size for i in infos)>40*1024**2:
            raise ValueError("ZIP limits exceeded")
        for i in infos:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or ".." in p.parts or chr(92) in i.filename or ":" in i.filename or i.filename in names or stat.S_ISLNK(i.external_attr>>16) or i.flag_bits&1:
                raise ValueError("Unsafe ZIP member")
            names.add(i.filename)
            if not i.is_dir():
                rows.append({"name":i.filename,"bytes":i.file_size,"sha256":hashlib.sha256(z.read(i)).hexdigest()})
    if sum(PurePosixPath(r["name"]).name=="rejestr-zastrzezen-proxy-contract.yml" for r in rows)!=1:
        raise ValueError("Expected exactly one official named contract")
    return {"status":"INVENTORY_ONLY","sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"files":rows}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive")
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    report=inventory(a.archive)
    with a.out.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2,ensure_ascii=False)
