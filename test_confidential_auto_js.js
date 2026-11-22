"use strict";
/* Offline Node tests for the UI-to-API AUTO boundary. No browser or AWS. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const script = fs.readFileSync("static/confidential-auto.js", "utf8");

function context(policyResponse) {
  const requests = [];
  const fakeDocument = {
    readyState: "loading",
    addEventListener() {},
    querySelector() { return null; },
    getElementById() { return null; },
  };
  const fakeWindow = {};
  const sandbox = {
    document: fakeDocument,
    window: fakeWindow,
    fetch: async (url, options) => {
      requests.push({url, options});
      if (url === "/api/confidential/policy") {
        return {ok: true, json: async () => policyResponse};
      }
      if (url.startsWith("/api/confidential/preview/")) {
        return {ok: true, json: async () => ({
          queued: true, job_id: "abcdef123456", mode: "auto",
          operation: "preview-only", can_submit: false
        })};
      }
      if (url.startsWith("/api/confidential/jobs/")) {
        return {ok: true, json: async () => ({
          job_id: "abcdef123456", status: "preview_completed",
          submitted: false, mode: "auto", can_submit: false
        })};
      }
      throw new Error("Unexpected network request");
    },
  };
  vm.runInNewContext(script, sandbox);
  return {client: fakeWindow.NotarAIConfidentialAuto, requests};
}

async function main() {
  const safe = {
    version: 1, mode: "auto", can_submit: false,
    can_sign: false, external_writes_enabled: false,
    thinking_enabled: false,
    ai_inference: {
      confidential_llm_enabled: false,
      external_bedrock_allowed: false,
      zk_status: "BLOCKED",
      strict_zero_knowledge_verified: false
    }
  };
  const {client, requests} = context(safe);
  const result = await client.queuePreview("case01", "scan01");
  assert.equal(result.mode, "auto");
  assert.equal(requests.length, 2);
  const req = requests[1];
  assert.equal(req.url, "/api/confidential/preview/case01/scan01?mode=auto");
  assert.equal(req.options.method, "POST");
  assert.equal(Object.hasOwn(req.options, "body"), false);
  assert(!req.url.includes("submit"));
  assert.deepEqual(Object.keys(client).sort(),
    ["jobStatus", "policy", "queuePreview", "refreshPolicy"].sort());
  const status = await client.jobStatus("abcdef123456");
  assert.equal(status.submitted, false);
  assert.equal(requests.length, 3);
  await assert.rejects(client.queuePreview("../other", "scan01"));
  const unsafe = context({...safe, can_submit: true});
  await assert.rejects(unsafe.client.queuePreview("case01", "scan01"));
  assert.equal(unsafe.requests.length, 1);
  const thought = context({...safe, thinking_enabled: true});
  await assert.rejects(thought.client.queuePreview("case01", "scan01"));
  assert.equal(thought.requests.length, 1);
  for (const injected of [
    {confidential_llm_enabled: true},
    {external_bedrock_allowed: true},
    {zk_status: "VERIFIED"},
    {strict_zero_knowledge_verified: true},
  ]) {
    const forged = context({
      ...safe, ai_inference: {...safe.ai_inference, ...injected}
    });
    await assert.rejects(forged.client.queuePreview("case01", "scan01"));
    assert.equal(forged.requests.length, 1,
      "invalid AI policy must be rejected before enqueue");
  }
  const missing = context({...safe, ai_inference: null});
  await assert.rejects(missing.client.queuePreview("case01", "scan01"));
  assert.equal(missing.requests.length, 1);
  console.log("AUTO client: blocked fake-ZK flags, submit escalation and unsafe policies");
}

main().catch(err => {console.error(err); process.exitCode = 1;});
