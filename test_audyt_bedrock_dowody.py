import pytest
from scripts.audyt_bedrock_dowody import collect, logging_status, model_regions

class Fake:
    def __init__(self, region, modes=None, logging=None, project="inherit"):
        self.region=region
        self.modes=modes or {}
        self.logging=logging or {}
        self.project=project
    def get_account_data_retention(self):
        return {"mode":self.modes.get(self.region,"none")}
    def get_model_invocation_logging_configuration(self):
        return self.logging.get(self.region,{})
    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models":[{"modelArn":"arn:aws:bedrock:"+r+"::foundation-model/anthropic.test"} for r in ("eu-central-1","eu-west-1")]}
    def get_project(self, projectIdentifier):
        return {"dataRetention":{"mode":self.project}}
    def get_foundation_model(self, modelIdentifier):
        return {"modelDetails":{"modelArn":"arn:aws:bedrock:"+self.region+"::foundation-model/anthropic.test"}}

def plan(**kwargs):
    return {"inventory_declared_complete":True,"invocations":[dict(label="main",region="eu-central-1",kind="profile",model="eu.anthropic.test",no_project_confirmed=True,**kwargs)]}

def test_all_regions_checked():
    seen=[]
    def factory(region):
        seen.append(region)
        return Fake(region)
    r=collect(plan(),factory)
    assert r["invocations"][0]["status"]=="READ_CHECKS_OK"
    assert set(seen)=={"eu-central-1","eu-west-1"}
    assert r["invocations"][0]["destination_regions"]==["eu-central-1","eu-west-1"]

def test_destination_retention_fails():
    r=collect(plan(),lambda reg:Fake(reg,modes={"eu-west-1":"default"}))
    assert r["invocations"][0]["status"]=="REVIEW_REQUIRED"

def test_project_override_fails():
    r=collect(plan(project="proj_example"),lambda reg:Fake(reg,project="aws_review"))
    assert r["invocations"][0]["effective_mode"]=="aws_review"
    assert r["invocations"][0]["status"]=="REVIEW_REQUIRED"

def test_unknown_scope_fails():
    p=plan()
    del p["invocations"][0]["no_project_confirmed"]
    assert collect(p,Fake)["invocations"][0]["status"]=="REVIEW_REQUIRED"

def test_unknown_logging():
    assert logging_status(None)=="unknown"
    assert logging_status({"loggingConfig":{"s3Config":{}}})=="unknown"
    assert logging_status({"loggingConfig":{"textDataDeliveryEnabled":True}})=="payload_enabled"

def test_malformed_arn():
    assert model_regions({"models":[{"modelArn":"bad"}]}) is None

def test_denied_read_is_not_success():
    class Denied(Fake):
        def get_account_data_retention(self):
            raise PermissionError("private token 123")
    r=collect(plan(),Denied)
    assert r["invocations"][0]["status"]=="REVIEW_REQUIRED"
    assert "private token" not in str(r)

def test_invalid_inventory_before_network():
    p=plan()
    p["invocations"].append(p["invocations"][0].copy())
    with pytest.raises(ValueError):
        collect(p,lambda _:pytest.fail("must not contact AWS"))
