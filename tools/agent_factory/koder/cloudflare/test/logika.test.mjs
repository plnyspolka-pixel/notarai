import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import {
  cialoGrupy, doSprzatniecia, kartyZ, koszt, podpisGithub, wpisyDrzewa, wybierzGpu, zdarzeniePush,
} from "../src/logika.js";

test("podpis webhooka GitHuba", async () => {
  const tresc = '{"ref":"refs/heads/koder/x"}';
  const dobry = "sha256=" + createHmac("sha256", "tajne").update(tresc).digest("hex");
  assert.equal(await podpisGithub("tajne", tresc, dobry), true);
  assert.equal(await podpisGithub("tajne", tresc + " ", dobry), false);
  assert.equal(await podpisGithub("inne", tresc, dobry), false);
  assert.equal(await podpisGithub("", tresc, dobry), false);
  assert.equal(await podpisGithub("tajne", tresc, null), false);
});

test("push: tylko koder/* z naszego repo", () => {
  const sha = "a".repeat(40);
  const p = (ref, extra = {}) => ({ ref, after: sha, repository: { full_name: "o/r" }, ...extra });
  assert.deepEqual(zdarzeniePush(p("refs/heads/koder/paczka"), "o/r"), { ref: "koder/paczka", sha });
  assert.equal(zdarzeniePush(p("refs/heads/master"), "o/r").pomin, "nie_koder");
  assert.equal(zdarzeniePush(p("refs/heads/koder/x", { deleted: true }), "o/r").pomin, "usunieta_galaz");
  assert.equal(zdarzeniePush(p("refs/heads/koder/x"), "inne/r").pomin, "obce_repo");
});

test("karty: walidacja listy", () => {
  assert.equal(kartyZ(" a-b , c "), "a-b,c");
  assert.equal(kartyZ(""), "");
  assert.throws(() => kartyZ("../x"));
});

const klasy = [
  { id: "g5090", name: "RTX 5090 (32 GB)", prices: [{ priority: "batch", price: "0.25" }, { priority: "high", price: "0.600" }] },
  { id: "g4090", name: "RTX 4090 (24 GB)", prices: [{ priority: "batch", price: "0.16" }] },
];

test("GPU: batch przed high, budżet przycina czas", () => {
  const g = wybierzGpu(klasy, { priorytety: ["batch", "high"], minVram: 32, maxHourly: 1, maxUsd: 1.5, minuty: 120 });
  assert.equal(g.id, "g5090");
  assert.equal(g.priorytet, "batch");
  assert.equal(g.minuty, 120);
  const h = wybierzGpu(klasy, { priorytety: ["high"], minVram: 32, maxHourly: 1, maxUsd: 0.6, minuty: 120 });
  assert.equal(h.minuty, 60);
  assert.ok(h.max_usd <= 0.6);
  assert.equal(wybierzGpu(klasy, { priorytety: ["high"], minVram: 48, maxHourly: 1, maxUsd: 1, minuty: 60 }), null);
});

test("ciało grupy: jedna replika, termin, bez kluczy w zmiennych", () => {
  const b = cialoGrupy({
    nazwa: "finyou-ai-clip-koder-20261123t1200", gpu: { id: "g", nazwa: "RTX", usd_h: 0.25, priorytet: "batch" },
    termin: "2026-11-23T14:00:00.000Z", sha: "b".repeat(40), repo: "o/r", przebieg: "cf-x", karty: "",
    model: "m", parser: "p", vllmArgs: "", image: "i", kontekst: 1, rownolegle: 3,
  });
  assert.equal(b.replicas, 1);
  assert.equal(b.restart_policy, "never");
  assert.equal(b.container.environment_variables.AICLIP_DEADLINE, "2026-11-23T14:00:00.000Z");
  assert.match(b.container.environment_variables.KODER_WEZEL_URL, /raw\.githubusercontent\.com\/o\/r\/b{40}\//);
  assert.ok(!JSON.stringify(b).match(/api[-_]?key|token/i));
});

test("strażnik: usuwa po terminie i osierocone, nie rusza bieżącej ani obcych", () => {
  const teraz = Date.parse("2026-11-23T12:00:00Z");
  const g = (name, t) => ({ name, container: { environment_variables: t ? { KODER_DEADLINE: t } : {} } });
  const grupy = [
    g("finyou-ai-clip-koder-a", "2026-11-23T13:00:00Z"),
    g("finyou-ai-clip-koder-b", "2026-11-23T11:00:00Z"),
    g("finyou-ai-clip-20261123t1100", "2026-11-23T11:00:00Z"),
    g("finyou-ai-clip-koder-c", null),
  ];
  assert.deepEqual(doSprzatniecia(grupy, "finyou-ai-clip-koder-", "finyou-ai-clip-koder-a", teraz),
    ["finyou-ai-clip-koder-b", "finyou-ai-clip-koder-c"]);
  assert.deepEqual(doSprzatniecia(grupy, "finyou-ai-clip-koder-", null, teraz),
    ["finyou-ai-clip-koder-a", "finyou-ai-clip-koder-b", "finyou-ai-clip-koder-c"]);
});

test("drzewo: tekst wprost, binaria jako blob, usunięcia, zakaz ucieczki ze ścieżki", () => {
  const b64 = (s) => Buffer.from(s).toString("base64");
  const { wpisy, bloby } = wpisyDrzewa({ "a.py": b64("zażółć\n"), "x.bin": Buffer.from([0xff, 0xfe]).toString("base64"), "stary.py": null }, "p/");
  assert.deepEqual(wpisy[0], { path: "p/a.py", mode: "100644", type: "blob", content: "zażółć\n" });
  assert.deepEqual(wpisy[1], { path: "p/stary.py", mode: "100644", type: "blob", sha: null });
  assert.equal(bloby[0].path, "p/x.bin");
  assert.throws(() => wpisyDrzewa({ "../a": b64("x") }));
  assert.throws(() => wpisyDrzewa({ ".git/config": b64("x") }));
});

test("koszt: górna granica", () => {
  assert.equal(koszt(0.6, 0, 3600000), 0.6);
  assert.equal(koszt(0.25, 0, 30 * 60000), 0.125);
  assert.equal(koszt(null, 0, 1), null);
});
