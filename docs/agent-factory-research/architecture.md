# Agent Factory R&D — architektura logiczna

Opis koncepcyjny. **Nie oznacza gotowych integracji ani wdrożenia.**

## Przepływ

    [Operator approves experiment + budget + region]
                    |
       [Experiment Registry + Policy Engine]
                    |
      [Dataset Foundry / Benchmarks (synthetic)]
                    |
           [Scheduler / GPU Allocator]
             |          |         |
          [Coder]     [Video]   [Voice]
         sandbox      ComfyUI    realtime
             |          |         |
             +---[Artifact Registry]---+
                         |
             [Independent Evaluators]
                         |
            [Evidence + Cost + Safety]
                         |
              [Human-reviewed PR]

## Komponenty i granice zaufania

- Experiment Registry: task ID, git SHA, model hash, dataset hash, prompt version, approval, region, spending cap, TTL, state. Dla długich jobów oceniaj Temporal jako osobny komponent.
- GPU Allocator: pluggable SkyPilot albo dstack, bez publicznego endpointu vLLM, z zatwierdzeniem regionu/dostawcy. Brak automatycznego provisioning na teraz.
- Runtime: istniejący Secure Agent Factory runner; osobny sandbox/VM dla OpenHands/Prime Agent, browser i wideo. Nie przenoś uprawnień między rolami.
- Dataset Foundry: NeMo Data Designer / Agent-World / Verifiers; tylko fikcyjne stany i dane o udokumentowanym źródle.
- Evaluator: testy deterministyczne, VBench dla wideo oraz niezależna ocena semantyczna; nie wolno agentowi modyfikować evaluatora w trakcie testu.
- Evolution: autoresearch / ShinkaEvolve / DSPy/GEPA; uruchom tylko dla jawnych zakresów parametrów i kodu.
- Artifact Store: co najmniej hashes, seedy, wersje modeli, koszty i wynik; nie przechowuj surowych transkryptów zawierających dane osobowe.
- Telemetry: Langfuse / Promptfoo w trybie metadata-only; oddzielne tajne tokeny poza workerem i logiem.
- Human gate: akceptuje nowe modele/wersje, dane, limity GPU i promowanie wyników; brak auto-merge/deploy.

## Minimalne zdarzenia

- experiment.created
- experiment.approved
- worker.allocated
- worker.started
- artifact.created
- evaluation.completed
- experiment.failed
- experiment.completed
- experiment.cancelled

Zdarzenia powinny zawierać ID, typ, timestamp, sanitized metadata, correlation ID i wersję schematu. Nie powinny zawierać promptów klientów, numerów KW, PESEL, kluczy ani niezanonimizowanych screenshotów.

## Ujednolicony run manifest (propozycja)

    {
      "schema_version": 1,
      "run_id": "synthetic-run-001",
      "experiment_id": "EXP-01",
      "repo_sha": "REPLACE_WITH_COMMIT_SHA",
      "model_ref": "REPLACE_WITH_PINNED_MODEL",
      "dataset_sha256": "REPLACE_WITH_HASH",
      "seed": 42,
      "gpu_type": null,
      "gpu_region": null,
      "approved_budget_pln": 0,
      "actual_cost_pln": null,
      "status": "proposed",
      "policy_violations": []
    }

## Zasady niepodlegające optymalizacji

Żaden agent nie może modyfikować w trakcie eksperymentu: zasad egress, policy engine, listy zatwierdzonych operacji, limitów kosztów, danych testowych, weryfikatora, kluczy, ustawień audytu ani zasad retencji. Badane zmiany w tych elementach wymagają osobnego PR i niezależnej oceny.

Obowiązują nadrzędne ograniczenia root CLAUDE.md i docs/agent-factory.md: eu-central-1 dla regulated workloads, brak danych klientów, brak nieautoryzowanych modeli/dostawców i brak wdrażania produkcyjnego.
