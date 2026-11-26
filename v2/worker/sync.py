"""Read-only manifest comparison; no blind overwrites or deletion propagation."""
import uuid

def plan(server, client):
    remote = {item["id"]:item["version"] for item in server}
    local = {}
    for item in client:
        doc_id = str(uuid.UUID(item["id"]))
        version = item["version"]
        if type(version) is not int or version < 1 or doc_id in local:
            raise ValueError("invalid manifest")
        local[doc_id] = version
    result={"download":[],"review":[],"unchanged":[]}
    for doc_id in sorted(remote.keys() | local.keys()):
        sv,cv=remote.get(doc_id),local.get(doc_id)
        if sv == cv:
            result["unchanged"].append(doc_id)
        elif sv is not None and (cv is None or cv < sv):
            result["download"].append({"id":doc_id,"version":sv})
        else:
            result["review"].append({"id":doc_id,"server_version":sv,"client_version":cv})
    return result
