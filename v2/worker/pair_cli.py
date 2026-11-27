"""Issue/revoke prototype device credentials using the local admin API."""
import argparse
import json
import urllib.request
from .init_vault import home_path
from .local_secrets import read_secret

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="action",required=True)
    invite=sub.add_parser("invite")
    invite.add_argument("name")
    invite.add_argument("--scope",choices=["read","write"],default="read")
    sub.add_parser("list")
    revoke=sub.add_parser("revoke")
    revoke.add_argument("id")
    args=parser.parse_args()
    token=read_secret(home_path(),"api.token").decode().strip()
    url="http://127.0.0.1:8765/v2/devices"
    method="GET"
    data=None
    if args.action=="invite":
        url+="/invite"
        method="POST"
        data=json.dumps({"name":args.name,"scope":args.scope}).encode()
    elif args.action=="revoke":
        import uuid
        url+="/"+str(uuid.UUID(args.id))
        method="DELETE"
    request=urllib.request.Request(url,data=data,method=method,headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request,timeout=5) as response:
        print(json.dumps(json.load(response),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
