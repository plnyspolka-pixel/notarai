/* Synthetic ciphertext-only browser courier test; no AWS, no customer data. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

async function scenario() {
  const handlers = {};
  const requests = [];
  const control = (id) => ({
    id, disabled: false, value: "", files: [],
    addEventListener(name, callback) { handlers[id + ":" + name] = callback; },
    textContent: "",
  });
  const elements = Object.fromEntries(
    ["store", "preview", "encrypted", "status"].map(id => [id, control(id)])
  );
  const sandbox = {
    document: { getElementById(id) { return elements[id]; } },
    fetch: async (url, args) => {
      requests.push({ url, args });
      return {ok: true, json: async () =>
        args.method === "PUT"
          ? {stored: true, s3_version: "s3Version001"}
          : {operation: "preview-only", can_submit: false},
      };
    },
  };
  vm.runInNewContext(
    fs.readFileSync("static/confidential-courier.js", "utf8"),
    sandbox, {filename: "confidential-courier.js"}
  );
  const envelope = {
    version: 2,
    algorithm: "AES-256-GCM+RSA-OAEP-SHA256",
    tenant_id: "pilot01", case_id: "case01", object_id: "scan01",
    kms_key_arn: "arn:aws:kms:eu-central-1:111122223333:key/pilot",
    document_version: "a".repeat(32),
    public_key_sha256: "A".repeat(43) + "=",
    nonce: "AQ==", wrapped_dek: "Ag==", ciphertext: "Aw==",
  };
  const asFile = (name, content) => ({
    name, size: Buffer.byteLength(content),
    text: async () => content,
  });
  elements.encrypted.files = [asFile("original.pdf", "REAL PLAINTEXT")];
  await handlers["store:click"]();
  assert.equal(requests.length, 0);
  elements.encrypted.files = [asFile(
    "scan01.encrypted.json", JSON.stringify({...envelope, version: 1})
  )];
  await handlers["store:click"]();
  assert.equal(requests.length, 0);
  elements.encrypted.files = [asFile(
    "scan01.encrypted.json", JSON.stringify(envelope)
  )];
  await handlers["store:click"]();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].args.method, "PUT");
  assert.equal(requests[0].url,
    "/api/confidential/envelopes/case01/scan01");
  assert.ok(!requests[0].args.body.includes("REAL PLAINTEXT"));
  assert.equal(elements.preview.disabled, false);
  await handlers["preview:click"]();
  assert.equal(requests.length, 2);
  assert.equal(requests[1].args.method, "POST");
  assert.equal(requests[1].url,
    "/api/confidential/preview/case01/scan01");
  assert.ok(!("submit" in requests[1].args));
  assert.match(elements.status.textContent, /nie zostanie wysłany/);
}
scenario().catch(error => { console.error(error); process.exit(1); });
