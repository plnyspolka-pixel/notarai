// notarai-koder: orkiestrator kodera na Cloudflare (Worker + Durable Object z alarmem).
// Zero minut GitHub Actions: start webhookiem GitHuba (push na koder/*) albo ręcznym POST /start,
// wynajem karty SaladCloud z vLLM i agentami na tym samym węźle (tools/agent_factory/koder/wezel.py),
// odbiór paczki wyników, ZAWSZE usunięcie karty (alarm co minutę + termin + cron-strażnik),
// gałęzie agent/* przez API GitHuba (gdy jest GITHUB_TOKEN) albo do odbioru (odbierz.py).
import {
  cialoGrupy, doSprzatniecia, kartyZ, koszt, podpisGithub, rowne, SHA_RE, wpisyDrzewa, wybierzGpu, zdarzeniePush,
} from "./logika.js";

const MINUTA = 60_000;
const json = (status, body) =>
  new Response(JSON.stringify(body, null, 2), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

// ------------------------------------------------------------------ Salad (brama albo wprost)

function salad(env) {
  const org = env.SALAD_ORG || "fi";
  const project = env.SALAD_PROJECT || "default";
  const grupy = `/organizations/${org}/projects/${project}/containers`;
  async function wywolaj(metoda, cel, body, token) {
    let url;
    const headers = new Headers();
    if (env.SALAD_API_KEY && !token) {
      // Tryb bezpośredni: własny klucz Salad w sekretach Workera.
      url = cel.startsWith("api/") ? "https://api.salad.com/api/public/" + cel.slice(4) : "https://" + cel.slice(3);
      headers.set("Salad-Api-Key", env.SALAD_API_KEY);
    } else {
      // Brama Finance You: klucz Salad zostaje w jej Workerze, my podajemy token z render_tokens.
      const u = new URL(env.SALAD_BRAMA_URL);
      u.searchParams.set("cel", cel);
      url = u.href;
      headers.set("x-webhook-secret", token || env.SALAD_BRAMA_TOKEN || "");
    }
    if (body !== undefined) headers.set("content-type", "application/json");
    return fetch(url, { method: metoda, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  }
  async function jsonZ(res, co) {
    const t = await res.text();
    if (!res.ok) throw new Error(`Salad ${co}: HTTP ${res.status} ${t.slice(0, 200)}`);
    return t ? JSON.parse(t) : {};
  }
  return {
    wywolaj,
    klasy: async () => (await jsonZ(await wywolaj("GET", `api/organizations/${org}/gpu-classes`), "gpu-classes")).items || [],
    lista: async () => (await jsonZ(await wywolaj("GET", "api" + grupy), "lista")).items || [],
    utworz: async (body) => jsonZ(await wywolaj("POST", "api" + grupy, body), "tworzenie"),
    grupa: async (n) => {
      const r = await wywolaj("GET", `api${grupy}/${n}`);
      if (r.status === 404) return null;
      return jsonZ(r, "grupa");
    },
    instancje: async (n) => {
      const r = await wywolaj("GET", `api${grupy}/${n}/instances`);
      if (r.status === 404) return [];
      return (await jsonZ(r, "instancje")).instances || [];
    },
    usun: async (n) => {
      const r = await wywolaj("DELETE", `api${grupy}/${n}`);
      if (!r.ok && r.status !== 404) throw new Error(`Salad usuwanie: HTTP ${r.status}`);
      return r.status;
    },
    wezel: (dns, sciezka) => wywolaj("GET", `gw/${dns}/${sciezka}`),
  };
}

// ------------------------------------------------------------------ GitHub (Git Data API)

function github(env) {
  const baza = `https://api.github.com/repos/${env.KODER_REPO}`;
  async function gh(metoda, sciezka, body) {
    const headers = { accept: "application/vnd.github+json", "user-agent": "notarai-koder", "x-github-api-version": "2022-11-28" };
    if (env.GITHUB_TOKEN) headers.authorization = `Bearer ${env.GITHUB_TOKEN}`;
    if (body) headers["content-type"] = "application/json";
    const r = await fetch(baza + sciezka, { method: metoda, headers, body: body ? JSON.stringify(body) : undefined });
    const t = await r.text();
    return { status: r.status, dane: t ? JSON.parse(t) : {} };
  }
  async function galaz(nazwa, sha, pliki, wiadomosc, przedrostek = "") {
    const baseCommit = await gh("GET", `/git/commits/${sha}`);
    if (baseCommit.status !== 200) throw new Error(`GitHub commit ${baseCommit.status}`);
    const { wpisy, bloby } = wpisyDrzewa(pliki, przedrostek);
    for (const b of bloby) {
      const r = await gh("POST", "/git/blobs", { content: b.b64, encoding: "base64" });
      if (r.status !== 201) throw new Error(`GitHub blob ${r.status}`);
      wpisy.push({ path: b.path, mode: "100644", type: "blob", sha: r.dane.sha });
    }
    const drzewo = await gh("POST", "/git/trees", { base_tree: baseCommit.dane.tree.sha, tree: wpisy });
    if (drzewo.status !== 201) throw new Error(`GitHub tree ${drzewo.status} ${JSON.stringify(drzewo.dane).slice(0, 200)}`);
    const kto = { name: "koder (agent)", email: "koder@users.noreply.github.com" };
    const commit = await gh("POST", "/git/commits", { message: wiadomosc, tree: drzewo.dane.sha, parents: [sha], author: kto, committer: kto });
    if (commit.status !== 201) throw new Error(`GitHub commit ${commit.status}`);
    let ref = await gh("POST", "/git/refs", { ref: `refs/heads/${nazwa}`, sha: commit.dane.sha });
    if (ref.status === 422) ref = await gh("PATCH", `/git/refs/heads/${nazwa}`, { sha: commit.dane.sha, force: true });
    if (ref.status !== 201 && ref.status !== 200) throw new Error(`GitHub ref ${ref.status}`);
    return commit.dane.sha;
  }
  return { gh, galaz };
}

// ------------------------------------------------------------------ uwierzytelnienie

async function uprawniony(request, env) {
  const naglowek = request.headers.get("x-webhook-secret") || (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!naglowek || naglowek.length < 32) return false;
  if (env.SALAD_BRAMA_TOKEN && (await rowne(naglowek, env.SALAD_BRAMA_TOKEN))) return true;
  if (env.KODER_TOKEN && (await rowne(naglowek, env.KODER_TOKEN))) return true;
  // Token renderera z public.render_tokens (zakres gpu:salad): rozstrzyga brama Finance You.
  if (!env.SALAD_BRAMA_URL) return false;
  const r = await salad(env).wywolaj("GET", `api/organizations/${env.SALAD_ORG || "fi"}/gpu-classes`, undefined, naglowek);
  return r.ok;
}

// ------------------------------------------------------------------ Worker

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const koder = env.KODER.get(env.KODER.idFromName("koder"));
    if (url.pathname === "/" && request.method === "GET")
      return json(200, { ok: true, usluga: "notarai-koder", opis: "POST /github (webhook), POST /start, GET /stan, GET /wyniki/<przebieg>, POST /stop" });

    if (url.pathname === "/github" && request.method === "POST") {
      const tresc = await request.text();
      if (!(await podpisGithub(env.GITHUB_WEBHOOK_SECRET, tresc, request.headers.get("x-hub-signature-256"))))
        return json(401, { ok: false, error: "zly_podpis" });
      const zdarzenie = request.headers.get("x-github-event");
      if (zdarzenie === "ping") return json(200, { ok: true, pong: true });
      if (zdarzenie !== "push") return json(202, { ok: true, pominieto: zdarzenie });
      let payload;
      try {
        payload = JSON.parse(tresc);
      } catch {
        return json(400, { ok: false, error: "zly_json" });
      }
      const z = zdarzeniePush(payload, env.KODER_REPO);
      if (z.pomin) return json(202, { ok: true, pominieto: z.pomin });
      return koder.fetch("https://do/start", { method: "POST", body: JSON.stringify({ ...z, zrodlo: "webhook" }) });
    }

    if (!(await uprawniony(request, env))) return json(401, { ok: false, error: "brak_uprawnien" });

    if (url.pathname === "/start" && request.method === "POST") {
      let b = {};
      try {
        b = await request.json();
      } catch {
        b = {};
      }
      let sha = String(b.sha || "");
      const ref = String(b.ref || "");
      if (!SHA_RE.test(sha)) {
        if (!/^koder\/[A-Za-z0-9._\/-]{1,100}$/.test(ref)) return json(400, { ok: false, error: "podaj_ref_koder_albo_sha" });
        const r = await github(env).gh("GET", `/commits/${encodeURIComponent(ref).replace(/%2F/g, "/")}`);
        if (r.status !== 200 || !SHA_RE.test(r.dane.sha || "")) return json(404, { ok: false, error: "nie_ma_galezi", status: r.status });
        sha = r.dane.sha;
      }
      let karty;
      try {
        karty = kartyZ(b.karty);
      } catch {
        return json(400, { ok: false, error: "zle_karty" });
      }
      return koder.fetch("https://do/start", {
        method: "POST",
        body: JSON.stringify({ ref: ref || null, sha, karty, minuty: b.minuty, max_usd: b.max_usd, zrodlo: "reczny" }),
      });
    }
    if (url.pathname === "/stan" && request.method === "GET") return koder.fetch("https://do/stan");
    if (url.pathname === "/stop" && request.method === "POST") return koder.fetch("https://do/stop", { method: "POST" });
    const w = /^\/wyniki\/([a-z0-9-]{1,60})$/.exec(url.pathname);
    if (w && request.method === "GET") return koder.fetch(`https://do/wyniki/${w[1]}`);
    return json(404, { ok: false, error: "nie_ma" });
  },

  // Strażnik niezależny od stanu przebiegu: co 5 minut budzi orkiestrator i usuwa każdą grupę
  // kodera po terminie albo osieroconą.
  async scheduled(_event, env, ctx) {
    const koder = env.KODER.get(env.KODER.idFromName("koder"));
    ctx.waitUntil(koder.fetch("https://do/straznik", { method: "POST" }));
  },
};

// ------------------------------------------------------------------ Durable Object

export class Koder {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.s = ctx.storage;
  }

  prefiks() {
    return this.env.SALAD_API_KEY ? "notarai-koder-" : this.env.KODER_GROUP_PREFIX || "finyou-ai-clip-koder-";
  }

  async stan() {
    return (await this.s.get("stan")) || { faza: "bezczynny" };
  }

  async zapisz(st) {
    st.zmieniono = new Date().toISOString();
    await this.s.put("stan", st);
  }

  async dziennik(st, tekst) {
    st.dziennik = [...(st.dziennik || []), `${new Date().toISOString().slice(11, 19)} ${tekst}`].slice(-60);
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/start") return this.start(await request.json());
    if (url.pathname === "/stan") {
      const st = await this.stan();
      return json(200, { ...st, kolejka: (await this.s.get("kolejka")) || null });
    }
    if (url.pathname === "/stop") {
      const st = await this.stan();
      if (st.grupa && !st.usunieto) {
        st.koniec_powod = "stop_reczny";
        st.faza = "usuwanie";
        await this.dziennik(st, "STOP ręczny - usuwam kartę");
        await this.zapisz(st);
        await this.s.setAlarm(Date.now() + 1000);
      }
      await this.s.delete("kolejka");
      return json(200, { ok: true, faza: st.faza });
    }
    if (url.pathname === "/straznik") return this.straznik();
    const w = /^\/wyniki\/([a-z0-9-]+)$/.exec(url.pathname);
    if (w) {
      const n = await this.s.get(`wn:${w[1]}`);
      if (!n) return json(404, { ok: false, error: "brak_wynikow" });
      const czesci = await this.s.get([...Array(n).keys()].map((i) => `w:${w[1]}:${i}`));
      const kawalki = [...Array(n).keys()].map((i) => czesci.get(`w:${w[1]}:${i}`));
      return new Response(new Blob(kawalki), { headers: { "content-type": "application/gzip", "cache-control": "no-store" } });
    }
    return json(404, { ok: false });
  }

  async start(z) {
    const st = await this.stan();
    const aktywne = !["bezczynny", "koniec", "do_odbioru"].includes(st.faza);
    if (aktywne) {
      await this.s.put("kolejka", z); // najwyżej jeden czekający przebieg (najnowszy push wygrywa)
      return json(202, { ok: true, zakolejkowano: z.sha, trwa: st.przebieg });
    }
    const teraz = new Date();
    const przebieg = `cf-${teraz.toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "t")}`;
    const maxUsd = Math.min(Number(this.env.KODER_MAX_USD || 1.5), Number(z.max_usd) || Infinity);
    const minuty = Math.min(Number(this.env.KODER_MINUTES || 120), Number(z.minuty) || Infinity);
    const nowy = {
      faza: "start", przebieg, sha: z.sha, ref: z.ref || null, karty: z.karty || "", zrodlo: z.zrodlo,
      max_usd: maxUsd, minuty, rozpoczeto: teraz.toISOString(), dziennik: [], galezie: [],
    };
    await this.dziennik(nowy, `start ${przebieg}: ${z.ref || ""} ${z.sha.slice(0, 10)} (${z.zrodlo})`);
    await this.zapisz(nowy);
    await this.s.setAlarm(Date.now() + 1000);
    return json(202, { ok: true, przebieg, sha: z.sha, limit_usd: maxUsd });
  }

  async alarm() {
    const st = await this.stan();
    try {
      await this.krok(st);
    } catch (e) {
      await this.dziennik(st, `błąd kroku ${st.faza}: ${String(e?.message || e).slice(0, 300)}`);
      st.bledy = (st.bledy || 0) + 1;
      // Ciągłe błędy w trakcie pracy karty: usuwamy ją, zamiast płacić za niewiadomą.
      if (st.grupa && !st.usunieto && st.bledy >= 15 && st.faza !== "usuwanie") {
        st.faza = "usuwanie";
        st.koniec_powod = "bledy_orkiestratora";
      }
    }
    await this.zapisz(st);
    if (!["bezczynny", "koniec", "do_odbioru"].includes(st.faza)) {
      await this.s.setAlarm(Date.now() + (st.faza === "wypychanie" ? 5000 : MINUTA));
    } else {
      const k = await this.s.get("kolejka");
      if (k) {
        await this.s.delete("kolejka");
        await this.start(k);
      }
    }
  }

  async krok(st) {
    const sal = salad(this.env);
    const teraz = Date.now();
    if (st.faza === "start") {
      // Bez kart nie wynajmujemy karty.
      const r = await github(this.env).gh("GET", `/contents/docs/agent-tasks/kolejka?ref=${st.sha}`);
      const karty = Array.isArray(r.dane) ? r.dane.filter((f) => f.name.endsWith(".md")).map((f) => f.name.slice(0, -3)) : null;
      // Bez odpowiedzi GitHuba (limit zapytań bez tokenu) nie blokujemy: kontrolę kart robi też węzeł.
      if (karty === null) await this.dziennik(st, `lista kart niedostępna (GitHub ${r.status}) - sprawdzi węzeł`);
      const wybrane = karty === null ? (st.karty ? st.karty.split(",") : ["?"]) : st.karty ? st.karty.split(",").filter((k) => karty.includes(k)) : karty;
      if (!wybrane.length) {
        st.faza = "koniec";
        st.koniec_powod = "brak_kart";
        await this.dziennik(st, "brak kart w docs/agent-tasks/kolejka - kończę bez kosztów");
        return;
      }
      // Brama jest wspólna z renderem ai-clip: nie stawiamy karty obok trwającego renderu.
      const grupy = await sal.lista();
      const obce = grupy.filter((g) => String(g.name).startsWith("finyou-ai-clip") && !String(g.name).startsWith(this.prefiks()));
      if (obce.length && !this.env.SALAD_API_KEY) {
        if (teraz - Date.parse(st.rozpoczeto) > 45 * MINUTA) {
          st.faza = "koniec";
          st.koniec_powod = "zajete_przez_render";
        } else await this.dziennik(st, `czekam: trwa render ${obce.map((g) => g.name).join(", ")}`);
        return;
      }
      const gpu = wybierzGpu(await sal.klasy(), {
        priorytety: st.bez_batch ? ["high"] : String(this.env.KODER_PRIORITY || "batch,high").split(","),
        minVram: Number(this.env.KODER_MIN_VRAM || 32), maxHourly: Number(this.env.KODER_MAX_HOURLY || 1),
        maxUsd: st.max_usd, minuty: st.minuty,
      });
      if (!gpu) {
        st.faza = "koniec";
        st.koniec_powod = "brak_karty_w_limicie";
        return;
      }
      const termin = new Date(teraz + gpu.minuty * MINUTA).toISOString();
      const nazwa = this.prefiks() + st.przebieg.slice(3);
      await sal.utworz(cialoGrupy({
        nazwa, gpu, termin, sha: st.sha, repo: this.env.KODER_REPO, przebieg: st.przebieg, karty: st.karty,
        model: this.env.KODER_MODEL, parser: this.env.KODER_PARSER, vllmArgs: this.env.KODER_VLLM_ARGS,
        image: this.env.KODER_IMAGE, kontekst: Number(this.env.KODER_CONTEXT || 65536), rownolegle: Number(this.env.KODER_PARALLEL || 3),
      }));
      Object.assign(st, { faza: "praca", grupa: nazwa, termin, gpu: gpu.nazwa, priorytet: gpu.priorytet, usd_h: gpu.usd_h,
        utworzono: new Date(teraz).toISOString(), limit_usd: gpu.max_usd, karty_liczba: wybrane.length });
      await this.dziennik(st, `utworzono ${nazwa}: ${gpu.nazwa} ${gpu.priorytet} ${gpu.usd_h} USD/h, do ${gpu.minuty} min (najwyżej ${gpu.max_usd} USD), kart ${wybrane.length}`);
      return;
    }

    if (st.faza === "praca") {
      const g = await sal.grupa(st.grupa);
      if (!g) {
        st.usunieto = new Date(teraz).toISOString();
        st.faza = "koniec";
        st.koniec_powod = "grupa_znikla";
        return;
      }
      const inst = (await sal.instancje(st.grupa))[0] || {};
      const stanSalad = inst.state || g.current_state?.status || "pending";
      const dns = String(g.networking?.dns || "").replace("https://", "").replace(/\/$/, "");
      if (stanSalad !== st.salad) await this.dziennik(st, `Salad: ${stanSalad}`);
      st.salad = stanSalad;
      if (stanSalad === "running" && !st.running_od) st.running_od = new Date(teraz).toISOString();
      // Batch bez wolnego węzła: nie czekamy w nieskończoność - usuń i postaw na high.
      const czekaMin = Number(this.env.KODER_BATCH_WAIT_MIN || 15);
      const przydzial = !inst.state && (g.current_state?.instance_status_counts?.allocating_count ?? 0) > 0;
      if (st.priorytet === "batch" && !st.running_od && przydzial && teraz - Date.parse(st.utworzono) > czekaMin * MINUTA) {
        await sal.usun(st.grupa);
        if (await sal.grupa(st.grupa)) return; // usunięcie w toku, następny krok
        await this.dziennik(st, `batch bez węzła przez ${czekaMin} min - usunięto ${st.grupa}, ponawiam na high`);
        Object.assign(st, { faza: "start", bez_batch: true, grupa: null, salad: null });
        st.przebieg = st.przebieg + "h";
        return;
      }
      let wezel = null;
      if (/^[a-z0-9.-]+\.salad\.cloud$/i.test(dns) && stanSalad === "running") {
        const r = await sal.wezel(dns, "stan");
        if (r.ok && (r.headers.get("content-type") || "").includes("json")) wezel = await r.json();
        else await r.body?.cancel();
      }
      if (wezel) {
        if (wezel.faza !== st.wezel?.faza) await this.dziennik(st, `węzeł: ${wezel.faza}`);
        st.wezel = { faza: wezel.faza, zrobione: wezel.zrobione, zadania: wezel.zadania, blad: wezel.blad, ostatnie: (wezel.dziennik || []).slice(-8) };
        if (wezel.faza === "gotowe") {
          await this.odbierz(sal, dns, st);
          st.faza = "usuwanie";
          st.koniec_powod = wezel.blad ? "blad_wezla" : "zrobione";
          await this.usun(sal, st);
          return;
        }
      }
      if (teraz > Date.parse(st.termin)) {
        await this.dziennik(st, "TERMIN minął - odbieram, co jest, i usuwam kartę");
        st.koniec_powod = "termin";
        st.faza = "usuwanie";
        await this.usun(sal, st);
      }
      return;
    }

    if (st.faza === "usuwanie") {
      await this.usun(sal, st);
      return;
    }

    if (st.faza === "wypychanie") {
      const n = await this.s.get(`wn:${st.przebieg}`);
      if (!n) {
        st.faza = "koniec";
        return;
      }
      if (!this.env.GITHUB_TOKEN) {
        st.faza = "do_odbioru";
        await this.dziennik(st, `brak GITHUB_TOKEN - wyniki do odbioru: GET /wyniki/${st.przebieg} (odbierz.py)`);
        return;
      }
      const p = await this.paczka(st.przebieg);
      const zrobione = new Set(st.galezie.map((x) => x.galaz));
      const gh = github(this.env);
      const nastepna = (p.galezie || []).find((x) => !zrobione.has(x.galaz));
      if (nastepna) {
        const sha = await gh.galaz(nastepna.galaz, st.sha, nastepna.pliki, nastepna.wiadomosc);
        st.galezie.push({ galaz: nastepna.galaz, sha });
        await this.dziennik(st, `wypchnięto ${nastepna.galaz}`);
        return;
      }
      const wynikowa = `agent/${st.przebieg}-wyniki`;
      if (!zrobione.has(wynikowa)) {
        const sha = await gh.galaz(wynikowa, st.sha, p.wyniki || {}, `koder: wyniki przebiegu ${st.przebieg} (${p.model || "?"})`,
          `docs/agent-tasks/wyniki/${st.przebieg}/`);
        st.galezie.push({ galaz: wynikowa, sha });
        await this.dziennik(st, `wypchnięto ${wynikowa}`);
      }
      st.faza = "koniec";
    }
  }

  async odbierz(sal, dns, st) {
    const r = await sal.wezel(dns, "wyniki");
    if (!r.ok) {
      await r.body?.cancel();
      await this.dziennik(st, `paczki wyników nie ma (HTTP ${r.status})`);
      return false;
    }
    const bajty = new Uint8Array(await r.arrayBuffer());
    const KAWALEK = 1_000_000;
    const n = Math.ceil(bajty.length / KAWALEK);
    for (let i = 0; i < n; i++) await this.s.put(`w:${st.przebieg}:${i}`, bajty.slice(i * KAWALEK, (i + 1) * KAWALEK));
    await this.s.put(`wn:${st.przebieg}`, n);
    st.wyniki_bajty = bajty.length;
    await this.dziennik(st, `odebrano paczkę wyników (${Math.round(bajty.length / 1024)} KB)`);
    // Zostawiamy wyniki trzech ostatnich przebiegów.
    const lista = [...((await this.s.get("przebiegi")) || []).filter((x) => x !== st.przebieg), st.przebieg];
    for (const stary of lista.slice(0, -3)) {
      const m = (await this.s.get(`wn:${stary}`)) || 0;
      await this.s.delete([`wn:${stary}`, ...[...Array(m).keys()].map((i) => `w:${stary}:${i}`)]);
    }
    await this.s.put("przebiegi", lista.slice(-3));
    return true;
  }

  async paczka(przebieg) {
    const n = await this.s.get(`wn:${przebieg}`);
    const czesci = await this.s.get([...Array(n).keys()].map((i) => `w:${przebieg}:${i}`));
    const blob = new Blob([...Array(n).keys()].map((i) => czesci.get(`w:${przebieg}:${i}`)));
    const tekst = await new Response(blob.stream().pipeThrough(new DecompressionStream("gzip"))).text();
    return JSON.parse(tekst);
  }

  async usun(sal, st) {
    if (!st.usunieto) {
      // Przy terminie albo stopie spróbuj jeszcze zabrać częściowe wyniki.
      if (!(await this.s.get(`wn:${st.przebieg}`)) && st.salad === "running") {
        try {
          const g = await sal.grupa(st.grupa);
          const dns = String(g?.networking?.dns || "").replace("https://", "").replace(/\/$/, "");
          if (dns) await this.odbierz(sal, dns, st);
        } catch {
          /* usunięcie karty jest ważniejsze niż wyniki */
        }
      }
      await sal.usun(st.grupa);
      const g = await sal.grupa(st.grupa);
      if (g) {
        await this.dziennik(st, "DELETE wysłane, grupa jeszcze istnieje - ponowię");
        return;
      }
      st.usunieto = new Date().toISOString();
      st.koszt_max_usd = koszt(st.usd_h, Date.parse(st.utworzono), Date.parse(st.usunieto));
      st.koszt_running_usd = koszt(st.usd_h, Date.parse(st.running_od || st.usunieto), Date.parse(st.usunieto));
      await this.dziennik(st, `karta usunięta; koszt najwyżej ${st.koszt_max_usd} USD (od stanu running: ${st.koszt_running_usd} USD)`);
    }
    st.faza = (await this.s.get(`wn:${st.przebieg}`)) ? "wypychanie" : "koniec";
  }

  async straznik() {
    const st = await this.stan();
    const sal = salad(this.env);
    const biezaca = st.grupa && !st.usunieto ? st.grupa : null;
    const doUsuniecia = doSprzatniecia(await sal.lista(), this.prefiks(), biezaca, Date.now());
    for (const n of doUsuniecia) await sal.usun(n);
    if (!["bezczynny", "koniec", "do_odbioru"].includes(st.faza) && !(await this.s.getAlarm()))
      await this.s.setAlarm(Date.now() + 1000);
    return json(200, { ok: true, usunieto: doUsuniecia, faza: st.faza });
  }
}
