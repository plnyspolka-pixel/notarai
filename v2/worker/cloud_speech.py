"""Speech to text in the cloud: Amazon Transcribe in eu-central-1, nothing kept afterwards.

Fast path (default): the recording is decoded to plain audio on this computer and streamed straight
to Transcribe in Frankfurt; text comes back in seconds and nothing is written to any bucket. If the
stream cannot be used (old network, firewall without HTTP/2), the slower batch path below is used.

Batch path: the recording is put in a private EU bucket under this office's own prefix, transcribed in
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
    def __init__(self, account, bucket: str, region: str, *, sleep=time.sleep, clock=time.monotonic,
                 streamer=None):
        self._account, self._bucket, self._region = account, bucket, region
        self._sleep, self._clock = sleep, clock
        self._streamer = stream_transcribe if streamer is None else streamer
        self.last_path = None        # "strumien" or "wsadowo": for the status line and tests

    def transcribe(self, audio: bytes, suffix: str) -> str:
        media = FORMATS.get(suffix.lower())
        if media is None:
            raise SpeechError("Tego formatu nagrania nie umiem przepisać.")
        if self._streamer:
            try:
                text = self._streamer(audio, self._account.credentials(), self._region)
                self.last_path = "strumien"
                return text
            except Exception as error:
                if error.__class__.__name__ == "LoginError":
                    raise
                if not self._bucket:
                    raise SpeechError("Nie udało się połączyć z usługą rozpoznawania mowy. Spróbuj ponownie.") from None
        self.last_path = "wsadowo"
        return self._batch(audio, suffix, media)

    def _batch(self, audio: bytes, suffix: str, media: str) -> str:
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
            # Nothing stays behind, even after a failure. Transcribe also leaves an empty
            # write-access check file next to the result.
            for key in (audio_key, text_key, prefix + ".write_access_check_file.temp"):
                try:
                    s3.delete_object(Bucket=self._bucket, Key=key)
                except Exception:
                    pass
            if started:
                try:
                    transcribe.delete_transcription_job(TranscriptionJobName=job)
                except Exception:
                    pass


RATE = 16000
CHUNK = 16000 * 2 // 5        # 200 ms of 16-bit mono audio per event


def to_pcm(audio: bytes) -> bytes:
    """Any common recording -> 16 kHz mono 16-bit PCM, decoded on this computer (PyAV)."""
    import io

    import av

    out = io.BytesIO()
    with av.open(io.BytesIO(audio)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)

        def write(frames):
            for frame in frames:
                out.write(bytes(frame.planes[0])[: frame.samples * 2])
        for frame in container.decode(audio=0):
            write(resampler.resample(frame))
        write(resampler.resample(None))
    return out.getvalue()


def stream_transcribe(audio: bytes, credentials: dict, region: str) -> str:
    """Amazon Transcribe streaming (HTTP/2) in the EU region; returns the final Polish text."""
    import asyncio

    from amazon_transcribe.auth import StaticCredentialResolver
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler

    if not region.startswith("eu-"):
        raise ValueError("EU regions only")
    pcm = to_pcm(audio)
    if not pcm:
        return ""

    class Collect(TranscriptResultStreamHandler):
        def __init__(self, stream):
            super().__init__(stream)
            self.parts = []

        async def handle_transcript_event(self, event):
            for result in event.transcript.results:
                if not result.is_partial and result.alternatives:
                    self.parts.append(result.alternatives[0].transcript)

    async def run() -> str:
        client = TranscribeStreamingClient(region=region, credential_resolver=StaticCredentialResolver(
            access_key_id=credentials["access_key"], secret_access_key=credentials["secret_key"],
            session_token=credentials["token"]))
        stream = await client.start_stream_transcription(
            language_code="pl-PL", media_sample_rate_hz=RATE, media_encoding="pcm")
        collect = Collect(stream.output_stream)

        async def feed():
            for start in range(0, len(pcm), CHUNK):
                await stream.input_stream.send_audio_event(audio_chunk=pcm[start:start + CHUNK])
            await stream.input_stream.end_stream()
        await asyncio.wait_for(asyncio.gather(feed(), collect.handle_events()), timeout=300)
        return " ".join(collect.parts).strip()
    return asyncio.run(run())
