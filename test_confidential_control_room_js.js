"use strict";
/* Offline Node tests for notary-only Control Room network contract. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("static/confidential-control-room.js", "utf8");

function setup(response, httpStatus = 200) {
  const calls = [];
  const doc = {
    readyState: "loading",
    addEventListener() {},
  };
  const window = {};
  vm.runInNewContext(source, {
    document: doc,
    window,
    fetch: async (path, options) => {
      calls.push({path, options});
      return {ok: httpStatus === 200, status: httpStatus,
              json: async () => response};
    }
  });
  return {api: window.NotarAIConfidentialControlRoom, calls};
}

function fixture() {
  return {
    version: 1,
    mode: "auto",
    thinking_enabled: false,
    can_submit: false,
    read_only: true,
    attention_on_page: 1,
    more_available: false,
    jobs: [{
      job_id: "abc012",
      status: "needs_review",
      attempts: 3,
      created_at: 1800000000,
      attention_required: true,
      attention_reason: "needs_review",
      submitted: false,
    }]
  };
}

async function main() {
  const {api, calls} = setup(fixture());
  const data = await api.fetchJobs();
  assert.equal(data.jobs[0].attention_required, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/api/confidential/control/jobs?limit=10");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[0].options.credentials, "same-origin");
  assert.equal(Object.hasOwn(calls[0].options, "body"), false);
  assert.deepEqual(Object.keys(api).sort(),
    ["fetchJobs", "fetchHistory", "refresh"].sort());

  for (const altered of [
    {can_submit: true}, {thinking_enabled: true},
    {read_only: false}, {mode: "manual"},
  ]) {
    const unsafe = setup({...fixture(), ...altered});
    await assert.rejects(unsafe.api.fetchJobs());
  }

  for (const job of [
    {submitted: true},
    {job_id: "../../other"},
    {status: "submitted"},
    {attempts: 999},
    {attention_reason: "unknown"},
  ]) {
    const unsafe = setup({
      ...fixture(), jobs: [{...fixture().jobs[0], ...job}]
    });
    await assert.rejects(unsafe.api.fetchJobs());
  }

  const eventFixture = {
    version: 1, read_only: true, job_id: "abc012",
    more_available: false,
    events: [{
      timestamp: 1800000000, from: "queued", to: "running",
      attempts: 1, event: "0123456789ab"
    }],
  };
  const history = setup(eventFixture);
  const event = await history.api.fetchHistory("abc012");
  assert.equal(event.events[0].to, "running");
  assert.equal(history.calls[0].path,
    "/api/confidential/control/jobs/abc012/history");
  assert.equal(history.calls[0].options.method, "GET");
  assert.equal(Object.hasOwn(history.calls[0].options, "body"), false);
  await assert.rejects(history.api.fetchHistory("../other"));
  for (const change of [
    {read_only: false},
    {job_id: "other"},
    {events: [{...eventFixture.events[0], to: "submitted"}]},
    {events: [{...eventFixture.events[0], event: "bad"}]},
  ]) {
    await assert.rejects(setup({...eventFixture, ...change}).api.fetchHistory("abc012"));
  }

  const unauthorized = setup(null, 403);
  await assert.rejects(unauthorized.api.fetchJobs());
  assert.equal(unauthorized.calls.length, 1);
  console.log("Read-only AUTO control room: role denials and unsafe API data rejected");
}

main().catch(err => {console.error(err); process.exitCode = 1;});
