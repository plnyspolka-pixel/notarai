"""A standard interactive user's synthetic service-status probe."""
import sys


def main():
    if sys.platform != "win32":
        raise SystemExit("This command requires Windows.")
    import pywintypes

    from .windows_ipc import PIPE_NAME, local_service_sid, probe, process_identity

    _, session, elevated = process_identity()
    if session == 0 or elevated:
        raise SystemExit("Use a non-elevated interactive Windows session.")
    try:
        probe(PIPE_NAME, local_service_sid())
    except (pywintypes.error, PermissionError, TimeoutError, ValueError):
        raise SystemExit("V2 status service is unavailable for this session.") from None
    print("V2 local status protocol v1 verified.")


if __name__ == "__main__":
    main()
