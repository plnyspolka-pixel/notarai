"""No AWS access required. Exercises DDB conditional claims and SQS recovery."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from computer_use.daemon import QueueConsumer
from computer_use.jobs import JobControl, JobConflict, JobMissing, TenantIdentity
from computer_use.fallback_router import AutomationResponse, Outcome


class FakeTable:
    def __init__(self):
        self.items = {}
    def get_item(self, Key, **kwargs):
        value = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": deepcopy(value)} if value else {}
    def put_item(self, Item, **kwargs):
        key = (Item["PK"], Item["SK"])
        if key in self.items:
            raise RuntimeError("conditional")
        self.items[key] = deepcopy(Item)
    def query(self, **kw):
        pk = kw["ExpressionAttributeValues"][":pk"]
        return {"Items": [deepcopy(v) for (p,k),v in self.items.items() if p==pk and k.startswith("JOB#")]}
    def update_item(self, Key, **kwargs):
        k=(Key["PK"],Key["SK"])
        x=self.items.setdefault(k, {"PK": k[0], "SK": k[1]})
        vals=kw["ExpressionAttributeValues"]
        cond=kw.get("ConditionExpression", "")
        if ":expected" in vals and (x.get("status") != vals[":expected"] or x.get("version")!=vals[":version"]):
            raise RuntimeError("conditional")
        if ":queued" in vals and (x.get("status") != vals[":queued"] or x.get("version")!=vals[":version"]):
            raise RuntimeError("conditional")
        if ":running" in vals and (x.get("status")!=vals[":running"] or x.get("worker_id")!=vals[":worker"]):
            raise RuntimeError("conditional")
        mapping={":new":"status",":cancelled":"status",":now":"updated_at",
                 ":expiry":"approval_expires",":w":"worker_id",":lease":"lease_until",
                 ":yes":"cancellation_requested",":ref":"result_ref",
                 ":strategy":"last_strategy",":reason":"reason",":disabled":"disabled"}
        for placeholder,field in mapping.items():
            if placeholder in vals:
                x[field]=vals[placeholder]
        if ":one" in vals:
            x["version"]=x.get("version",0)+vals[":one"]


class FakeSQS:
    def __init__(self):
        self.queue=[]
        self.deleted=[]
    def send_message(self,**kwargs):
        self.queue.append(kwargs)
    def receive_message(self,**kwargs):
        if not self.queue:
            return {}
        return {"Messages":[{"Body":self.queue[0]["MessageBody"],"ReceiptHandle":"receipt"}]}
    def delete_message(self,**kwargs):
        self.deleted.append(kwargs)
        self.queue.pop(0)


class FakePayloads:
    def __init__(self):
        self.data={}
    def write(self,tenant,job,part,data):
        self.data[(tenant,job,part)]=data
        return "a"*64
    def read(self,tenant,job,part,ref):
        assert ref=="a"*64
        return self.data[(tenant,job,part)]


def setup():
    table, settings, sqs, payloads = FakeTable(),FakeTable(),FakeSQS(),FakePayloads()
    control=JobControl(table=table,settings_table=settings,sqs=sqs,payloads=payloads,
                       queue_resolver=lambda tenant: "https://sqs.example.test/"+tenant,
                       clock=lambda:100000)
    return control,table,settings,sqs,payloads


def user(tenant="office_1",approve=False):
    return TenantIdentity(tenant,"user@office.test",approve)


def test_job_is_tenant_scoped_and_queue_carries_no_pii():
    svc, table, settings,sqs,store=setup()
    item=svc.create(user(),app_id="generic_app",action="fill_draft_field",
                    field="rep_number",value="FIKCYJNA TRESC")
    key=("TENANT#office_1","JOB#"+item["job_id"])
    assert "FIKCYJNA TRESC" not in json.dumps(table.items[key])
    assert sqs.queue==[]
    assert store.data[("office_1",item["job_id"],"input")]["value"]=="FIKCYJNA TRESC"


def test_readonly_job_can_be_enqueued():
    svc, table,settings,sqs,store=setup()
    item=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    assert item["status"]=="queued"
    assert item["job_id"] in sqs.queue[0]["MessageBody"]
    assert "rep_number" not in sqs.queue[0]["MessageBody"]


def test_cross_tenant_job_not_visible():
    svc,*_=setup()
    x=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    with pytest.raises(JobMissing):
        svc.get(user("office_2"),x["job_id"])
    assert svc.list(user("office_2"))==[]


def test_draft_approval_requires_notarial_role():
    svc,*_=setup()
    x=svc.create(user(),app_id="generic_app",action="fill_draft_field",
                 field="rep_number",value="TEST")
    with pytest.raises(PermissionError):
        svc.approve(user(),x["job_id"])
    assert svc.approve(user(approve=True),x["job_id"])["status"]=="queued"


def test_cancel_pending_job_prevents_claim():
    svc,*_=setup()
    x=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    assert svc.cancel(user(),x["job_id"])["status"]=="cancelled"
    with pytest.raises(JobConflict):
        svc.claim(bound_tenant="office_1",job_id=x["job_id"],worker_id="robot_1")


def test_atomic_claim_no_duplicate_execution():
    svc,*_=setup()
    x=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    svc.claim(bound_tenant="office_1",job_id=x["job_id"],worker_id="robot_1")
    with pytest.raises(JobConflict):
        svc.claim(bound_tenant="office_1",job_id=x["job_id"],worker_id="robot_2")


def test_job_result_never_in_dynamodb():
    svc,table,_,_,payloads=setup()
    x=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    svc.claim(bound_tenant="office_1",job_id=x["job_id"],worker_id="robot_1")
    result={"field":"rep_number","value":"FIKCYJNE TAJNE DANE"}
    svc.finish(bound_tenant="office_1",job_id=x["job_id"],worker_id="robot_1",
               outcome="completed",strategy="windows_uia",result=result)
    assert svc.result(user(),x["job_id"])==result
    assert "FIKCYJNE TAJNE DANE" not in json.dumps(table.items)


def test_kill_switch_default_denied_and_worker_cannot_clear_via_jobs():
    svc,table,settings,_,_=setup()
    assert svc.kill_switch(bound_tenant="office_1") is True
    with pytest.raises(PermissionError):
        svc.set_kill_switch(user(),disabled=False)
    svc.set_kill_switch(user(approve=True),disabled=False)
    assert svc.kill_switch(bound_tenant="office_1") is False
    assert ("TENANT#office_1","CONFIG#WORKER") not in table.items
    assert ("TENANT#office_1","CONFIG#WORKER") in settings.items


class FakeWorker:
    def __init__(self):
        self.calls=0
    def execute(self,request):
        self.calls+=1
        return AutomationResponse(Outcome.COMPLETED,strategy="windows_uia",
                                  data={"field":"rep_number","value":"TEST"})


def test_consumer_only_executes_bound_tenant_once():
    svc,table,settings,sqs,payloads=setup()
    svc.set_kill_switch(user(approve=True),disabled=False)
    item=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    worker=FakeWorker()
    consumer=QueueConsumer(bound_tenant="office_1",worker_id="robot_1",
                           queue_url="https://sqs.example.test/office_1",sqs=sqs,
                           control=svc,worker=worker)
    assert consumer.poll_once()=="completed"
    assert worker.calls==1
    assert svc.get(user(),item["job_id"])["status"]=="completed"
    assert consumer.poll_once()=="idle"


def test_consumer_respects_switch_without_claiming():
    svc,_,_,sqs,_=setup()
    svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    worker=FakeWorker()
    consumer=QueueConsumer(bound_tenant="office_1",worker_id="robot_1",
                           queue_url="https://sqs.example.test/office_1",sqs=sqs,
                           control=svc,worker=worker)
    assert consumer.poll_once()=="disabled"
    assert worker.calls==0
    assert len(sqs.queue)==1


def test_consumer_recovers_duplicate_without_rerun():
    svc,_,_,sqs,_=setup()
    svc.set_kill_switch(user(approve=True),disabled=False)
    item=svc.create(user(),app_id="generic_app",action="read_field",field="rep_number")
    svc.claim(bound_tenant="office_1",job_id=item["job_id"],worker_id="robot_1")
    worker=FakeWorker()
    consumer=QueueConsumer(bound_tenant="office_1",worker_id="robot_2",
                           queue_url="https://sqs.example.test/office_1",sqs=sqs,
                           control=svc,worker=worker)
    assert consumer.poll_once()=="already_claimed_or_cancelled"
    assert worker.calls==0


def test_approval_preview_requires_notary_and_returns_exact_tenant_field():
    svc, table, settings, sqs, store = setup()
    item = svc.create(user(), app_id="generic_app", action="fill_draft_field",
                      field="rep_number", value="DANE FIKCYJNE DO POTWIERDZENIA")
    with pytest.raises(PermissionError):
        svc.approval_preview(user(), item["job_id"])
    preview = svc.approval_preview(user(approve=True), item["job_id"])
    assert preview["field"] == "rep_number"
    assert preview["value"] == "DANE FIKCYJNE DO POTWIERDZENIA"
    assert "DANE FIKCYJNE" not in json.dumps(table.items)
    with pytest.raises(JobMissing):
        svc.approval_preview(user("office_2", approve=True), item["job_id"])


def test_expired_running_lease_never_requeued_automatically():
    svc, table, settings, sqs, store = setup()
    item = svc.create(user(), app_id="generic_app",
                      action="read_field", field="rep_number")
    svc.claim(bound_tenant="office_1", job_id=item["job_id"], worker_id="robot_1")
    with pytest.raises(PermissionError):
        svc.reconcile_expired(user(), item["job_id"])
    with pytest.raises(JobConflict):
        svc.reconcile_expired(user(approve=True), item["job_id"])
    svc.clock = lambda: 1001000
    reconciled = svc.reconcile_expired(user(approve=True), item["job_id"])
    assert reconciled["status"] == "needs_reconciliation"
    with pytest.raises(JobConflict):
        svc.claim(bound_tenant="office_1", job_id=item["job_id"],
                  worker_id="robot_2")
