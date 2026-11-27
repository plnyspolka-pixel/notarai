"use strict";
// Device side of the NotarAI tunnel (see tunnel.py for the protocol). The signing key is
// generated here as non-extractable and kept in IndexedDB: it can be used, never read.

const NotaraiTunnel = (() => {
  const LABEL = new TextEncoder().encode("notarai-tunnel-v1");
  const CHUNK = 16 * 1024;
  const DB = "notarai-pocket";

  const b64e = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const b64d = text => Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
  const concat = (...parts) => {
    const out = new Uint8Array(parts.reduce((n, p) => n + p.byteLength, 0));
    let offset = 0;
    for (const part of parts) { out.set(new Uint8Array(part), offset); offset += part.byteLength; }
    return out;
  };

  function store(mode, action) {
    return new Promise((resolve, reject) => {
      const open = indexedDB.open(DB, 1);
      open.onupgradeneeded = () => open.result.createObjectStore("kv");
      open.onerror = () => reject(new Error("Ta przeglądarka nie pozwala zapamiętać urządzenia."));
      open.onsuccess = () => {
        const tx = open.result.transaction("kv", mode);
        const request = action(tx.objectStore("kv"));
        tx.oncomplete = () => { open.result.close(); resolve(request.result); };
        tx.onerror = () => { open.result.close(); reject(tx.error); };
      };
    });
  }
  const loadIdentity = () => store("readonly", kv => kv.get("identity"));
  const saveIdentity = identity => store("readwrite", kv => kv.put(identity, "identity"));
  const forgetIdentity = () => store("readwrite", kv => kv.delete("identity"));

  class Cipher {
    constructor(key) { this.key = key; this.counter = 0; }
    nonce() {
      const nonce = new Uint8Array(12);
      new DataView(nonce.buffer).setUint32(8, this.counter++);   // 2^32 records per session is ample
      return nonce;
    }
    async seal(data, final) {
      return b64e(await crypto.subtle.encrypt({ name: "AES-GCM", iv: this.nonce(), additionalData: Uint8Array.of(final ? 1 : 0) }, this.key, data));
    }
    async open(record, final) {
      return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: this.nonce(), additionalData: Uint8Array.of(final ? 1 : 0) }, this.key, b64d(record)));
    }
  }

  class Tunnel {
    constructor(relay, office, workerKey) {
      this.relay = relay; this.office = office; this.workerKey = workerKey;
      this.socket = null; this.queue = Promise.resolve(); this.waiting = null; this.next = 0;
      this.onclose = () => {};
    }

    open() {
      return new Promise((resolve, reject) => {
        const socket = new WebSocket(this.relay + "?role=client&office=" + encodeURIComponent(this.office));
        const failed = () => reject(new Error("Komputer kancelarii jest wyłączony albo niedostępny. Dokumenty są tylko na nim."));
        socket.onerror = failed;
        socket.onclose = failed;
        socket.onopen = () => {
          socket.onerror = null;
          socket.onclose = () => { this.fail(new Error("Połączenie z kancelarią zostało przerwane.")); this.onclose(); };
          socket.onmessage = event => this.receive(event.data);
          this.socket = socket;
          resolve();
        };
      });
    }

    fail(error) {
      if (this.waiting) { this.waiting.reject(error); this.waiting = null; }
    }

    receive(text) {
      let frame;
      try { frame = JSON.parse(text); } catch { frame = { t: "bye" }; }
      if (this.waiting) this.waiting.frame(frame);
    }

    expect(handler) {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { this.waiting = null; reject(new Error("Kancelaria nie odpowiada.")); }, 300000);
        this.waiting = {
          reject: error => { clearTimeout(timer); reject(error); },
          frame: async frame => {
            try {
              if (frame.t === "bye") throw new Error("Kancelaria odrzuciła połączenie. Sparuj urządzenie ponownie.");
              const done = await handler(frame);
              if (done !== undefined) { clearTimeout(timer); this.waiting = null; resolve(done); }
            } catch (error) { clearTimeout(timer); this.waiting = null; reject(error); }
          },
        };
      });
    }

    async connect() {
      await this.open();
      const curve = { name: "ECDH", namedCurve: "P-256" };
      const ephemeral = await crypto.subtle.generateKey(curve, false, ["deriveBits"]);
      const e = new Uint8Array(await crypto.subtle.exportKey("raw", ephemeral.publicKey));
      const welcome = this.expect(frame => {
        if (frame.t !== "welcome") throw new Error("Nieoczekiwana odpowiedź kancelarii.");
        return frame;
      });
      this.socket.send(JSON.stringify({ t: "hello", v: 1, e: b64e(e) }));
      const f = b64d((await welcome).f);
      const bits = async raw => new Uint8Array(await crypto.subtle.deriveBits(
        { name: "ECDH", public: await crypto.subtle.importKey("raw", raw, curve, false, []) }, ephemeral.privateKey, 256));
      const shared = concat(await bits(this.workerKey), await bits(f));
      this.transcript = new Uint8Array(await crypto.subtle.digest("SHA-256", concat(LABEL, this.workerKey, e, f)));
      const material = new Uint8Array(await crypto.subtle.deriveBits(
        { name: "HKDF", hash: "SHA-256", salt: this.transcript, info: LABEL },
        await crypto.subtle.importKey("raw", shared, "HKDF", false, ["deriveBits"]), 512));
      const aes = raw => crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
      this.outbound = new Cipher(await aes(material.slice(0, 32)));
      this.inbound = new Cipher(await aes(material.slice(32)));
    }

    exchange(message) {
      const turn = this.queue.then(async () => {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) throw new Error("Połączenie z kancelarią zostało przerwane.");
        const data = new TextEncoder().encode(JSON.stringify(message));
        const parts = [];
        const reply = this.expect(async frame => {
          if (frame.t !== "d") throw new Error("Nieoczekiwana odpowiedź kancelarii.");
          parts.push(await this.inbound.open(frame.c, frame.f === 1));
          return frame.f === 1 ? JSON.parse(new TextDecoder().decode(concat(...parts))) : undefined;
        });
        for (let offset = 0; offset < Math.max(data.length, 1); offset += CHUNK) {
          const final = offset + CHUNK >= data.length;
          this.socket.send(JSON.stringify({ t: "d", f: final ? 1 : 0, c: await this.outbound.seal(data.subarray(offset, offset + CHUNK), final) }));
        }
        return reply;
      });
      this.queue = turn.catch(() => {});
      return turn;
    }

    async request(method, path, body) {
      const id = ++this.next;
      const reply = await this.exchange({ op: "req", id, method, path, body: body === undefined ? null : body });
      if (reply.id !== id) throw new Error("Nieoczekiwana odpowiedź kancelarii.");
      return { status: reply.status, body: reply.body };
    }

    close() {
      if (this.socket) { this.socket.onclose = null; this.socket.close(); this.socket = null; }
    }
  }

  // First contact: the pairing link carries the relay, the office, its key and a one-time code.
  async function pair(link) {
    const signing = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
    const tunnel = new Tunnel(link.relay, link.office, b64d(link.key));
    await tunnel.connect();
    const publicKey = await crypto.subtle.exportKey("raw", signing.publicKey);
    const device = await tunnel.exchange({ op: "pair", code: link.code, key: b64e(publicKey) });
    await saveIdentity({ relay: link.relay, office: link.office, key: link.key, device: device.device, signing });
    return { tunnel, device };
  }

  // Later visits: no code and no stored token, only a signature with the device key.
  async function resume() {
    const identity = await loadIdentity();
    if (!identity) return null;
    const tunnel = new Tunnel(identity.relay, identity.office, b64d(identity.key));
    await tunnel.connect();
    const message = concat(LABEL, new TextEncoder().encode("|auth|"), tunnel.transcript);
    const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, identity.signing.privateKey, message);
    const device = await tunnel.exchange({ op: "auth", device: identity.device, sig: b64e(signature) });
    return { tunnel, device };
  }

  function parseLink(fragment) {
    const values = new URLSearchParams(fragment.replace(/^#/, ""));
    const link = { relay: values.get("r"), office: values.get("o"), key: values.get("k"), code: values.get("c") };
    if (!link.relay || !link.office || !link.key || !link.code) return null;
    if (!/^wss:\/\//.test(link.relay) && !/^ws:\/\/127\.0\.0\.1[:/]/.test(link.relay)) return null;
    return link;
  }

  return { pair, resume, parseLink, forgetIdentity, hasIdentity: async () => Boolean(await loadIdentity()) };
})();
