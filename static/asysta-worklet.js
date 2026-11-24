/* AudioWorklet: microphone -> mono PCM signed 16-bit 16 kHz, no local recording. */
class NotaraiPcm extends AudioWorkletProcessor {
  constructor() {
    super();
    this.phase = 0;
    this.sum = 0;
    this.count = 0;
    this.samples = new Int16Array(1600); // one 100 ms packet
    this.used = 0;
    this.running = true;
    this.port.onmessage = event => {
      if (event.data === "stop") this.running = false;
    };
  }
  process(inputs) {
    if (!this.running) return false;
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (let i = 0; i < input.length; i++) {
      this.sum += input[i];
      this.count++;
      this.phase += 16000;
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate;
        const averaged = this.sum / Math.max(1, this.count);
        const clipped = Math.min(1, Math.max(-1, averaged));
        this.samples[this.used++] = clipped < 0 ? Math.round(clipped * 32768) : Math.round(clipped * 32767);
        this.sum = 0;
        this.count = 0;
        if (this.used === this.samples.length) {
          this.port.postMessage(this.samples.buffer, [this.samples.buffer]);
          this.samples = new Int16Array(1600);
          this.used = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("notarai-pcm", NotaraiPcm);
