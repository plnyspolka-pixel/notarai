"""Cognito-bound tenant control APIs for Virtual Employee.

Fail closed when service is unprovisioned. Only metadata is returned by list;
result content is retrieved separately after authentication and role checks.
Worker access is via SQS/IAM, never this user-facing API.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .jobs import JobConflict, JobControl, JobMissing, TenantIdentity
from .payloads import EncryptedPayloadStore

router = APIRouter(prefix="/api/virtual-employee", tags=["virtual-employee"])
page_router = APIRouter()


class CreateJobBody(BaseModel):
    app_id: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    action: str = Field(pattern=r"^(read_field|fill_draft_field)$")
    field: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    value: str | None = Field(default=None, max_length=2000)


class KillSwitchBody(BaseModel):
    disabled: bool


@page_router.get("/virtual-employee", response_class=HTMLResponse)
def console_page():
    return (Path(__file__).resolve().parent.parent /
            "static" / "virtual_employee.html").read_text("utf-8")


def _caller(request: Request) -> TenantIdentity:
    import autoryzacja
    if (not autoryzacja.MULTI or
            os.getenv("PIECZAPP_VIRTUAL_EMPLOYEE_ENABLED", "false").lower() != "true"):
        raise HTTPException(503, "Wirtualny pracownik nie jest jeszcze wlaczony.")
    state = request.state
    tenant = getattr(state, "kancelaria", "")
    email = getattr(state, "email", "")
    if not tenant or not email or getattr(state, "serwis", False) or getattr(state, "komputer", None):
        raise HTTPException(403, "Wymagane osobiste logowanie pracownika kancelarii.")
    person = autoryzacja._osoba_w_kancelarii(tenant, email) or {}
    import stanowiska
    permissions = stanowiska.uprawnienia(person)
    if "sprawy_ai" not in permissions:
        raise HTTPException(403, "Brak uprawnien do obslugi spraw.")
    can_approve = (person.get("rola") == "wlasciciel"
                   or person.get("stanowisko") == "notariusz")
    return TenantIdentity(tenant, email, can_approve)


def _service(tenant: str) -> JobControl:
    """No tenant config or AWS credentials supplied from browser or model."""
    for key in ("NOTARAI_VE_JOBS_TABLE", "NOTARAI_VE_TENANTS_TABLE",
                "NOTARAI_VE_PAYLOAD_BUCKET", "NOTARAI_VE_SETTINGS_TABLE"):
        if not os.getenv(key):
            raise HTTPException(503, "Brak konfiguracji centrum zadan.")
    import boto3
    dynamo = boto3.resource("dynamodb", region_name="eu-central-1")
    config = dynamo.Table(os.environ["NOTARAI_VE_TENANTS_TABLE"]).get_item(
        Key={"tenant_id": tenant}, ConsistentRead=True).get("Item")
    if not config or not config.get("enabled", False):
        raise HTTPException(503, "Brak aktywnego stanowiska kancelarii.")
    if not config.get("queue_url") or not config.get("kms_key_id") or not config.get("control_role_arn"):
        raise HTTPException(503, "Stanowisko nie ma kompletnych uprawnien.")
    assumed = boto3.client("sts", region_name="eu-central-1").assume_role(
        RoleArn=config["control_role_arn"], RoleSessionName="notarai-ve-controller",
        Tags=[{"Key": "TenantId", "Value": tenant}], DurationSeconds=900,
    )["Credentials"]
    session = boto3.Session(
        aws_access_key_id=assumed["AccessKeyId"],
        aws_secret_access_key=assumed["SecretAccessKey"],
        aws_session_token=assumed["SessionToken"],
        region_name="eu-central-1",
    )
    store = EncryptedPayloadStore(
        s3=session.client("s3"),
        bucket=os.environ["NOTARAI_VE_PAYLOAD_BUCKET"],
        tenant_id=tenant, kms_key_id=config["kms_key_id"],
    )
    return JobControl(
        table=session.resource("dynamodb").Table(os.environ["NOTARAI_VE_JOBS_TABLE"]),
        settings_table=session.resource("dynamodb").Table(os.environ["NOTARAI_VE_SETTINGS_TABLE"]),
        sqs=session.client("sqs"),
        payloads=store,
        queue_resolver=lambda scoped_tenant: (
            config["queue_url"] if scoped_tenant == tenant else None),
    )


def _translate(fn):
    try:
        return fn()
    except JobMissing:
        raise HTTPException(404, "Zadania nie znaleziono.") from None
    except JobConflict:
        raise HTTPException(409, "Stan zadania ulegl zmianie. Odswiez konsolę.") from None
    except PermissionError:
        raise HTTPException(403, "Brak uprawnien.") from None
    except ValueError:
        raise HTTPException(422, "Niepoprawna operacja.") from None


@router.get("/jobs")
def list_jobs(request: Request):
    caller = _caller(request)
    service = _service(caller.tenant_id)
    return {"jobs": _translate(lambda: service.list(caller))}


@router.post("/jobs", status_code=202)
def new_job(request: Request, body: CreateJobBody):
    caller = _caller(request)
    service = _service(caller.tenant_id)
    return _translate(lambda: service.create(
        caller, app_id=body.app_id, action=body.action,
        field=body.field, value=body.value))


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str):
    caller = _caller(request)
    return _translate(lambda: _service(caller.tenant_id).get(caller, job_id))


@router.post("/jobs/{job_id}/approve")
def approve_job(request: Request, job_id: str):
    caller = _caller(request)
    return _translate(lambda: _service(caller.tenant_id).approve(caller, job_id))


@router.post("/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: str):
    caller = _caller(request)
    return _translate(lambda: _service(caller.tenant_id).cancel(caller, job_id))


@router.get("/jobs/{job_id}/result")
def job_result(request: Request, job_id: str):
    caller = _caller(request)
    return {"result": _translate(lambda: _service(caller.tenant_id).result(caller, job_id))}


@router.get("/worker/status")
def worker_status(request: Request):
    caller = _caller(request)
    svc = _service(caller.tenant_id)
    return {"disabled": svc.kill_switch(bound_tenant=caller.tenant_id)}


@router.put("/worker/status")
def change_worker_status(request: Request, body: KillSwitchBody):
    caller = _caller(request)
    service = _service(caller.tenant_id)
    _translate(lambda: service.set_kill_switch(caller, disabled=body.disabled))
    return {"disabled": body.disabled}
