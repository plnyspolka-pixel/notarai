"""Large reproducible SYNTHETIC coding corpus; 10 families x 20 contracts.

Contracts are variations of TEN algorithmic problem families, NOT 200
statistically independent algorithm families. Each task has 8 deterministic
oracle-checked example inputs held OUTSIDE worker prompts. Task ID parity
determines dev vs heldout (no task overlaps); family overlap remains, so the
holdout is not a true distribution-shift/real-world generalization test.

This module does not call models, evaluate generated code or write private data.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

FAMILIES = (
    "numeric", "text", "records", "authorization", "timeslots",
    "dependencies", "eventlog", "redaction", "slugs", "intervals",
)
COUNT_PER_FAMILY = 20
CASES_PER_TASK = 8
VERSION = "worker-army-synthetic-200-v1"


def _cfg(family: str, variant: int) -> dict:
    if family not in FAMILIES or type(variant) is not int or not 0 <= variant < 20:
        raise ValueError("unsupported algorithm family or variant")
    if family == "numeric":
        return {"predicate": ("even", "odd", "positive", "nonnegative", "negative")[variant % 5],
                "operation": ("abs", "square", "add", "negate")[variant // 5],
                "offset": 1 + variant % 7}
    if family == "text":
        return {"filter": ("contains_a", "starts_a", "nonempty", "longer3", "ends_n")[variant % 5],
                "order": ("asc", "desc")[variant // 5 % 2],
                "dedup": bool(variant // 10 % 2)}
    if family == "records":
        return {"minimum": variant % 5, "dedup": ("first", "last")[variant // 5 % 2],
                "order": ("asc", "desc")[variant // 10 % 2]}
    if family == "authorization":
        return {"writer": ("editor", "staff", "owner", "admin", "operator")[variant % 5],
                "tenant": bool(variant // 5 % 2),
                "approval": bool(variant // 10 % 2)}
    if family == "timeslots":
        return {"gap": variant % 5, "cap": (0, 2, 4, 6)[variant // 5]}
    if family == "dependencies":
        return {"direction": ("upstream", "downstream")[variant % 2],
                "depth": ("direct", "transitive")[variant // 2 % 2],
                "include_changed": bool(variant // 4 % 2),
                "limit": variant // 8,
                "ignore_missing": True}
    if family == "eventlog":
        return {"by_revision": bool(variant % 2),
                "dedup_event_id": bool(variant // 2 % 2),
                "skip_negative": bool(variant // 4 % 2),
                "default_value": variant // 8}
    if family == "redaction":
        return {"tokens": bool(variant % 2),
                "emails": bool(variant // 2 % 2),
                "ids11": bool(variant // 4 % 2),
                "marker": ("[HIDDEN]", "[MASKED]", "[REDACTED]")[variant // 8]}
    if family == "slugs":
        return {"separator": ("-", "_")[variant % 2],
                "uppercase": bool(variant // 2 % 2),
                "max_chars": (8, 12, 16, 20, 32)[variant // 4]}
    return {"merge_touching": bool(variant % 2),
            "minimum_length": 1 + variant // 2}


def _prompt(family: str, cfg: dict) -> str:
    text = {
        "numeric": "solve(data): data is a list of integers. Keep numbers satisfying predicate {predicate}. For each retained number apply operation {operation} (add uses offset={offset}). Return the integer SUM of transformed numbers; empty returns zero.",
        "text": "solve(data): data is list of strings. Strip whitespace and casefold each item. Filter normalized items by {filter} (longer3 means length > 3). Remove duplicates? {dedup}. Sort normalized strings in {order} lexical order. Return list of strings.",
        "records": "solve(data): data is list of dicts with id and integer score. Ignore malformed records (id must be nonempty string, score must be exact int). For repeated IDs keep the {dedup} valid record. Keep records with score >= {minimum}. Return list of ID strings sorted by score {order}, with ID as ascending tiebreaker.",
        "authorization": "solve(data): data is dictionary with role, action, optional actor_tenant, resource_tenant and approved. Reader may read; {writer} may read/write; admin may read/write/delete. Unknown action/role denies. Tenant equality required? {tenant} (if required, both tenant values must be nonempty strings and equal). Delete requires approved is exactly True? {approval}. Return bool, fail closed on malformed input.",
        "timeslots": "solve(data): dict with integer start,end,duration,step and optional blocked list of integer [start,end] pairs. Return ascending valid start times. A slot [t,t+duration) must fit before or at end and not intersect any blocked interval after extending each blocked interval by {gap} minutes on each side. If cap={cap} is nonzero return at most cap results. Invalid data returns [].",
        "dependencies": "solve(data): dict with imports mapping module -> list of imported module names and changed list. Follow edges in {direction} direction ({depth}); include changed named modules? {include_changed}. Ignore unknown module names. Return sorted unique list of affected known module names, restricted to at most {limit} entries when limit > 0. Avoid infinite loops on cycles.",
        "eventlog": "solve(data): list of event dictionaries with string id,key, op set/delete, integer rev and optional value. Ignore malformed entries and invalid revision types. Apply only rev>=0? {skip_negative}. Ignore duplicate event IDs? {dedup_event_id}. Choose newest rev per key? {by_revision} (if true, only events with strictly higher rev than existing key history apply; else apply in input order). set stores value (missing value defaults to {default_value}); delete removes key. Return dict of live keys with sorted key insertion order.",
        "redaction": "solve(data): data is a text string. Replace credential strings matching the literal prefix sk- followed by at least 8 ASCII alphanumeric chars? {tokens}; replace emails matching ASCII local@domain.tld? {emails}; replace stand-alone exactly 11-digit identifiers? {ids11}. Use exact marker {marker} for each enabled category. Preserve all nonmatching text. Nonstring input returns empty string.",
        "slugs": "solve(data): data is text string. Strip surrounding whitespace, lowercase English ASCII letters, replace runs of NON-alphanumeric ASCII chars with separator {separator}, strip leading/trailing separators. Convert result to uppercase? {uppercase}. Truncate final result to {max_chars} characters, then strip trailing separators. For nonstring return empty string. Keep only letters a-z and digits 0-9.",
        "intervals": "solve(data): data is list of [start,end] pairs with exact integer endpoints and start<end. Ignore malformed pairs. Remove ranges shorter than {minimum_length}. Merge overlapping half-open intervals, also merge exactly touching intervals? {merge_touching}. Return sorted list of integer [start,end] pairs.",
    }[family]
    return text.format(**cfg)


def make_task(family: str, variant: int) -> dict:
    cfg = _cfg(family, variant)
    id_ = "L%02d-%02d" % (FAMILIES.index(family) + 1, variant)
    statement = _prompt(family, cfg)
    return {
        "id": id_, "family": family, "variant": variant,
        "split": "development" if variant < 10 else "heldout",
        "entrypoint": "solve(data)", "instruction": statement,
        "contract": cfg, "data_class": "synthetic",
        "task_sha256": hashlib.sha256(statement.encode()).hexdigest(),
    }


def tasks(split: str = "all") -> list[dict]:
    if split not in ("all", "development", "heldout"):
        raise ValueError("invalid split")
    records = [make_task(family, variant)
               for family in FAMILIES for variant in range(COUNT_PER_FAMILY)]
    return records if split == "all" else [
        task for task in records if task["split"] == split
    ]


def oracle(family: str, cfg: dict, data):
    if family == "numeric":
        result = 0
        for n in data:
            if type(n) is not int:
                continue
            ok = {"even": n % 2 == 0, "odd": n % 2 != 0,
                  "positive": n > 0, "nonnegative": n >= 0, "negative": n < 0}[cfg["predicate"]]
            if ok:
                x = {"abs": abs(n), "square": n*n, "add": n+cfg["offset"], "negate": -n}[cfg["operation"]]
                result += x
        return result
    if family == "text":
        if not isinstance(data, list):
            return []
        norm = [x.strip().casefold() for x in data if isinstance(x, str)]
        test = {
            "contains_a": lambda x: "a" in x,
            "starts_a": lambda x: x.startswith("a"),
            "nonempty": lambda x: bool(x),
            "longer3": lambda x: len(x) > 3,
            "ends_n": lambda x: x.endswith("n")
        }[cfg["filter"]]
        out = [x for x in norm if test(x)]
        if cfg["dedup"]:
            out = list(dict.fromkeys(out))
        return sorted(out, reverse=cfg["order"] == "desc")
    if family == "records":
        d = {}
        for x in data:
            if not isinstance(x, dict):
                continue
            id_, score = x.get("id"), x.get("score")
            if not isinstance(id_, str) or not id_ or type(score) is not int:
                continue
            if cfg["dedup"] == "last" or id_ not in d:
                d[id_] = score
        rows = [(id_, score) for id_, score in d.items() if score >= cfg["minimum"]]
        rows.sort(key=lambda item: (item[1] if cfg["order"] == "asc" else -item[1], item[0]))
        return [id_ for id_, _ in rows]
    if family == "authorization":
        if not isinstance(data, dict):
            return False
        role, action = data.get("role"), data.get("action")
        allowed = {"reader": {"read"}, cfg["writer"]: {"read", "write"},
                   "admin": {"read", "write", "delete"}}
        if role not in allowed or action not in allowed[role]:
            return False
        if cfg["tenant"]:
            a,b = data.get("actor_tenant"), data.get("resource_tenant")
            if not isinstance(a,str) or not isinstance(b,str) or not a or a != b:
                return False
        if cfg["approval"] and action == "delete" and data.get("approved") is not True:
            return False
        return True
    if family == "timeslots":
        if not isinstance(data, dict):
            return []
        start,end,duration,step = (data.get(k) for k in ("start","end","duration","step"))
        if any(type(v) is not int for v in (start,end,duration,step)) or start >= end or duration <= 0 or step <= 0:
            return []
        blocks = data.get("blocked", [])
        if not isinstance(blocks, list):
            return []
        for b in blocks:
            if not isinstance(b,(list,tuple)) or len(b)!=2 or any(type(v) is not int for v in b) or b[0] >= b[1]:
                return []
        out = []
        for x in range(start,end,step):
            if x+duration > end:
                break
            if all(x+duration <= a-cfg["gap"] or x >= b+cfg["gap"] for a,b in blocks):
                out.append(x)
                if cfg["cap"] and len(out) >= cfg["cap"]:
                    break
        return out
    if family == "dependencies":
        if not isinstance(data,dict) or not isinstance(data.get("imports"),dict) or not isinstance(data.get("changed"),list):
            return []
        imports = data["imports"]
        keys = {k for k in imports if isinstance(k,str)}
        graph = {k: set() for k in keys}
        for mod, deps in imports.items():
            if mod not in keys or not isinstance(deps,list):
                continue
            for dep in deps:
                if isinstance(dep,str) and dep in keys:
                    if cfg["direction"]=="upstream":
                        graph[mod].add(dep)
                    else:
                        graph[dep].add(mod)
        starts = {x for x in data["changed"] if isinstance(x,str) and x in keys}
        touched = set(starts) if cfg["include_changed"] else set()
        todo = set(starts)
        visited = set(starts)
        while todo:
            candidate = set()
            for k in todo:
                candidate |= graph[k]
            touched |= candidate - starts
            candidate -= visited
            visited |= candidate
            if cfg["depth"]=="direct":
                break
            todo = candidate
        result = sorted(touched)
        return result[:cfg["limit"]] if cfg["limit"] else result
    if family == "eventlog":
        if not isinstance(data,list):
            return {}
        result, revisions, seen = {}, {}, set()
        for e in data:
            if not isinstance(e,dict):
                continue
            id_,key,op,rev=e.get("id"),e.get("key"),e.get("op"),e.get("rev")
            if any(not isinstance(v,str) or not v for v in (id_,key)) or op not in ("set","delete") or type(rev) is not int:
                continue
            if cfg["skip_negative"] and rev < 0:
                continue
            if cfg["dedup_event_id"] and id_ in seen:
                continue
            if cfg["dedup_event_id"]:
                seen.add(id_)
            if cfg["by_revision"] and rev <= revisions.get(key,float("-inf")):
                continue
            revisions[key] = rev
            if op=="delete":
                result.pop(key,None)
            else:
                result[key]=e.get("value",cfg["default_value"])
        return dict(sorted(result.items()))
    if family == "redaction":
        if not isinstance(data,str):
            return ""
        out=data
        if cfg["tokens"]:
            out=re.sub(r"sk-[A-Za-z0-9]{8,}",cfg["marker"],out)
        if cfg["emails"]:
            out=re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",cfg["marker"],out)
        if cfg["ids11"]:
            out=re.sub(r"(?<!\d)\d{11}(?!\d)",cfg["marker"],out)
        return out
    if family == "slugs":
        if not isinstance(data,str):
            return ""
        raw=data.strip().lower()
        out=re.sub(r"[^a-z0-9]+",cfg["separator"],raw).strip(cfg["separator"])
        if cfg["uppercase"]:
            out=out.upper()
        return out[:cfg["max_chars"]].rstrip(cfg["separator"])
    if family == "intervals":
        intervals = []
        if not isinstance(data,list):
            return []
        for v in data:
            if (not isinstance(v,(tuple,list)) or len(v)!=2 or
                    type(v[0]) is not int or type(v[1]) is not int or v[0]>=v[1]):
                continue
            if v[1]-v[0]>=cfg["minimum_length"]:
                intervals.append(list(v))
        intervals.sort()
        merged=[]
        for a,b in intervals:
            if not merged or (a>merged[-1][1] if cfg["merge_touching"] else a>=merged[-1][1]):
                merged.append([a,b])
            else:
                merged[-1][1]=max(merged[-1][1],b)
        return merged
    raise ValueError("unknown family")


def samples(task: dict, count: int = CASES_PER_TASK) -> list[dict]:
    if type(count) is not int or not 1 <= count <= 40:
        raise ValueError("invalid case count")
    # Separate per-task random seeds; the worker only sees task["instruction"].
    seed = int(hashlib.sha256((VERSION+task["id"]).encode()).hexdigest()[:15],16)
    rng=random.Random(seed)
    out=[]
    for i in range(count):
        family=task["family"]
        if family=="numeric":
            payload=[rng.randint(-9,10) for _ in range(i%7+1)]
        elif family=="text":
            words=["Antenna"," apple ","CAnNon","banana","sun","", "PAnda"," BAn ","  a  "]
            payload=[rng.choice(words) for _ in range(i%7+2)]
        elif family=="records":
            payload=[{"id":rng.choice(["a","b","c","d"]),"score":rng.randint(-2,8)}
                     for _ in range(i%7+3)]
            if i%3==0: payload.append({"id":"","score":2})
            if i%4==0: payload.append({"id":"x","score":True})
        elif family=="authorization":
            payload={"role":rng.choice(["reader","editor","staff","owner","admin","operator","hacker"]),
                     "action":rng.choice(["read","write","delete","exec"]),
                     "actor_tenant":rng.choice(["a","b",""]),
                     "resource_tenant":rng.choice(["a","b",""]),
                     "approved":rng.choice([True,False,"true"])}
        elif family=="timeslots":
            payload={"start":rng.choice([0,2,5,8]),"end":rng.randint(12,30),
                     "duration":rng.choice([1,2,3,5]),"step":rng.choice([1,2,3,4]),
                     "blocked":[[a:=rng.randint(2,10),a+rng.randint(1,5)]] if i%2==0 else []}
        elif family=="dependencies":
            payload={"imports":{"a":["b"],"b":["c"],"c":[],"d":["b"],"e":["d"],"f":["g"],"g":[]},
                     "changed":[rng.choice(["a","b","c","d","z"])]}
        elif family=="eventlog":
            payload=[{"id":rng.choice(["e1","e2","e3","e4"]),"key":rng.choice(["a","b","c"]),
                      "op":rng.choice(["set","delete"]), "rev":rng.randint(-2,5),"value":rng.randint(0,10)}
                     for _ in range(3+i%7)]
        elif family=="redaction":
            segments=["hello","sk-abcdefghij","contact x@y.io","12345678901",
                      "ordinary","sk-no","1234567890123", "a@b.com"]
            payload=" ".join(rng.choice(segments) for _ in range(2+i%5))
        elif family=="slugs":
            payload=rng.choice(["  Hello   World!  ","Cafe au lait","A__B...C","what-now?",
                               "UPPER lower","eng #42", "ąbč","a    b    c"]) + str(i)
        else:
            payload=[]
            for _ in range(i%7+3):
                start=rng.randint(-4,18)
                payload.append([start,start+rng.randint(1,10)])
            if i%3==0: payload.append([2,2])
        out.append({"case_id":task["id"]+"-c"+str(i),
                    "input":payload,"expected":oracle(family,task["contract"],payload)})
    return out


def summary() -> dict:
    rows=tasks()
    dev=tasks("development")
    hold=tasks("heldout")
    if len(rows)!=200 or len(dev)!=100 or len(hold)!=100:
        raise AssertionError("unexpected generated suite cardinality")
    if set(t["id"] for t in dev) & set(t["id"] for t in hold):
        raise AssertionError("data leakage: task IDs overlap")
    if len({t["task_sha256"] for t in rows})!=len(rows):
        raise AssertionError("not enough distinct public specifications")
    return {"schema_version":1, "suite":VERSION,
            "families":len(FAMILIES),"distinct_parameterized_contracts":len(rows),
            "development_contracts":len(dev),"heldout_contracts":len(hold),
            "oracle_cases_per_contract":CASES_PER_TASK,
            "oracle_case_count":len(rows)*CASES_PER_TASK,
            "structural_templates":len(FAMILIES),
            "caveat":"Parameter variations within a family are correlated; not 200 independent algorithms.",
            "model_calls":0, "weight_training":False}


if __name__=="__main__":
    print(json.dumps(summary(),indent=2))
