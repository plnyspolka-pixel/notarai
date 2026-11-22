"""Local smoke probe on a TEST Windows VM with WinApp CLI installed.

Run from repository root:
  python -m examples.computer_use_windows_probe --app notepad

No changes are made to the target application. Only aggregate control counts
are printed; raw UI text and clients' data stay inside the local process.
"""
import argparse
import json
from collections import Counter

from computer_use.discovery import WinAppDiscovery
from computer_use.profiles import AppProfile


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only UIA capability probe')
    parser.add_argument('--app', required=True, help='approved, running Windows application name')
    args = parser.parse_args()
    profile = AppProfile('probe', windows_app=args.app)
    try:
        inventory = WinAppDiscovery(profile).run()
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({'status': 'unavailable', 'reason': str(exc)}))
        return 1
    counts = Counter(candidate.control_type for candidate in inventory.candidates)
    print(json.dumps({
        'status': 'inspected',
        'controls_with_stable_ids': len(inventory.candidates),
        'examined_elements': inventory.examined_elements,
        'truncated': inventory.truncated,
        'control_types': dict(counts),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
