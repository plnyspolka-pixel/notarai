---
name: coding-agent-engineering
description: Buduj autonomicznych agentów programujących i mierz realną skuteczność na repo. Używaj dla agent coding i Claude Code.
---

# coding-agent-engineering

Użyj metoda superpowers: plan->mały diff->test->review->verify. Zawsze izolacja branch/worktree, sandbox bez prod secrets, preflight git status. Zrób zadania A/B dla Claude Code+model komercyjny i Claude Code+vLLM Anthropic Messages; skonfiguruj tool parser właściwy dla modelu. Nie zakładaj identycznej jakości. Porównuj przy równych narzędziach: pass test, tool correctness, cost, latency, PR acceptance.

## Definition of done
Powstaje zweryfikowany artefakt z wersjami źródeł i wynikami testów. Brak ukrytych skutków ubocznych oraz deklaracji bez dowodów. Sprawdź powiązane dokumenty w docs/ przed zakończeniem.
