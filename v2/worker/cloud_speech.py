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


# ---------------------------------------------------------------- live dictation
class Dictation:
    """One live dictation: 16 kHz PCM pieces in, text out while the notary speaks.

    `stream(chunks, on_text)` runs the speech service: it reads PCM pieces from the iterator-like
    `chunks.get()` (None ends) and calls `on_text(final_parts, partial)` as results arrive. Nothing
    is stored: the audio goes straight to the EU service and only the text comes back.
    """

    def __init__(self, stream, *, clock=time.monotonic, max_seconds=600):
        import queue
        import threading

        self._queue: "queue.Queue[bytes | None]" = queue.Queue(maxsize=400)
        self._finals: list[str] = []
        self._partial = ""
        self._lock = threading.Lock()
        self._clock = clock
        self.started = self.touched = clock()
        self.max_seconds = max_seconds
        self.done = threading.Event()
        self.error: str | None = None
        self.cause: str | None = None             # the error's type only, for diagnostics (never content)
        self.login_needed = False
        self.audio = bytearray()                  # kept for the second way if the stream fails

        def run():
            try:
                stream(self, self._update)
            except Exception as error:
                import sys

                self.cause = error.__class__.__name__
                print(f"dyktowanie: strumien nie dziala ({self.cause})", file=sys.stderr, flush=True)
                if self.cause == "LoginError":
                    self.login_needed = True
                    self.error = "Zaloguj stanowisko kontem NotarAI (napisz „zaloguj”), żeby dyktować przez Frankfurt."
                else:
                    self.error = ("Szybkie dyktowanie nie łączy się z Frankfurtem. Mów dalej: po ■ przepiszę całe "
                                  "nagranie drugą drogą (wolniej). Szczegóły: napisz „sprawdź mowę”.")
            finally:
                self.done.set()
        threading.Thread(target=run, daemon=True, name="notarai-dyktowanie").start()

    # the speech side reads with get()
    def get(self, timeout: float = 15.0):
        import queue

        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None                         # nothing for a while: end the stream

    def _update(self, finals: list[str], partial: str) -> None:
        with self._lock:
            self._finals, self._partial = list(finals), partial

    # the window side
    def feed(self, pcm: bytes) -> None:
        self.touched = self._clock()
        if len(self.audio) < 16000 * 2 * 600:
            self.audio += pcm
        if self.done.is_set():
            return
        if self._clock() - self.started > self.max_seconds:
            self.finish()
            return
        try:
            self._queue.put_nowait(pcm)
        except Exception:
            pass                                # the service is behind: drop a piece rather than block

    def finish(self) -> None:
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

    def text(self) -> str:
        with self._lock:
            return " ".join([*self._finals, self._partial]).strip()


def transcribe_stream(credentials_source, region: str):
    """A `stream` for Dictation: Amazon Transcribe streaming in the EU region, Polish, with partial results."""
    if not region.startswith("eu-"):
        raise ValueError("EU regions only")

    def stream(source, on_text):
        import asyncio

        from amazon_transcribe.auth import StaticCredentialResolver
        from amazon_transcribe.client import TranscribeStreamingClient
        from amazon_transcribe.handlers import TranscriptResultStreamHandler

        credentials = credentials_source()

        class Live(TranscriptResultStreamHandler):
            def __init__(self, output):
                super().__init__(output)
                self.finals = []

            async def handle_transcript_event(self, event):
                partial = ""
                for result in event.transcript.results:
                    if not result.alternatives:
                        continue
                    if result.is_partial:
                        partial = result.alternatives[0].transcript
                    else:
                        self.finals.append(result.alternatives[0].transcript)
                on_text(self.finals, partial)

        async def run():
            client = TranscribeStreamingClient(region=region, credential_resolver=StaticCredentialResolver(
                access_key_id=credentials["access_key"], secret_access_key=credentials["secret_key"],
                session_token=credentials["token"]))
            started = await client.start_stream_transcription(
                language_code="pl-PL", media_sample_rate_hz=RATE, media_encoding="pcm",
                enable_partial_results_stabilization=True, partial_results_stability="high")
            handler = Live(started.output_stream)

            async def pump():
                loop = asyncio.get_running_loop()
                while True:
                    piece = await loop.run_in_executor(None, source.get)
                    if piece is None:
                        break
                    await started.input_stream.send_audio_event(audio_chunk=piece)
                await started.input_stream.end_stream()
            await asyncio.gather(pump(), handler.handle_events())
        asyncio.run(run())
    return stream


def wav(pcm: bytes) -> bytes:
    import io
    import wave

    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(bytes(pcm))
    return out.getvalue()
