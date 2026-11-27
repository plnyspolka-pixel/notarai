"""Synthetic-only Bedrock smoke test. No vault access, no cloud state."""
import os

REGIONS = {"eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2", "eu-central-2"}

def smoke_test(client_factory=None):
    if os.environ.get("NOTARAI_V2_BEDROCK_SYNTHETIC") != "1":
        raise PermissionError("Bedrock disabled")
    region = os.environ.get("NOTARAI_V2_BEDROCK_REGION", "eu-central-1")
    model = os.environ.get("NOTARAI_V2_BEDROCK_MODEL", "")
    # Reject inference profiles, ARNs and provisioned endpoints at this stage.
    if region not in REGIONS or not model.startswith(("anthropic.", "amazon.", "meta.", "mistral.", "cohere.")) or "/" in model or ":" in model.split(".",1)[0]:
        raise ValueError("Configure an approved direct EU foundation model")
    if client_factory is None:
        import boto3
        client_factory = boto3.client
    control = client_factory("bedrock", region_name=region)
    config = control.get_model_invocation_logging_configuration().get("loggingConfig") or {}
    if config:
        raise PermissionError("Invocation logging must be removed for this prototype")
    runtime = client_factory("bedrock-runtime", region_name=region)
    result = runtime.converse(modelId=model, messages=[{"role":"user","content":[{"text":"Synthetic test only. Reply with OK."}]}], inferenceConfig={"maxTokens":32})
    return {"ok": True, "model": model, "region": region, "stop_reason": result.get("stopReason")}
