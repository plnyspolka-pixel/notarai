// Testy strażnika: node --test .claude/hooks/straznik.test.mjs
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { checkShell, checkWrite, decidePre, diffSnapshots, isSecretHome } from "./straznik.mjs";

import os from "node:os";
import fs from "node:fs";
import path from "node:path";
const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), "straznik-"));
const id = (cmd) => checkShell(cmd)?.id ?? null;
// Fałszywe sekrety składane z kawałków — żeby skanery sekretów nie zgłaszały tego pliku.
const AWS = "AKIA" + "ABCDEFGHIJKLMNOP";
const GH = "ghp_" + "a".repeat(36);
const SK = "sk-" + "ant-" + "x".repeat(40);
const PEM = "-----BEGIN " + "PRIVATE KEY-----";

test("blokuje wypisywanie sekretów w powłoce", () => {
  assert.equal(id("aws secretsmanager get-secret-value --secret-id notarai/x"), "sekret-aws-odczyt");
  assert.equal(id("cat .env"), "sekret-env-odczyt");
  assert.equal(id("type C:\\app\\.env.local"), "sekret-env-odczyt");
  assert.equal(id('Get-Content "./.env.production"'), "sekret-env-odczyt");
  assert.equal(id("gh auth token"), "sekret-token-cli");
  assert.equal(id('echo "$SUPABASE_SERVICE_ROLE_KEY"'), "sekret-echo-zmiennej");
  assert.equal(id("Write-Host $env:CLOUDFLARE_API_TOKEN"), "sekret-echo-zmiennej");
});

test("przepuszcza bezpieczne odpowiedniki (mało fałszywych alarmów)", () => {
  for (const ok of [
    "cat .env.example",
    "grep -c '^SUPABASE_URL=' .env",
    "ls -la .env",
    '[ -n "$GITHUB_TOKEN" ] && echo ustawiona',
    "echo $HOME",
    "cat package.json",
    "aws secretsmanager list-secrets",
    "git push origin feature/x",
    "git push --force origin feature/x",
    "git commit -m 'opis'",
    "git commit --amend --no-edit",
    "git push -n origin main",
  ]) assert.equal(id(ok), null, ok);
});

test("blokuje force-push na gałąź główną i omijanie hooków", () => {
  assert.equal(id("git push --force origin main"), "git-force-glowna");
  assert.equal(id("git push -f origin master"), "git-force-glowna");
  assert.equal(id("git push origin +main"), "git-force-glowna");
  assert.equal(id("git commit --no-verify -m x"), "git-no-verify");
  assert.equal(id("git commit -nm x"), "git-no-verify");
  assert.equal(id("git push --no-verify origin x"), "git-no-verify");
});

test("blokuje sekret zapisywany do pliku repo, ale nie do .env", () => {
  for (const s of [AWS, GH, SK, PEM, "sk_live_" + "b".repeat(24)]) {
    assert.ok(checkWrite("src/config.ts", `const k = "${s}";`), s.slice(0, 6));
  }
  assert.equal(checkWrite(".env", `KEY=${AWS}`), null);
  assert.equal(checkWrite("C:/Users/x/.aws/credentials", AWS), null);
  assert.ok(checkWrite(".env.example", `KEY=${AWS}`), "przykład trafia do repo");
  assert.equal(checkWrite("src/a.ts", "const x = process.env.KEY;"), null);
});

test("isSecretHome", () => {
  assert.equal(isSecretHome(".env"), true);
  assert.equal(isSecretHome("app/.env.local"), true);
  assert.equal(isSecretHome(".dev.vars"), true);
  assert.equal(isSecretHome(".env.example"), false);
  assert.equal(isSecretHome("src/env.ts"), false);
});

test("decidePre rozpoznaje narzędzia", () => {
  assert.ok(decidePre({ tool_name: "Bash", tool_input: { command: "cat .env" } }));
  assert.ok(decidePre({ tool_name: "PowerShell", tool_input: { command: "gc .env" } }));
  assert.ok(decidePre({ tool_name: "Edit", tool_input: { file_path: "a.ts", new_string: GH } }));
  assert.ok(decidePre({ tool_name: "MultiEdit", tool_input: { file_path: "a.ts", edits: [{ new_string: SK }] } }));
  assert.equal(decidePre({ tool_name: "Read", tool_input: { file_path: ".env" } }), null);
});

test("diffSnapshots", () => {
  assert.deepEqual(diffSnapshots({ a: "1", b: "2" }, { a: "1", b: "3", c: "4" }), ["zmienione: b", "nowe: c"]);
  assert.deepEqual(diffSnapshots({ a: "1" }, {}), ["usunięte: a"]);
});

test("hook jako proces: deny w formacie Claude Code, cisza przy dozwolonym", () => {
  const script = fileURLToPath(new URL("./straznik.mjs", import.meta.url));
  const run = (input) =>
    spawnSync(process.execPath, [script, "pre"], {
      input: JSON.stringify(input),
      encoding: "utf8",
      env: { ...process.env, HOME: tmpHome, USERPROFILE: tmpHome },
    });
  const deny = run({ tool_name: "Bash", tool_input: { command: "cat .env" }, cwd: "x" });
  assert.equal(deny.status, 0);
  const out = JSON.parse(deny.stdout);
  assert.equal(out.hookSpecificOutput.permissionDecision, "deny");
  assert.match(out.hookSpecificOutput.permissionDecisionReason, /Zamiast tego/);
  const allow = run({ tool_name: "Bash", tool_input: { command: "ls" } });
  assert.equal(allow.status, 0);
  assert.equal(allow.stdout, "");
  const broken = spawnSync(process.execPath, [script, "pre"], { input: "nie-json", encoding: "utf8", env: { ...process.env, HOME: tmpHome, USERPROFILE: tmpHome } });
  assert.equal(broken.status, 0, "zepsute wejście nie blokuje pracy");
});
