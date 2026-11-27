// node --test v2/relay
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { test } from "node:test";
import { createRelay, workerProofIsValid } from "./relay.mjs";

function office(now = 1_800_000_000) {
  const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  const jwk = publicKey.export({ format: "jwk" });
  const raw = Buffer.concat([Buffer.from([4]), Buffer.from(jwk.x, "base64url"), Buffer.from(jwk.y, "base64url")]);
  const id = createHash("sha256").update(raw).digest("hex").slice(0, 32);
  const query = ts => ({
    role: "worker", office: id, key: raw.toString("base64url"), ts: String(ts),
    sig: sign("sha256", Buffer.from(`notarai-relay-v1|${id}|${ts}`), privateKey).toString("base64url"),
  });
  return { id, query, now };
}

function memory() {
  const workers = new Map(), clients = new Map(), sent = [], dead = new Set();
  const store = {
    async putWorker(o, id) { workers.set(o, id); },
    async getWorker(o) { return workers.get(o) ?? null; },
    async putClient(id, o) { clients.set(id, { office: o }); },
    async getClient(id) { return clients.get(id) ?? null; },
    async remove(id) { clients.delete(id); for (const [o, w] of workers) if (w === id) workers.delete(o); },
  };
  const post = async (id, text) => { if (dead.has(id)) return false; sent.push([id, text]); return true; };
  return { store, post, sent, dead, workers, clients };
}

test("only the key holder can register an office, within the time window", () => {
  const a = office(), b = office();
  assert.equal(workerProofIsValid(a.query(a.now), a.now), true);
  assert.equal(workerProofIsValid(a.query(a.now), a.now + 121), false);
  assert.equal(workerProofIsValid({ ...a.query(a.now), office: b.id }, a.now), false);
  assert.equal(workerProofIsValid({ ...b.query(a.now), office: a.id, key: a.query(a.now).key }, a.now), false);
  assert.equal(workerProofIsValid({ ...a.query(a.now), sig: "AAAA" }, a.now), false);
  assert.equal(workerProofIsValid({}, a.now), false);
  assert.equal(workerProofIsValid(undefined, a.now), false);
});

test("frames travel only between a client and its own office", async () => {
  const a = office(), b = office(), m = memory();
  const relay = createRelay({ store: m.store, post: m.post, now: () => a.now });
  assert.equal(await relay.connect("C0", { role: "client", office: a.id }), 404);     // office offline
  assert.equal(await relay.connect("WA", a.query(a.now)), 200);
  assert.equal(await relay.connect("WB", b.query(a.now)), 200);
  assert.equal(await relay.connect("X", { role: "worker", office: a.id }), 403);
  assert.equal(await relay.connect("X", { role: "other" }), 400);
  assert.equal(await relay.connect("C1", { role: "client", office: a.id }), 200);

  assert.equal(await relay.message("C1", "frame-1"), 200);
  assert.deepEqual(m.sent.pop(), ["WA", JSON.stringify({ from: "C1", data: "frame-1" })]);
  assert.equal(await relay.message("WA", JSON.stringify({ to: "C1", data: "reply-1" })), 200);
  assert.deepEqual(m.sent.pop(), ["C1", "reply-1"]);

  // Another office's worker cannot write to this client; strangers cannot write at all.
  assert.equal(await relay.message("WB", JSON.stringify({ to: "C1", data: "evil" })), 403);
  assert.equal(await relay.message("stranger", JSON.stringify({ to: "C1", data: "evil" })), 403);
  assert.equal(await relay.message("WA", "not json"), 400);
  assert.equal(await relay.message("C1", "x".repeat(70000)), 413);
  assert.equal(m.sent.length, 0);

  await relay.disconnect("C1");
  assert.deepEqual(m.sent.pop(), ["WA", JSON.stringify({ from: "C1", gone: true })]);
  assert.equal(await relay.message("C1", "late"), 400);
});

test("a client learns at once when its office goes away", async () => {
  const a = office(), m = memory();
  const relay = createRelay({ store: m.store, post: m.post, now: () => a.now });
  await relay.connect("WA", a.query(a.now));
  await relay.connect("C1", { role: "client", office: a.id });
  m.dead.add("WA");
  assert.equal(await relay.message("C1", "frame"), 410);
  assert.deepEqual(m.sent.pop(), ["C1", JSON.stringify({ t: "bye" })]);
  await relay.disconnect("WA");
  assert.equal(await relay.connect("C2", { role: "client", office: a.id }), 404);
});
