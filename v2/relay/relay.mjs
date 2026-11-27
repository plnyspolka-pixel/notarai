// NotarAI relay: forwards opaque frames between a device and its office worker.
// It cannot read them (end-to-end encryption happens above it) and it stores no frame,
// only which connection belongs to which office. Runs as one Lambda behind an
// API Gateway WebSocket API (infra/notarai-v2-przekaznik.yaml).
import { createHash, createPublicKey, verify } from "node:crypto";

export const MAX_SKEW_SECONDS = 120;
export const MAX_FRAME = 64 * 1024;
const OFFICE = /^[0-9a-f]{32}$/;

function fromBase64Url(text) {
  return Buffer.from(String(text || ""), "base64url");
}

// The office address is the hash of the worker's public key, and the worker signs the
// connection request with that key: nobody else can register as this office.
export function workerProofIsValid(query, now) {
  const { office, key, ts, sig } = query || {};
  const timestamp = Number(ts);
  if (!OFFICE.test(office || "") || !Number.isInteger(timestamp) || Math.abs(now - timestamp) > MAX_SKEW_SECONDS) {
    return false;
  }
  const raw = fromBase64Url(key);
  if (raw.length !== 65 || raw[0] !== 4) return false;
  if (createHash("sha256").update(raw).digest("hex").slice(0, 32) !== office) return false;
  try {
    const publicKey = createPublicKey({
      format: "jwk",
      key: { kty: "EC", crv: "P-256", x: raw.subarray(1, 33).toString("base64url"), y: raw.subarray(33).toString("base64url") },
    });
    return verify("sha256", Buffer.from(`notarai-relay-v1|${office}|${timestamp}`), publicKey, fromBase64Url(sig));
  } catch {
    return false;
  }
}

// `store`: { putWorker(office, id), getWorker(office), putClient(id, office), getClient(id), remove(id), removeWorker(office, id) }
// `post(connectionId, text)` resolves false when that connection is gone.
export function createRelay({ store, post, now = () => Math.floor(Date.now() / 1000) }) {
  async function connect(connectionId, query) {
    if (query?.role === "worker") {
      if (!workerProofIsValid(query, now())) return 403;
      await store.putWorker(query.office, connectionId);
      return 200;
    }
    if (query?.role === "client" && OFFICE.test(query.office || "")) {
      // Refuse early when the office is offline, so the phone can say so at once.
      if (!(await store.getWorker(query.office))) return 404;
      await store.putClient(connectionId, query.office);
      return 200;
    }
    return 400;
  }

  async function disconnect(connectionId) {
    const client = await store.getClient(connectionId);
    await store.remove(connectionId);
    if (client) {
      const worker = await store.getWorker(client.office);
      if (worker) await post(worker, JSON.stringify({ from: connectionId, gone: true }));
    }
  }

  async function message(connectionId, body) {
    if (typeof body !== "string" || body.length > MAX_FRAME) return 413;
    const client = await store.getClient(connectionId);
    if (client) {
      const worker = await store.getWorker(client.office);
      if (!worker || !(await post(worker, JSON.stringify({ from: connectionId, data: body })))) {
        await post(connectionId, JSON.stringify({ t: "bye" }));
        return 410;
      }
      return 200;
    }
    // Otherwise the sender must be a worker answering one of its own clients.
    let envelope;
    try { envelope = JSON.parse(body); } catch { return 400; }
    if (typeof envelope?.to !== "string" || typeof envelope.data !== "string") return 400;
    const target = await store.getClient(envelope.to);
    if (!target || (await store.getWorker(target.office)) !== connectionId) return 403;
    await post(envelope.to, envelope.data);
    return 200;
  }

  return { connect, disconnect, message };
}
