import hashlib
import hmac
import json

import pytest

from computer_use.fallback_router import AutomationResponse, Outcome
from computer_use.profiles import AppProfile, Element
from computer_use.workflows import WorkflowRunner, load_signed_skill

KEY=b'k'*32


def signed(tenant='office_1', app='office_app', steps=None):
    if steps is None:
        steps=[
            {'action':'navigate_to','field':'cases_tab','expected_field':'search_field'},
            {'action':'read_field','field':'search_field'},
        ]
    data={'tenant_id':tenant,'app_id':app,'skill_id':'find_case',
          'revision':1,'steps':steps}
    raw=json.dumps(data,sort_keys=True).encode()
    return raw,hmac.new(KEY,raw,hashlib.sha256).hexdigest()


def profile():
    return AppProfile('office_app',windows_app='notepad',fields={
        'cases_tab':Element('uia','CasesTab',allow_navigation=True),
        'search_field':Element('uia','SearchBox'),
    })


class Worker:
    def __init__(self, outcomes=None):
        self.outcomes=outcomes or [
            AutomationResponse(Outcome.COMPLETED,strategy='windows_uia',
                               data={'target':'cases_tab'}),
            AutomationResponse(Outcome.COMPLETED,strategy='windows_uia',
                               data={'field':'search_field','value':'TEST'}),
        ]
        self.requests=[]
    def execute_sequence(self,requests,**kw):
        self.requests=list(requests)
        return tuple(self.outcomes)


def test_load_and_run_multistep_signed_skill():
    raw,sig=signed()
    skill=load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')
    worker=Worker()
    result=WorkflowRunner(worker=worker,bound_tenant='office_1',app_profile=profile()).run(
        job_id='task_1',skill=skill)
    assert result.outcome is Outcome.COMPLETED
    assert result.steps_completed==2
    assert worker.requests[0].action=='navigate_to'
    assert worker.requests[0].payload['expected_field']=='search_field'
    assert result.results['search_field']['value']=='TEST'


def test_reject_modified_skill_and_cross_tenant():
    raw,sig=signed()
    with pytest.raises(ValueError):
        load_signed_skill(raw+b' ',sig,KEY,bound_tenant='office_1',bound_app='office_app')
    with pytest.raises(ValueError,match='outside_tenant'):
        load_signed_skill(raw,sig,KEY,bound_tenant='office_2',bound_app='office_app')


def test_reject_unsafe_steps_and_unbounded_loop():
    for steps in [[{'action':'send','field':'cases_tab'}],
                  [{'action':'navigate_to','field':'cases_tab'}],
                  [{'action':'read_field','field':'search_field'}]*13]:
        raw,sig=signed(steps=steps)
        with pytest.raises(ValueError):
            load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')


def test_partial_after_navigation_requires_reconciliation():
    raw,sig=signed()
    skill=load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')
    w=Worker([
        AutomationResponse(Outcome.COMPLETED),
        AutomationResponse(Outcome.UNSUPPORTED),
    ])
    result=WorkflowRunner(worker=w,bound_tenant='office_1',app_profile=profile()).run(
        job_id='task_1',skill=skill)
    assert result.outcome is Outcome.NEEDS_RECONCILIATION


def test_unapproved_fields_do_not_reach_execution():
    raw,sig=signed(steps=[{'action':'read_field','field':'secret_admin_field'}])
    skill=load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')
    w=Worker()
    result=WorkflowRunner(worker=w,bound_tenant='office_1',app_profile=profile()).run(
        job_id='task_1',skill=skill)
    assert result.outcome is Outcome.DENIED
    assert not w.requests


def test_workflow_cannot_be_replayed_for_different_app():
    raw,sig=signed()
    skill=load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')
    p=AppProfile('other',windows_app='notepad')
    result=WorkflowRunner(worker=Worker(),bound_tenant='office_1',app_profile=p).run(
        job_id='task_1',skill=skill)
    assert result.outcome is Outcome.DENIED


def test_draft_inputs_bound_from_request_not_from_skill():
    raw,sig=signed(steps=[
        {'action':'fill_draft_field','field':'search_field','value_from':'case_number'}
    ])
    skill=load_signed_skill(raw,sig,KEY,bound_tenant='office_1',bound_app='office_app')
    w=Worker([AutomationResponse(Outcome.COMPLETED)])
    res=WorkflowRunner(worker=w,bound_tenant='office_1',app_profile=profile()).run(
        job_id='task_1',skill=skill,input_values={'case_number':'FIKCYJNE'})
    assert res.outcome is Outcome.COMPLETED
    assert w.requests[0].payload['value']=='FIKCYJNE'
