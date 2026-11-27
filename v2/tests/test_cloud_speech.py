"""Speech in the cloud: the recording and the result are deleted whatever happens."""
import json

import pytest

from worker.cloud_speech import CloudSpeech, SpeechError


class S3:
    def __init__(self):
        self.objects, self.deleted = {}, []

    def put_object(self, Bucket, Key, Body, ServerSideEncryption):
        assert ServerSideEncryption == "AES256"
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        return {"Body": type("B", (), {"read": lambda self, data=self.objects[Key]: data})()}

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)


class Transcribe:
    def __init__(self, s3, outcome="COMPLETED", text="Klient przyniesie odpis w piątek.", polls=2):
        self.s3, self.outcome, self.text, self.polls, self.started, self.deleted = s3, outcome, text, polls, None, []

    def start_transcription_job(self, **job):
        self.started = job

    def get_transcription_job(self, TranscriptionJobName):
        self.polls -= 1
        if self.polls > 0:
            return {"TranscriptionJob": {"TranscriptionJobStatus": "IN_PROGRESS"}}
        if self.outcome == "COMPLETED":
            self.s3.objects[self.started["OutputKey"]] = json.dumps(
                {"results": {"transcripts": [{"transcript": self.text}]}}).encode()
        return {"TranscriptionJob": {"TranscriptionJobStatus": self.outcome}}

    def delete_transcription_job(self, TranscriptionJobName):
        self.deleted.append(TranscriptionJobName)


class Account:
    def __init__(self, s3, transcribe):
        self.clients = {"s3": s3, "transcribe": transcribe}
        self.regions = []

    def identity_id(self):
        return "eu-central-1:kancelaria-a"

    def client_factory(self, region):
        self.regions.append(region)
        return self.clients.__getitem__


def test_a_note_is_transcribed_in_polish_in_the_eu_and_nothing_is_left():
    s3 = S3()
    transcribe = Transcribe(s3)
    account = Account(s3, transcribe)
    speech = CloudSpeech(account, "notarai-v2-mowa-1", "eu-central-1", sleep=lambda s: None)
    assert speech.transcribe(b"WEBM", ".webm") == "Klient przyniesie odpis w piątek."
    job = transcribe.started
    assert job["LanguageCode"] == "pl-PL" and job["MediaFormat"] == "webm"
    assert job["Media"]["MediaFileUri"].startswith("s3://notarai-v2-mowa-1/eu-central-1:kancelaria-a/notarai-")
    assert job["OutputKey"].startswith("eu-central-1:kancelaria-a/") and account.regions == ["eu-central-1"]
    assert s3.objects == {} and len(s3.deleted) == 3 and transcribe.deleted == [job["TranscriptionJobName"]]


@pytest.mark.parametrize("outcome", ["FAILED", "CRASH"])
def test_failures_still_clean_up_and_say_so_plainly(outcome):
    s3 = S3()
    transcribe = Transcribe(s3, outcome="FAILED")
    if outcome == "CRASH":
        def crash(**job):
            raise RuntimeError("AccessDenied with internal details")
        transcribe.start_transcription_job = crash
    speech = CloudSpeech(Account(s3, transcribe), "b", "eu-central-1", sleep=lambda s: None)
    with pytest.raises(SpeechError) as error:
        speech.transcribe(b"OGG", ".ogg")
    assert "details" not in str(error.value) and s3.objects == {}
    with pytest.raises(SpeechError):
        speech.transcribe(b"x", ".exe")


def test_the_voice_note_endpoint_uses_the_cloud_when_set(tmp_path):
    import base64

    from fastapi.testclient import TestClient

    from worker.api import create_app
    from worker.init_vault import initialize

    s3 = S3()
    transcribe = Transcribe(s3, text="Notatka z chmury.")
    account = Account(s3, transcribe)
    account.signed_in = True
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    (home / "settings.json").write_text(json.dumps({"speech": {"where": "chmura", "bucket": "notarai-v2-mowa-1"}}))
    import worker.cloud_speech as module
    module.time.sleep = lambda seconds: None
    client = TestClient(create_app(home, account=account))
    result = client.post("/v2/voice", headers=admin, json={"audio_b64": base64.b64encode(b"WEBM").decode(), "case": "s"}).json()
    assert result["text"] == "Notatka z chmury." and len(result["documents"]) == 2 and s3.objects == {}
    (home / "settings.json").write_text(json.dumps({"speech": {"where": "chmura", "bucket": ""}}))
    client = TestClient(create_app(home, account=account))
    result = client.post("/v2/voice", headers=admin, json={"audio_b64": base64.b64encode(b"WEBM").decode(), "case": "s"}).json()
    assert result["text"] is None and "nie jest skonfigurowane" in result["detail"]
