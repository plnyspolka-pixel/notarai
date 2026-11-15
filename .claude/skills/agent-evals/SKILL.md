---
name: agent-evals
description: Zbuduj mierzalne testy i release gates dla agentów kodu, browser, voice, video i kosztów. Używaj przy zmianach modelu lub skilla.
---

# agent-evals

Zbuduj golden test sets, deterministic grading tam gdzie możliwe, human ratings dla naturalności/obrazu. Phoenix traces, DeepEval trajektorie, versioned eval datasets. Mierz task success, tool errors, total cost, retry cap, drift, regressions, bezpieczeństwo. Nie raportuj samodzielnie wymyślonych rezultatów. Jeśli zewnętrzny LLM ocenia wynik, kalibruj go przeciw ludziom.

## Definition of done
Powstaje zweryfikowany artefakt z wersjami źródeł i wynikami testów. Brak ukrytych skutków ubocznych oraz deklaracji bez dowodów. Sprawdź powiązane dokumenty w docs/ przed zakończeniem.
