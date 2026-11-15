---
name: fine-tuning-decision
description: Decyduj, czy potrzebne jest LoRA/SFT/DPO/GRPO, czy wystarczą skille, narzędzia i evals. Używaj dla post-training modeli.
---

# fine-tuning-decision

Najpierw zbuduj evals i popraw tool schemas / retrieval / prompting. Rozważ DSPy prompt optimization. Jeśli są powtarzalne błędy i legalny dataset, dobierz supervised fine-tuning, DPO lub GRPO w Axolotl/LlamaFactory/TRL. Prowadź checkpoint baselines, wyklucz tajne dane bez podstawy, dokonaj oceny licencji bazowego modelu i danych. Tuning postaci wizualnych (LoRA do video) jest innym treningiem niż modelu kodującego.

## Definition of done
Powstaje zweryfikowany artefakt z wersjami źródeł i wynikami testów. Brak ukrytych skutków ubocznych oraz deklaracji bez dowodów. Sprawdź powiązane dokumenty w docs/ przed zakończeniem.
