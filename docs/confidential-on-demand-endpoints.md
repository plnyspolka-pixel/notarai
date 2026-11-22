# Endpointy Interface na żądanie (shared fabric)

Stan: kod, szablon i testy są na gałęzi; **nic z tego nie jest wdrożone**
i nie było jeszcze sprawdzone na żywo. Pierwsze uruchomienie wymaga
obserwacji (patrz „Do sprawdzenia na żywo”).

## Po co

Sieć `notarai-confidential-shared-fabric` nie ma NAT ani IGW. Host Nitro
dosięga ECS, ECR, KMS i SQS tylko przez siedem endpointów Interface, a te
są płatne za każdą rozpoczętą godzinę, także bez ruchu (ok. 0,084 USD/h,
ok. 61 USD/mies. w jednej AZ). Automat trzyma je wyłączone, gdy żadna
kancelaria nie ma pracy.

## Jak działa

- `infra/notarai-confidential-shared-fabric.yaml` ma parametr
  `EnableCoreInterfaceEndpoints` (domyślnie `true`). `false` zostawia VPC,
  podsieć, grupy bezpieczeństwa i bezpłatne endpointy Gateway.
- `confidential/fabric_scaler.py` (Lambda z
  `infra/notarai-confidential-fabric-scaler.yaml`, co minutę):
  - praca = wiadomość widoczna, przetwarzana lub opóźniona w kolejce FIFO
    któregokolwiek tenanta z listy albo działający task w klastrze shared;
  - jest praca, endpointów brak: jedna zmiana parametru stacka na `true`;
  - brak pracy, endpointy są i minęło `MinOnSeconds` (domyślnie 50 min,
    bo rozpoczęta godzina i tak jest zapłacona): zmiana na `false`;
  - stack w trakcie zmiany: czeka; stack po rollbacku: `needs_review`
    i żadnych kolejnych prób;
  - nie da się odczytać kolejki, listy tasków albo stanu stacka: nic nie
    zmienia.
- `confidential/dispatch.py` w trybie shared przed `RunTask` sprawdza, czy
  wszystkie siedem endpointów jest `available`. Jeśli nie, zwraca
  `fabric_warming` i nie uruchamia płatnej instancji. Pierwsze zlecenie po
  przerwie startuje więc kilka minut później.

## Uprawnienia automatu

Rola `notarai-confidential-fabric-scaler` może: odczytać liczniki kolejek
`notarai-confidential-*.fifo`, wylistować taski klastra shared oraz
wykonać `DescribeStacks` i `UpdateStack` wyłącznie na stacku shared fabric.
Tworzenie i usuwanie endpointów jest dozwolone tylko wtedy, gdy wywołuje
je CloudFormation (`aws:CalledVia`), nie bezpośrednio. Nie ma dostępu do
S3, KMS, DynamoDB, treści kolejek, IAM, tras, bram ani grup bezpieczeństwa.
Wyłączenie endpointów nie odsłania danych; to wyłącznie decyzja kosztowa.

## Wdrożenie (po udanym E2E na Nitro)

1. `python scripts/package_confidential_dispatch.py --output <zip>`, wgrać
   zip do bucketu artefaktów pod kluczem z sumą SHA-256.
2. Stack `notarai-confidential-fabric-scaler`: `Tenants=pilot02,pilot03`,
   `CodeBucket`, `CodeKey`, `ScalerEnabled=false`, `CAPABILITY_NAMED_IAM`.
3. Jednorazowo wywołać Lambdę ręcznie i obejrzeć zwracany stan.
4. `ScalerEnabled=true` dopiero po kroku 3.
5. Stacki `notarai-confidential-dispatch-<tenant>` z `SharedCompute=true`
   wymagają teraz `SharedVpcId`.

## Do sprawdzenia na żywo

- Czy lista akcji EC2/Route 53 dla CloudFormation wystarcza do utworzenia
  endpointu z prywatnym DNS (zestaw przyjęty z dokumentacji, niezweryfikowany).
- Czas od zmiany parametru do `available` dla wszystkich siedmiu endpointów.
- Zachowanie przy zleceniu, które przychodzi w chwili wyłączania: task może
  nie wystartować, lease schedulera trzyma 15 minut, potem ponowna próba.

## Znane ograniczenia

- Zlecenie, którego worker nie potrafi przetworzyć, trzyma endpointy
  włączone do wygaśnięcia wiadomości (retencja kolejki 24 h, ok. 2 USD)
  albo do przeniesienia do DLQ po trzech próbach. DLQ nie liczy się jako praca.
- Scheduler tenantów wymaga `ReservedConcurrentExecutions: 1`, czego konto
  z limitem 10 współbieżnych wykonań Lambda nie przyjmuje. Automat
  endpointów nie rezerwuje współbieżności, bo CloudFormation i tak
  wykonuje jedną zmianę stacka naraz.
