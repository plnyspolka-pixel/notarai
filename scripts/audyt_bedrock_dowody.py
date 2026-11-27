"""Read-only Bedrock audit. Never invokes a model or changes AWS configuration."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

REGION = re.compile(r"[a-z]{2}(?:-[a-z0-9]+)+-\d+")
MODES = {"none", "inherit", "default", "aws_review", "provider_data_share"}
FLAGS = ("textDataDeliveryEnabled", "imageDataDeliveryEnabled",
         "embeddingDataDeliveryEnabled", "videoDataDeliveryEnabled")

def read(client, operation, **kwargs):
    try:
        result = getattr(client, operation)(**kwargs)
        return (result, None) if isinstance(result, dict) else (None, "InvalidResponse")
    except Exception as error:
        # No raw error message, ARN, account ID or secret in the report.
        return None, type(error).__name__

def mode(value):
    return value if isinstance(value, str) and value in MODES else None

def logging_status(response):
    if response is None:
        return "unknown"
    cfg = response.get("loggingConfig", {})
    if not isinstance(cfg, dict):
        return "unknown"
    if any(cfg.get(k) is True for k in FLAGS):
        return "payload_enabled"
    if not cfg:
        return "not_configured"
    if any(k.endswith("DataDeliveryEnabled") and k not in FLAGS and v is not False for k,v in cfg.items()):
        return "unknown"
    return "payload_flags_off" if all(cfg.get(k) is False for k in FLAGS) else "unknown"

def model_regions(response):
    rows = (response or {}).get("models")
    if not isinstance(rows, list) or not rows:
        return None
    regions = set()
    for item in rows:
        arn = item.get("modelArn", "") if isinstance(item, dict) else ""
        parts = arn.split(":", 5) if isinstance(arn, str) else []
        if len(parts) != 6 or parts[0] != "arn" or parts[2] != "bedrock" or not REGION.fullmatch(parts[3]) or not parts[5].startswith("foundation-model/"):
            return None
        regions.add(parts[3])
    return sorted(regions)

def collect(plan, client):
    rows = plan["invocations"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("Invalid invocation inventory")
    labels = set()
    # Validate everything before contacting AWS.
    for row in rows:
        label, region = row["label"], row["region"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", label) or label in labels or not REGION.fullmatch(region):
            raise ValueError("Invalid label or region")
        labels.add(label)
        if row["kind"] not in ("profile", "foundation") or not isinstance(row["model"], str) or not row["model"]:
            raise ValueError("Invalid model")
    regions, results = {}, []
    def check(region):
        if region not in regions:
            c = client(region)
            ret, err = read(c, "get_account_data_retention")
            logs, logerr = read(c, "get_model_invocation_logging_configuration")
            regions[region] = {"account_mode": mode((ret or {}).get("mode")),
                "logging": logging_status(logs), "retention_error": err, "logging_error": logerr}
        return regions[region]
    for row in rows:
        region = row["region"]
        account = check(region)
        c = client(region)
        effective, pm, pe = None, None, None
        if row.get("project"):
            project, pe = read(c, "get_project", projectIdentifier=row["project"])
            data = (project or {}).get("dataRetention")
            pm = mode(data.get("mode")) if isinstance(data, dict) else None
            effective = account["account_mode"] if pm == "inherit" else pm
        elif row.get("no_project_confirmed") is True:
            effective = account["account_mode"]
        if row["kind"] == "profile":
            profile, me = read(c, "get_inference_profile", inferenceProfileIdentifier=row["model"])
            dest = model_regions(profile)
        else:
            model, me = read(c, "get_foundation_model", modelIdentifier=row["model"])
            dest = model_regions({"models": [(model or {}).get("modelDetails", {})]})
        for d in dest or []:
            check(d)
        checks = {"effective_none": effective == "none", "destinations_known": bool(dest),
            "all_logging_off": bool(dest) and all(regions[d]["logging"] in ("not_configured", "payload_flags_off") for d in {region, *dest}),
            "dest_accounts_none": bool(dest) and all(regions[d]["account_mode"] == "none" for d in dest)}
        results.append({"label": row["label"], "source_region": region, "destination_regions": dest,
            "effective_mode": effective, "project_mode": pm, "project_error": pe, "model_error": me,
            "checks": checks, "status": "READ_CHECKS_OK" if all(checks.values()) and not pe and not me else "REVIEW_REQUIRED"})
    return {"observed_at": datetime.now(timezone.utc).isoformat(), "scope": "Control-plane reads only; not certification",
            "inventory_declared_complete": plan.get("inventory_declared_complete") is True,
            "regions": regions, "invocations": results,
            "still_required": ["Verify actual deployed model inventory and fallback paths", "Model-specific contractual terms",
                "Application and agent logs/cache", "Authorized synthetic positive/negative tests", "Independent 3xZero review"],
            "sources": ["https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html",
                "https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html",
                "https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetInferenceProfile.html"]}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--aws-profile")
    a = p.parse_args()
    out = a.out.resolve()
    if out.is_relative_to(Path(__file__).resolve().parents[1]) or out.exists():
        p.error("Use a new private output path outside the repository")
    import boto3
    from botocore.config import Config
    session = boto3.Session(profile_name=a.aws_profile)
    report = collect(json.loads(a.plan.read_text("utf-8")), lambda region: session.client("bedrock", region_name=region,
        config=Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 2})))
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if report["inventory_declared_complete"] and all(row["status"] == "READ_CHECKS_OK" for row in report["invocations"]) else 2

if __name__ == "__main__":
    raise SystemExit(main())
