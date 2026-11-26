"""Read-only Microsoft WinApp CLI adapter, local operator diagnostics only."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from .connect import Result, State, Router

class WinApp:
    name = "winapp"
    def __init__(self, executable, runner=None):
        path = Path(executable)
        if not path.is_absolute() or path.suffix.lower() != ".exe":
            raise ValueError("absolute trusted .exe path required")
        self.exe = path
        self.runner = runner or subprocess.run
        self.injected_runner = runner is not None

    def supports(self, operation):
        return operation in {"inspect_window","list_windows"} and (self.injected_runner or (os.name == "nt" and self.exe.is_file()))

    def execute(self, operation, args):
        if operation == "inspect_window":
            hwnd = args.get("hwnd")
            if type(hwnd) is not int or not 0 < hwnd < 2**64:
                raise ValueError("explicit HWND required")
            depth = args.get("depth",3)
            if type(depth) is not int or not 1 <= depth <= 5:
                raise ValueError("invalid depth")
            if set(args) - {"hwnd","depth"}:
                raise ValueError("unexpected arguments")
            command = ["ui","inspect","-w",str(hwnd),"--depth",str(depth),"--json"]
        elif operation == "list_windows":
            if args:
                raise ValueError("unexpected arguments")
            command = ["ui","list-windows","--json"]
        else:
            raise PermissionError("read-only")
        # Do not inherit AWS credentials or arbitrary CLI arguments.
        allowed = {"systemroot","windir","temp","tmp","localappdata","appdata","userprofile","programfiles","programfiles(x86)","programdata","path"}
        env = {k:v for k,v in os.environ.items() if k.lower() in allowed}
        proc = self.runner([str(self.exe),*command], shell=False, capture_output=True, timeout=15, env=env, cwd=str(self.exe.parent))
        if proc.returncode != 0 or len(proc.stdout) > 2_000_000:
            return Result(State.UNCERTAIN,self.name)
        try:
            data = json.loads(proc.stdout)
        except (ValueError,UnicodeError):
            return Result(State.UNCERTAIN,self.name)
        if operation == "inspect_window":
            if not isinstance(data,dict) or not isinstance(data.get("windows"),list) or len(data["windows"]) != 1 or str(data["windows"][0].get("hwnd")) != str(hwnd):
                return Result(State.UNCERTAIN,self.name)
        elif not isinstance(data,(dict,list)):
            return Result(State.UNCERTAIN,self.name)
        return Result(State.VERIFIED,self.name,data)

def main():
    p=argparse.ArgumentParser(description="Local synthetic-only Windows UI diagnostics. Output may contain sensitive text.")
    p.add_argument("--winapp",required=True,help="Absolute path to operator-verified Microsoft executable")
    p.add_argument("--hwnd",type=int)
    p.add_argument("--synthetic-only",action="store_true",required=True)
    args=p.parse_args()
    op="inspect_window" if args.hwnd is not None else "list_windows"
    result=Router([WinApp(args.winapp)]).run(op,{"hwnd":args.hwnd} if args.hwnd is not None else {})
    print(json.dumps({"state":result.state.value,"backend":result.backend,"data":result.data},ensure_ascii=True))
    return 0 if result.state == State.VERIFIED else 1

if __name__ == "__main__":
    raise SystemExit(main())
