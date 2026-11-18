# Integracja V4 z aktualną pracą PR #20

Data: 12.11.2026. Przegląd zmian od baseline pakietu `5e58dd03b79ba1228657ec858b3116e84e5f659d` do `2b2058c72726f0403c691bb6927c901e9db08ee9` wykazał cztery nowsze commity: głosy v2, aktualizację kart postaci i próbki/podglądy produkcji i korektę opisu porównania głosów. V4 dodano na tym nowszym stanie; żadnego z tych materiałów nie nadpisano.

## Pierwszeństwo aktualnych głosów

Źródłem produkcyjnym jest [glosy.md](../glosy.md) i aktualne karty w [pakiet/10_obsada_v2/postacie](../pakiet/10_obsada_v2/postacie). Identyfikatory z rozdziału „Głosy odziedziczone z PR” zamrożonej biblii V4 opisują starszy baseline; **nie wolno ich używać jako aktualnej konfiguracji produkcyjnej**.

| Postać | Aktualny voice_id v2 |
| --- | --- |
| Helena | `0YMlrD87k6Saqi6L1Joy` |
| Marta | `rOIbi11t4PdzPrW90No0` |
| Basia | `vqyfbWoOfYmPoa0QNkKB` |
| Kuba | `l49KzmmcER7qYZfvh1NN` |

Według aktualnego przepisu cała scena powstaje przez **Text to Dialogue**, `eleven_v3`, stability 0.5 i zapisany seed, a następnie jest dzielona według czasów słów. Nie wracać do generowania każdej kwestii bez kontekstu sceny. Do HeyGen trafia czysta mowa; ambience dodaje się w montażu. Przed generowaniem kolejnych odcinków sprawdzić bieżące pliki źródłowe i zatwierdzenie głosów przez człowieka.

Zamrożone źródło tej aktualizacji: [glosy.md przy sprawdzonym head](https://github.com/plnyspolka-pixel/notarai/blob/ae3541627ec6602be7f4ddf668c2e0198e9a03d0/docs/kampania-komputerku/glosy.md), [karta Heleny](https://github.com/plnyspolka-pixel/notarai/blob/ae3541627ec6602be7f4ddf668c2e0198e9a03d0/docs/kampania-komputerku/pakiet/10_obsada_v2/postacie/helena/postac.json).

## Zachowane reguły

- Postacie i scenografia v2 oraz oryginalny sygnet i logotyp z PR.
- Prawdziwe nagrania produktu na danych testowych; brak pseudoekranów udających wdrożenie.
- Znaczek AI przez cały film według aktualnego README; prawna kontrola oznaczeń pozostaje wymagana.
- Nowe kadry i awatary nie uzyskują zgody przez sam fakt istnienia pliku. W sprawdzonej karcie Heleny pola zatwierdzenia kadrów i avatar_id v2 nadal są puste.
- Historyczne sześć scenariuszy i nowe osiem koncepcji mają odrębne numeracje. V4 nie uruchamia poprzednich scenariuszy ani nie pisze nowych dialogów.
- Publikacja wymaga niezależnych kontroli prawnych, notarialnych, produktu i finalnego eksportu. Same próbki głosu lub podgląd odcinka nie odblokowują kampanii.

## Zakres dodanego commitu

`v4/pakiet/` zawiera niezmienione pliki przekazane w czacie. ZIP i jego manifest zachowano jako snapshot z ujawnionymi ograniczeniami. Niniejsza nota ma pierwszeństwo w zakresie aktualnej konfiguracji głosów i sposobu realizacji audio. Przed każdą produkcją porównać aktualny head i źródła, zamiast kopiować historyczne ID z PDF. Kod aplikacji, referencje, konfiguracje postaci, próbki i dotychczasowe scenariusze nie zostały zmienione.
