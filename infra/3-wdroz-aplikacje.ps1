# notarai - etap 3: aplikacja na ECS Fargate za load balancerem z HTTPS
#
# Uruchom z katalogu notarai:
#   powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1
#
# Wymaga: certyfikat ze stosu notarai-certyfikat w statusie ISSUED oraz obraz
# dla biezacego commita w ECR (etap 2). Wdraza do domyslnego VPC konta.
# Ponowne uruchomienie po nowym commicie i etapie 2 podmienia wersje aplikacji
# bez przestoju.
param(
    [string]$Profil = "notarai-admin",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971",
    [string]$Tag    = "",
    # Adres na alarmy i budzet. Podaj raz - przy kolejnych wdrozeniach
    # CloudFormation zapamieta poprzednia wartosc.
    [string]$Email  = "plnyspolka@gmail.com",
    [int]$Kopie     = 2,
    # Cena miesiaca abonamentu w zl brutto. Pusta = zostaje poprzednia.
    [string]$Cena   = "600.00",
    # Tpay w trybie testowym (klucze z sandboxa, bez prawdziwych pieniedzy).
    [switch]$TpaySandbox
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Aws {
    $wynik = & aws @args --profile $Profil --region $Region
    if ($LASTEXITCODE -ne 0) { throw "Polecenie aws $($args[0]) $($args[1]) nie powiodlo sie (kod $LASTEXITCODE)." }
    return $wynik
}
# Sprawdzenie, ktorego odpowiedz "nie ma" jest oczekiwana. Windows PowerShell 5.1
# przy ErrorActionPreference=Stop zamienia przekierowany stderr programu w blad
# krytyczny, wiec wewnatrz funkcji wracamy do Continue.
function Czy-Aws {
    $ErrorActionPreference = "Continue"
    & aws @args --profile $Profil --region $Region 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}
function Wyjscie($stos, $klucz) {
    Uruchom-Aws cloudformation describe-stacks --stack-name $stos `
        --query "Stacks[0].Outputs[?OutputKey=='$klucz'].OutputValue | [0]" --output text
}

Write-Host "== Sprawdzam konto, certyfikat i obraz" -ForegroundColor Cyan
if (-not (Czy-Aws sts get-caller-identity)) {
    throw "Sesja profilu $Profil nie dziala. Odnow ja poleceniem:`n  aws login --profile $Profil --region $Region`nLink z terminala otworz w tym oknie Chrome, w ktorym jestes zalogowana do konsoli AWS."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "Profil $Profil wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

if (-not $Tag) { $Tag = (git -C $korzen rev-parse --short=12 HEAD).Trim() }

$stanCert = Uruchom-Aws cloudformation describe-stacks --stack-name notarai-certyfikat --query "Stacks[0].StackStatus" --output text
if ($stanCert -ne "CREATE_COMPLETE") {
    throw "Stos notarai-certyfikat ma status $stanCert. Dodaj rekord CNAME z etapu 1 w az.pl i poczekaj na ISSUED."
}
$certArn = Wyjscie notarai-certyfikat CertyfikatArn
$repo    = Wyjscie notarai-budowanie RepozytoriumUri
$nazwaRepo = $repo.Split("/", 2)[1]

if (-not (Czy-Aws ecr describe-images --repository-name $nazwaRepo --image-ids "imageTag=$Tag")) { throw "Brak obrazu $($repo):$Tag w ECR. Uruchom najpierw etap 2." }

# Argumenty z przecinkiem zawsze w cudzyslowie: bez niego PowerShell robi z nich
# tablice i przekazuje do aws jako osobne slowa.
$vpc = Uruchom-Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
if (-not $vpc -or $vpc -eq "None") { throw "Brak domyslnego VPC w regionie $Region." }
$podsieci = (Uruchom-Aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" "Name=default-for-az,Values=true" --query "Subnets[].SubnetId" --output text) -split "\s+" | Where-Object { $_ }
if ($podsieci.Count -lt 2) { throw "Load balancer potrzebuje co najmniej dwoch podsieci, znaleziono $($podsieci.Count)." }
Write-Host "   obraz $Tag, VPC $vpc, podsieci: $($podsieci.Count)"

$parametry = @(
    "VpcId=$vpc"
    "Podsieci=$($podsieci -join ',')"
    "RepozytoriumUri=$repo"
    "TagObrazu=$Tag"
    "CertyfikatArn=$certArn"
    "LiczbaKopii=$Kopie"
)
# Pustego adresu nie wysylamy - CloudFormation zostawi wtedy poprzedni.
if ($Email) { $parametry += "EmailAlarmowy=$Email" }

# Logowanie uzytkownikow jest opcjonalne: gdy stos notarai-logowanie istnieje,
# przekazujemy jego identyfikatory do aplikacji.
if (Czy-Aws cloudformation describe-stacks --stack-name notarai-logowanie) {
    $pula = Wyjscie notarai-logowanie PulaId
    $klientId = Wyjscie notarai-logowanie KlientId
    $parametry += "PulaLogowania=$pula"
    $parametry += "KlientLogowania=$klientId"
    Write-Host "   logowanie uzytkownikow: pula $pula"
} else {
    Write-Host "   logowanie uzytkownikow: brak stosu notarai-logowanie, zostaje sam token kancelarii" -ForegroundColor Yellow
}

# Platnosci Tpay: sekret notarai/tpay zaklada sie recznie w konsoli (klucze
# client_id i client_secret). Czytamy tylko jego ARN - wartosc zostaje w AWS.
if (Czy-Aws secretsmanager describe-secret --secret-id notarai/tpay) {
    $tpayArn = Uruchom-Aws secretsmanager describe-secret --secret-id notarai/tpay --query ARN --output text
    $parametry += "TpaySekretArn=$tpayArn"
    $parametry += "TpaySrodowisko=$(if ($TpaySandbox) { 'sandbox' } else { 'produkcja' })"
    if ($Cena) { $parametry += "CenaAbonamentu=$Cena" }
    Write-Host "   platnosci Tpay: sekret notarai/tpay$(if ($TpaySandbox) { ', SANDBOX' })$(if ($Cena) { ", cena $Cena zl" })"
} else {
    Write-Host "   platnosci Tpay: brak sekretu notarai/tpay, platnosci wylaczone" -ForegroundColor Yellow
}

Write-Host "== Stos notarai-aplikacja (zwykle 5-10 minut przy pierwszym wdrozeniu)" -ForegroundColor Cyan
Uruchom-Aws cloudformation deploy --stack-name notarai-aplikacja `
    --template-file "$korzen\infra\notarai-aplikacja.yaml" `
    --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai `
    --no-fail-on-empty-changeset `
    --parameter-overrides @parametry | Out-Host

$alb = Wyjscie notarai-aplikacja AdresLoadBalancera
$domena = Uruchom-Aws acm describe-certificate --certificate-arn $certArn --query "Certificate.DomainName" --output text

Write-Host ""
Write-Host "== Aplikacja wdrozona" -ForegroundColor Green
Write-Host "   Dodaj w az.pl rekord CNAME:"
Write-Host "     Nazwa : $domena"
Write-Host "     Cel   : $alb"
Write-Host ""
Write-Host "   Token panelu admina odczytasz w konsoli AWS:"
Write-Host "     Secrets Manager -> notarai/admin-token -> Retrieve secret value"
if ($Email) {
    Write-Host ""
    Write-Host "   AWS wyslal na $Email prosbe o potwierdzenie subskrypcji alarmow." -ForegroundColor Yellow
    Write-Host "   Bez kliniecia linku z tej wiadomosci alarmy nie dojda."
}
