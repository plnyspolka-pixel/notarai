# Koszty AWS notarai: przegląd 23.11.2026

Konto 127621462971, prawie wszystko w eu-central-1. Dane z Cost Explorer.

| Miesiąc | Razem (z VAT) | Największe pozycje |
|---|---|---|
| październik 2026 | 127,42 USD | Bedrock Opus 4.6 45,6 · VAT 23,8 · ALB 20,1 · VPC (publiczne IPv4) 19,2 · ECS 9,8 · CloudWatch 8,1 |
| listopad 2026 (1–22) | 84,52 USD | ECS/Fargate 24,9 · VAT 15,8 · ALB 14,2 · publiczne IPv4 13,5 · Bedrock 9,7 · CloudWatch 5,1 |

Stałe koszty to około **100 USD miesięcznie z VAT**, niezależnie od liczby klientów.

## Co było przewymiarowane (pomiar z 14 dni)

- 2 kontenery Fargate po 1 vCPU / 3 GB: CPU średnio **0,2%** (szczyt 31%),
  pamięć w szczycie **8%** (~250 MB). Kontener głównie czeka na Bedrock.
- Container Insights: ~40 płatnych metryk CloudWatch, z których nie korzysta żaden alarm.
- Każdy kontener ma własny publiczny IPv4 (0,005 USD/h, czyli ok. 3,65 USD miesięcznie za sztukę).
- 21 stosów po pilocie Nitro (`notarai-confidential-*`), bez pracy, ale z kluczami KMS.

## Zmiany

| Zmiana | Jak | Oszczędność / mies. |
|---|---|---|
| 1 kontener zamiast 2 | `LiczbaKopii` domyślnie 1 (szablon, workflow, `3-wdroz-aplikacje.ps1`) | ~17 USD Fargate + 3,65 USD IPv4 |
| 0,5 vCPU / 2 GB zamiast 1 vCPU / 3 GB | `Cpu` 512, `Pamiec` 2048 | ~7 USD |
| Container Insights wyłączony | `containerInsights: disabled` | ~4–5 USD |
| Usunięcie pilota Nitro | `infra/usun-pilota-nitro.sh --tak` (wykonane 23.11.2026) | ~4 USD (KMS) |
| **Razem** | | **~35 USD netto, ~43 USD z VAT** |

Z około 100 USD miesięcznie stałych kosztów zostaje około 57 USD. Bedrock płaci
się dalej za faktyczne użycie.

Rozmiar wchodzi przy najbliższym wdrożeniu z `master`. Workflow `wdrozenie.yml`
przekazuje go jawnie. Bez commita zmienisz go w GitHub → Settings → Secrets and
variables → Actions → **Variables**: `NOTARAI_CPU`, `NOTARAI_PAMIEC`,
`NOTARAI_KOPIE`. Przykład: `NOTARAI_KOPIE=2`, gdy klientów przybędzie i
przerwa 1–2 minuty przy awarii przestanie być do przyjęcia.

Koszt jednej kopii: po awarii kontenera albo strefy ECS stawia nowy w 1–2
minuty, a przez ten czas aplikacja nie odpowiada. Wdrożenia idą bez przestoju
(najpierw nowy kontener, potem stary). Alarm `notarai-brak-zdrowych-kontenerow`
wyśle wtedy maila.

## Czego celowo nie ruszam (i dlaczego)

- **Load balancer (ok. 19 USD + 3 adresy IPv4 ok. 11 USD).** Bez niego trzeba by
  przebudować wejście (CloudFront/API Gateway) i obejść limit czasu odczytu
  skanów, które trwają kilka minut. Dużo pracy przy niewielkim zysku. Drobna
  opcja: ALB w 2 podsieciach zamiast 3 (parametr `Podsieci`) to −3,65 USD.
- **NAT Gateway:** nie ma go i nie wolno go dodawać (ok. 35 USD + transfer),
  kontenery wychodzą przez publiczny IP.
- **Bedrock:** model do skanów (Opus 4.6) wybrano po porównaniu jakości
  (SAAS.md). Prompt cache już działa. Tu oszczędza się na liczbie wywołań,
  nie na infrastrukturze.
- **Compute Savings Plan:** po zmniejszeniu Fargate to kilka USD miesięcznie
  rabatu w zamian za roczne zobowiązanie. Ma sens dopiero przy większym ruchu.

## Bez zmian, bo nie kosztują albo kosztują grosze

CloudTrail (`notarai-slad`, pierwszy trail darmowy), AWS Backup (`notarai-kopia`),
4 sekrety w Secrets Manager (~1,60 USD), logi `/ecs/notarai` 2,4 MB z retencją
90 dni, brak dysków EBS i snapshotów, brak instancji EC2.
