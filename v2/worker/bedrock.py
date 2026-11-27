"""Synthetic-only Bedrock smoke test. No vault access, no cloud state."""
import os

from .policy import Policy, PolicyError



def smoke_test(client_factory=None):
    if os.environ.get("NOTARAI_V2_BEDROCK_SYNTHETIC") != "1":
        raise PermissionError("Bedrock disabled")
    region = os.environ.get("NOTARAI_V2_BEDROCK_REGION", "eu-central-1")
    model = os.environ.get("NOTARAI_V2_BEDROCK_MODEL", "")
    try:
        policy = Policy(region, model)
    except PolicyError:
        raise ValueError("Configure an approved EU model or eu. inference profile") from None
    if client_factory is None:
        import boto3
        client_factory = boto3.client
    policy.verify(client_factory("bedrock", region_name=region))
    runtime = client_factory("bedrock-runtime", region_name=region)
    result = runtime.converse(modelId=model, messages=[{"role":"user","content":[{"text":"Synthetic test only. Reply with OK."}]}], inferenceConfig={"maxTokens":32})
    return {"ok": True, "model": model, "region": region, "stop_reason": result.get("stopReason")}
