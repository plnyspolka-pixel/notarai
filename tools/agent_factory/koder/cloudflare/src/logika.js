// Czysta logika Workera notarai-koder (bez sieci) - testy: node --test test/
export const KODER_RE = /^[a-z][a-z0-9-]{0,61}[a-z0-9]$/;
export const SHA_RE = /^[0-9a-f]{40}$/;
export const KARTA_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

const enc = new TextEncoder();

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256hex(tekst) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(tekst)));
}

/** Porównanie w stałym czasie (przez skróty, więc długość nie wycieka). */
export async function rowne(a, b) {
  const [x, y] = await Promise.all([sha256hex(String(a)), sha256hex(String(b))]);
  let r = 0;
  for (let i = 0; i < x.length; i++) r |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return r === 0 && String(a).length > 0;
}

/** Podpis webhooka GitHuba: nagłówek X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(treść). */
export async function podpisGithub(sekret, tresc, naglowek) {
  if (!sekret || !naglowek || !String(naglowek).startsWith("sha256=")) return false;
  const klucz = await crypto.subtle.importKey("raw", enc.encode(sekret), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]);
  const podpis = "sha256=" + hex(await crypto.subtle.sign("HMAC", klucz, enc.encode(tresc)));
  return rowne(podpis, naglowek);
}

/** Zdarzenie push z GitHuba -> {ref, sha} albo powód pominięcia. */
export function zdarzeniePush(payload, repo) {
  if (!payload || typeof payload !== "object") return { pomin: "zly_json" };
  if (payload.repository?.full_name !== repo) return { pomin: "obce_repo" };
  const ref = String(payload.ref || "");
  if (!ref.startsWith("refs/heads/koder/")) return { pomin: "nie_koder" };
  if (payload.deleted) return { pomin: "usunieta_galaz" };
  const sha = String(payload.after || "");
  if (!SHA_RE.test(sha)) return { pomin: "zly_sha" };
  return { ref: ref.slice("refs/heads/".length), sha };
}

/** Karty do wykonania: "a,b" -> "a,b" po walidacji, pusty = wszystkie. */
export function kartyZ(tekst) {
  if (!tekst) return "";
  const k = String(tekst).split(",").map((s) => s.trim()).filter(Boolean);
  if (k.length > 50 || k.some((x) => !KARTA_RE.test(x))) throw new Error("zle_karty");
  return k.join(",");
}

/**
 * Wybór karty GPU: najpierw kolejne priorytety (batch, potem high), w każdym największy VRAM
 * i najtańsza oferta spełniająca limity. Czas pracy przycięty tak, by nie przekroczyć budżetu.
 */
export function wybierzGpu(klasy, { priorytety, minVram, maxHourly, maxUsd, minuty }) {
  for (const priorytet of priorytety) {
    const oferty = [];
    for (const c of klasy || []) {
      const m = /\((\d+)\s*GB\)/.exec(String(c?.name ?? ""));
      const cena = (c?.prices || []).find((p) => p.priority === priorytet);
      if (!m || !cena) continue;
      const usd = Number(cena.price);
      const vram = Number(m[1]);
      if (vram >= minVram && usd > 0 && usd <= maxHourly) oferty.push({ id: c.id, nazwa: c.name, vram, usd_h: usd, priorytet });
    }
    oferty.sort((a, b) => b.vram - a.vram || a.usd_h - b.usd_h);
    if (oferty.length) {
      const o = oferty[0];
      const min = Math.min(minuty, Math.floor((maxUsd / o.usd_h) * 60));
      if (min >= 30) return { ...o, minuty: min, max_usd: +((min / 60) * o.usd_h).toFixed(2) };
    }
  }
  return null;
}

/** Treść tworzenia grupy kontenerów Salad: vLLM + agenci na jednym węźle (wezel.py). */
export function cialoGrupy({ nazwa, gpu, termin, sha, repo, przebieg, karty, model, parser, vllmArgs, image,
  kontekst, rownolegle }) {
  const wezelUrl = `https://raw.githubusercontent.com/${repo}/${sha}/tools/agent_factory/koder/wezel.py`;
  const pobierz = "import os,urllib.request as u;u.urlretrieve(os.environ['KODER_WEZEL_URL'],'/wezel.py')";
  return {
    name: nazwa,
    display_name: nazwa,
    container: {
      image,
      command: ["bash", "-c", `python3 -c "${pobierz}" && exec python3 -u /wezel.py`],
      priority: gpu.priorytet,
      resources: { cpu: 8, memory: 32 * 1024, gpu_classes: [gpu.id], storage_amount: 60 * 1024 ** 3 },
      environment_variables: {
        // AICLIP_DEADLINE: wymagany przez bramę salad-brama i jej strażnika (usuwa grupę po terminie).
        AICLIP_DEADLINE: termin, KODER_DEADLINE: termin, KODER_WEZEL_URL: wezelUrl, KODER_REPO: repo,
        KODER_SHA: sha, KODER_RUN: przebieg, KODER_KARTY: karty || "", KODER_MODEL: model,
        KODER_PARSER: parser, KODER_VLLM_ARGS: vllmArgs, KODER_IMAGE: image, KODER_CONTEXT: String(kontekst),
        KODER_PARALLEL: String(rownolegle), KODER_GROUP: nazwa, KODER_GPU: gpu.nazwa, KODER_USD_H: String(gpu.usd_h),
      },
    },
    autostart_policy: true,
    restart_policy: "never",
    replicas: 1,
    networking: {
      protocol: "http", port: 8000, auth: true, load_balancer: "round_robin",
      single_connection_limit: false, client_request_timeout: 100000, server_response_timeout: 100000,
    },
  };
}

/** Termin grupy z jej zmiennych; null, gdy brak. */
export function terminGrupy(g) {
  const t = Date.parse(String(g?.container?.environment_variables?.KODER_DEADLINE ?? ""));
  return Number.isFinite(t) ? t : null;
}

/** Które grupy kodera usunąć: po terminie albo bez terminu, albo nie nasza bieżąca. */
export function doSprzatniecia(grupy, prefiks, biezaca, teraz) {
  return (grupy || [])
    .filter((g) => typeof g?.name === "string" && g.name.startsWith(prefiks) && KODER_RE.test(g.name))
    .filter((g) => {
      const t = terminGrupy(g);
      return g.name !== biezaca || t === null || t < teraz;
    })
    .map((g) => g.name);
}

function base64Bajty(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Wpisy drzewa Git (API GitHuba) z mapy ścieżka -> base64 | null (usunięcie).
 * Tekst UTF-8 do 1 MB idzie wprost w `content`, resztę trzeba wysłać jako blob (zwracamy listę).
 */
export function wpisyDrzewa(pliki, przedrostek = "") {
  const wpisy = [];
  const bloby = [];
  for (const [sciezka, b64] of Object.entries(pliki || {})) {
    if (sciezka.startsWith("/") || sciezka.split("/").some((p) => p === ".." || p === "." || p === ".git" || !p))
      throw new Error("zla_sciezka " + sciezka);
    const path = przedrostek + sciezka;
    if (b64 === null) {
      wpisy.push({ path, mode: "100644", type: "blob", sha: null });
      continue;
    }
    const bajty = base64Bajty(b64);
    let tekst = null;
    if (bajty.length <= 1024 * 1024) {
      try {
        tekst = new TextDecoder("utf-8", { fatal: true }).decode(bajty);
      } catch {
        tekst = null;
      }
    }
    if (tekst !== null) wpisy.push({ path, mode: "100644", type: "blob", content: tekst });
    else bloby.push({ path, b64 });
  }
  return { wpisy, bloby };
}

/** Górna granica kosztu: cena za godzinę x czas od utworzenia do usunięcia grupy. */
export function koszt(usdH, od, doCzasu) {
  if (!usdH || !Number.isFinite(od) || !Number.isFinite(doCzasu)) return null;
  return +((Math.max(0, doCzasu - od) / 3600000) * usdH).toFixed(3);
}
