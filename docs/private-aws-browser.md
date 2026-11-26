# Prywatna przeglądarka AWS (jedno konto)
Osobny stos `notarai-private-browser` w eu-central-1, korzystający z już istniejącego `notarai-egress`. Nie zmienia EIP, NAT, routingu ani aplikacji NotarAI. Nie jest to VPN urządzenia. Chromium (LinuxServer/Selkies) działa na prywatnej EC2, wejście przez HTTPS ALB i osobny Cognito z MFA. Publiczny port przeglądarki nie jest wystawiany bezpośrednio. Wartości IP, ARN i identyfikatory wyłącznie poza repozytorium. Przeznaczenie: prywatna sesja i publiczny internet; nie rejestry urzędowe ani dane kancelarii. 
## Wymagania
- Istniejący NAT włączony w `notarai-egress` i sprawdzony adres. Według NA-18 jest to adres TEST; nie uznawać go za adres rejestrów PROD.
- Dwie publiczne podsieci ALB w różnych AZ w tym samym VPC; prywatna podsieć odczytywana ze stosu egress.
- Własny hostname, certyfikat ACM w eu-central-1 oraz DNS alias/CNAME do ALB (wyjście DnsTarget; po pierwszym utworzeniu ustawić DNS i powtórzyć skrypt).
- Dedykowany Cognito User Pool z jednym użytkownikiem administratora, MFA ON, bez samorejestracji i z klientem OAuth confidential z sekretem, grant authorization code, scope openid i callback `https://HOST/oauth2/idpresponse`. Nie używać produkcyjnego poola kancelarii. Nie pobierać sekretu do repozytorium.
- Zweryfikowany digest obrazu `lscr.io/linuxserver/chromium@sha256:...`. Nie używać latest.
- Uprawniony profil AWS do nowego stosu CloudFormation, EC2, ALB i odczytów Cognito / istniejącego stosu. Obecna rola GitHub aplikacji jest ograniczona do notarai-aplikacja i nie wystarcza. Nie rozszerzać jej automatycznie.
- Konfiguracja przez zmienne środowiskowe: BROWSER_HOSTNAME, BROWSER_CERT_ARN, BROWSER_POOL_ARN, BROWSER_POOL_CLIENT, BROWSER_POOL_DOMAIN, BROWSER_PUBLIC_SUBNETS (lista rozdzielona przecinkami), BROWSER_CLIENT_CIDR (zatwierdzony IPv4 CIDR użytkownika), BROWSER_IMAGE.
## Wdrożenie
```bash
bash infra/deploy-private-browser.sh
```
Skrypt odmawia, jeśli NAT wyłączony, nie ma unikalnej trasy lub EIP nie zgadza się; sprawdza MFA i brak samorejestracji, zdrowie celu ALB i przekierowanie niezalogowanego klienta. Samo scalenie nie daje dowodu wdrożenia. Workflow może wdrażać po scaleniu, gdy ustawiono dedykowaną rolę OIDC i konfigurację. Nie publikuje adresów infrastruktury w logach. Nie przyznaje instancji roli IAM; IMDSv2 tylko host (hop 1), blokada sieci prywatnych w DOCKER-USER, IPv6 wyłączony, brak trwałego profilu Chromium. Po restarcie kontener nie startuje automatycznie; odtworzyć instancję i ponownie zweryfikować. Nie zmieniać podsieci ani firewalla na współdzielonych hostach. 
## Odbiór
Z uprawnionej sieci otworzyć HTTPS na komputerze i telefonie, zalogować się, sprawdzić klawiaturę i WebSocket, w zdalnym Chromium wejść na checkip.amazonaws.com i porównać z AdresEgress. Sprawdzić brak dostępu do IMDS i prywatnych adresów, brak dostępu anonimowego oraz zatrzymanie ruchu po wyłączeniu NAT. Nie używać produkcyjnych danych ani przekazywać linku innym. Uwaga: testy runtime i mobile jeszcze niewykonane. Nowa EC2, ALB i działający NAT generują koszty. Usunięcie wyłącznie stosu notarai-private-browser nie usuwa adresu EIP. 
