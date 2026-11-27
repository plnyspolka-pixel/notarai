"""Create a private, hash-indexed evidence manifest. Never certifies compliance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

REQUIRED = ("D01","D02","D03","D04","D05","D06")
STATES = {"GOTOWE","CZESCIOWE","BLOKER","NIEZWERYFIKOWANE"}

def index(root, rows):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Expected evidence directory")
    if not isinstance(rows,list) or len(rows)!=len(REQUIRED) or {r.get("id") for r in rows}!=set(REQUIRED):
        raise ValueError("Expected exactly D01-D06")
    results=[]
    for row in sorted(rows,key=lambda r:r["id"]):
        state=row.get("status")
        if state not in STATES:
            raise ValueError("Invalid declared status")
        refs=row.get("files",[])
        if not isinstance(refs,list) or len(refs)>100:
            raise ValueError("Invalid file list")
        evidence=[]
        for ref in refs:
            path=Path(ref)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe evidence path")
            target=root/path
            if any((root.joinpath(*path.parts[:n])).is_symlink() for n in range(1,len(path.parts)+1)):
                raise ValueError("Symlinks forbidden")
            resolved=target.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise ValueError("Invalid evidence file")
            h=hashlib.sha256()
            with resolved.open("rb") as f:
                for block in iter(lambda:f.read(65536),b""):
                    h.update(block)
            evidence.append({"file":path.as_posix(),"sha256":h.hexdigest(),"bytes":resolved.stat().st_size})
        if state=="GOTOWE" and not evidence:
            raise ValueError("Ready requires evidence")
        if state!="GOTOWE" and not str(row.get("next_step","")).strip():
            raise ValueError("Unresolved item requires next step")
        results.append({"id":row["id"],"declared_status":state,"evidence":evidence,
                        "next_step":row.get("next_step","")})
    return {"schema":1,"created_at":datetime.now(timezone.utc).isoformat(),
            "scope":"File integrity and completeness only; status declared by reviewer",
            "items":results,"unresolved":[r["id"] for r in results if r["declared_status"]!="GOTOWE"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    if any(x.resolve().is_relative_to(repo) for x in (a.root,a.plan,a.out)):
        p.error("Use private locations outside git checkout")
    result=index(a.root,json.loads(a.plan.read_text("utf-8")))
    import os
    fd=os.open(a.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    return 2 if result["unresolved"] else 0

if __name__=="__main__":
    raise SystemExit(main())
