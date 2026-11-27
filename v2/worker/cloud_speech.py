"""Speech to text in the cloud: Amazon Transcribe in eu-central-1, nothing kept afterwards.

The recording is put in a private EU bucket under this office's own prefix, transcribed in
Polish, and the recording, the result file and the transcription job are all deleted as soon as
the text is read back (the bucket also expires anything left over after a day). The office
computer does no speech work and downloads no model. Credentials are the workstation's
hour-long sign-in credentials, limited to this bucket prefix and Transcribe in the EU.
"""
import json
import time
import uuid

FORMATS = {".webm": "webm", ".ogg": "ogg", ".opus": "ogg", ".oga": "ogg", ".m4a": "m4a", ".mp4": "mp4",
           ".mp3": "mp3", ".wav": "wav", ".flac": "flac", ".amr": "amr", ".aac": "m4a", ".3gp": "mp4"}


class SpeechError(Exception):
    """Fixed message, safe to show."""


class CloudSpeech:
    def __init__(self, account, bucket: str, region: str, *, sleep=time.sleep, clock=time.monotonic):
        self._account, self._bucket, self._region = account, bucket, region
        self._sleep, self._clock = sleep, clock

    def transcribe(self, audio: bytes, suffix: str) -> str:
        media = FORMATS.get(suffix.lower())
        if media is None:
            raise SpeechError("Tego formatu nagrania nie umiem przepisać.")
        clients = self._account.client_factory(self._region)
        s3, transcribe = clients("s3"), clients("transcribe")
        prefix = self._account.identity_id() + "/"
        job = "notarai-" + uuid.uuid4().hex
        audio_key, text_key = prefix + job + suffix.lower(), prefix + job + ".json"
        started = False
        try:
            s3.put_object(Bucket=self._bucket, Key=audio_key, Body=audio, ServerSideEncryption="AES256")
            transcribe.start_transcription_job(
                TranscriptionJobName=job, LanguageCode="pl-PL", MediaFormat=media,
                Media={"MediaFileUri": f"s3://{self._bucket}/{audio_key}"},
                OutputBucketName=self._bucket, OutputKey=text_key,
            )
            started = True
            deadline, wait = self._clock() + 900, 1.5
            while True:
                status = transcribe.get_transcription_job(TranscriptionJobName=job)["TranscriptionJob"]
                state = status["TranscriptionJobStatus"]
                if state == "COMPLETED":
                    break
                if state == "FAILED" or self._clock() > deadline:
                    raise SpeechError("Usługa rozpoznawania mowy nie przepisała nagrania.")
                self._sleep(wait)
                wait = min(wait * 1.5, 5)
            result = json.loads(s3.get_object(Bucket=self._bucket, Key=text_key)["Body"].read())
            return " ".join(t["transcript"] for t in result["results"]["transcripts"]).strip()
        except SpeechError:
            raise
        except Exception as error:
            if error.__class__.__name__ == "LoginError":
                raise
            raise SpeechError("Nie udało się połączyć z usługą rozpoznawania mowy. Spróbuj ponownie.") from None
        finally:
            for key in (audio_key, text_key):           # nothing stays behind, even after a failure
                try:
                    s3.delete_object(Bucket=self._bucket, Key=key)
                except Exception:
                    pass
            if started:
                try:
                    transcribe.delete_transcription_job(TranscriptionJobName=job)
                except Exception:
                    pass
