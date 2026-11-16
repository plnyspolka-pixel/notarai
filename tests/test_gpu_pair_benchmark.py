"""Pair comparison tests never call GPU network or load model weights."""
from unittest.mock import patch
import pytest

from tools.agent_factory.gpu_pair_benchmark import (
    parse_endpoint, run, REQUIRED_CONFIRM, inference
)
from tools.agent_factory.worker_pool import WorkerPolicyError


def env():
    return {
        "AGENT_GPU_14B_ENDPOINT":"https://model14.example.net/v1",
        "AGENT_GPU_14B_TOKEN":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "AGENT_GPU_14B_MODEL":"qwen2.5-coder-14b-instruct",
        "AGENT_GPU_32B_ENDPOINT":"https://model32.example.net/v1",
        "AGENT_GPU_32B_TOKEN":"yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
        "AGENT_GPU_32B_MODEL":"qwen2.5-coder-32b-instruct",
        "AGENT_GPU_ALLOWED_HOSTS":"model14.example.net,model32.example.net",
    }


def test_parse_two_separate_tls_endpoints_with_explicit_allowlist():
    a=parse_endpoint("14B",env())
    b=parse_endpoint("32B",env())
    assert a.host=="model14.example.net" and b.host=="model32.example.net"
    assert a.url=="https://model14.example.net/v1/chat/completions"
    assert "xxxxxxxx" not in a.url
    assert b.model=="qwen2.5-coder-32b-instruct"


@pytest.mark.parametrize("url",[
    "http://model14.example.net/v1",
    "https://127.0.0.1/v1",
    "https://localhost/v1",
    "https://model14.example.net/v1?secret=aaa",
    "https://bad:secret@model14.example.net/v1",
    "https://model14.example.net/redirect",
    "https://169.254.169.254/v1",
    "https://model14.example.net.evil.net/v1",
])
def test_refuses_unsafe_or_unknown_endpoints(url):
    values=env()
    values["AGENT_GPU_14B_ENDPOINT"]=url
    with pytest.raises(WorkerPolicyError):
        parse_endpoint("14B",values)


def test_refuses_missing_key_or_unapproved_auth_type():
    values=env()
    values["AGENT_GPU_32B_TOKEN"]=""
    with pytest.raises(WorkerPolicyError):
        parse_endpoint("32B",values)
    values=env()
    values["AGENT_GPU_32B_AUTH_HEADER"]="X-Random-Token"
    with pytest.raises(WorkerPolicyError):
        parse_endpoint("32B",values)


def test_missing_manual_approval_prevents_all_model_calls(monkeypatch,tmp_path):
    with patch.dict("os.environ",env(),clear=True):
        with pytest.raises(WorkerPolicyError):
            run(image="python@sha256:"+"a"*64,output=tmp_path/"experiment")


def test_even_with_approval_refuses_non_disposable_runner(monkeypatch,tmp_path):
    values=env()
    values["AGENT_GPU_PAIR_APPROVAL"]=REQUIRED_CONFIRM
    with patch.dict("os.environ",values,clear=True):
        with pytest.raises(WorkerPolicyError):
            run(image="python@sha256:"+"a"*64,output=tmp_path/"experiment")
