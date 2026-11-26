"""Operator-only structural inspection of one synthetic DOCX revision."""
import argparse
import json
import sqlite3
from uuid import UUID

from pydantic import ValidationError

from .connect import State
from .connect_sdk import ConnectSession, InspectDocx, LocalReceipts, RevisionTarget
from .docx_adapter import DOCX_APP, OpenXmlDocx
from .init_vault import home_path
from .local_secrets import read_secret
from .vault import Vault


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document_id", type=UUID)
    parser.add_argument("version", type=int)
    parser.add_argument(
        "--synthetic-only", action="store_true", required=True,
        help="attest that this workspace contains only synthetic documents",
    )
    parser.add_argument(
        "--approve", action="store_true", required=True,
        help="approve inspecting exactly the supplied document and revision",
    )
    args = parser.parse_args()
    try:
        request = InspectDocx(
            app=DOCX_APP, target=RevisionTarget(document_id=args.document_id, version=args.version)
        )
    except ValidationError:
        parser.error("version must be a positive SQLite revision number")

    try:
        home = home_path()
        vault = Vault(home, read_secret(home, "vault.key"))
        session = ConnectSession(
            [OpenXmlDocx(vault)], {DOCX_APP: frozenset({"inspect_docx"})}, LocalReceipts(home)
        )
        result = session.execute(request, session.approve(request))
    except (KeyError, OSError, ValueError, sqlite3.Error):
        parser.exit(1, "Unable to open the synthetic V2 workspace or write a local receipt.\n")

    output = {"state": result.state.value, "backend": result.backend}
    if result.state is State.VERIFIED:
        output["data"] = result.data.model_dump(mode="json")
    print(json.dumps(output))
    return 0 if result.state is State.VERIFIED else 1


if __name__ == "__main__":
    raise SystemExit(main())
