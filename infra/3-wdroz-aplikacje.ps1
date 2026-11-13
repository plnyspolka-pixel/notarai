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
    [string]$Profil = "",
    [string]$Region = "eu-central-1",
    [string]$Konto  = "127621462971",
    [string]$Tag    = "",
    # Adres na alarmy i budzet. Podaj raz - przy kolejnych wdrozeniach
    # CloudFormation zapamieta poprzednia wartosc.
    [string]$Email  = "plnyspolka@gmail.com",
    [int]$Kopie     = 2,
    # Bramka TPay: produkcja albo sandbox (https://openapi.sandbox.tpay.com).
    [string]$TpayApi = "https://api.tpay.com",
    # VAT doliczany do pakietow kredytow: "0" = Fundacja zwolniona z VAT.
    [ValidateSet("0", "0.23")][string]$Vat = "0",
    # Adres API Finance You (dostawca tresci ksiag wieczystych); uzywany, gdy
    # istnieje sekret notarai/finyou.
    [string]$FinyouAdres = "https://finyou.pl",
    # Powiadomienia o zapytaniach - tylko po weryfikacji tozsamosci SES.
    [string]$EmailNadawcy = "",
    [string]$EmailZgloszen = ""
)
$ErrorActionPreference = "Stop"
$korzen = Split-Path -Parent $PSScriptRoot

function Uruchom-Aws {
    # Nie wymuszamy --profile: istniejąca sesja AWS CLI może być z env/SSO.
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    $wynik = & aws @args @opcje
    if ($LASTEXITCODE -ne 0) { throw "Polecenie aws $($args[0]) $($args[1]) nie powiodlo sie (kod $LASTEXITCODE)." }
    return $wynik
}
# Sprawdzenie, ktorego odpowiedz "nie ma" jest oczekiwana. Windows PowerShell 5.1
# przy ErrorActionPreference=Stop zamienia przekierowany stderr programu w blad
# krytyczny, wiec wewnatrz funkcji wracamy do Continue.
function Czy-Aws {
    $ErrorActionPreference = "Continue"
    $opcje = @("--region", $Region)
    if ($Profil) { $opcje += @("--profile", $Profil) }
    & aws @args @opcje 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}
function Wyjscie($stos, $klucz) {
    Uruchom-Aws cloudformation describe-stacks --stack-name $stos `
        --query "Stacks[0].Outputs[?OutputKey=='$klucz'].OutputValue | [0]" --output text
}

Write-Host "== Sprawdzam konto, certyfikat i obraz" -ForegroundColor Cyan
if (-not (Czy-Aws sts get-caller-identity)) {
    throw "AWS CLI nie ma aktywnych uprawnien dla tej sesji. Sprawdz profil AWS_PROFILE lub skonfigurowany dostep CLI; logowanie w przegladarce nie jest sesja CLI."
}
$biezace = Uruchom-Aws sts get-caller-identity --query Account --output text
if ($biezace -ne $Konto) { throw "AWS wskazuje konto $biezace, oczekiwane $Konto. Przerywam." }

if (-not $Tag) { $Tag = (git -C $korzen rev-parse --short=12 HEAD).Trim() }

$stanCert = Uruchom-Aws cloudformation describe-stacks --stack-name notarai-certyfikat --query "Stacks[0].StackStatus" --output text
if ($stanCert -notin @("CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE")) {
    throw "Stos notarai-certyfikat ma status $stanCert. Sprawdz CloudFormation."
}
$certArn = Wyjscie notarai-certyfikat CertyfikatArn
$stanAcm = Uruchom-Aws acm describe-certificate --certificate-arn $certArn --query "Certificate.Status" --output text
if ($stanAcm -ne "ISSUED") { throw "Certyfikat ACM ma status $stanAcm zamiast ISSUED." }
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

# Kredyty sa jedynym sposobem zakupu (tokenomia.py), pakiety kupuje sie przez TPay.
$parametry += "Tokenomia=true"
$parametry += "TpayApi=$TpayApi"
$parametry += "StawkaVat=$Vat"
# Platnosci TPay: sekret notarai/tpay zaklada infra\zapisz-sekret-tpay.ps1
# (client_id, client_secret, kod). Czytamy tylko jego ARN - wartosc zostaje w AWS.
if (Czy-Aws secretsmanager describe-secret --secret-id notarai/tpay) {
    $tpayArn = Uruchom-Aws secretsmanager describe-secret --secret-id notarai/tpay --query ARN --output text
    $parametry += "TpaySekretArn=$tpayArn"
    Write-Host "   platnosci TPay: sekret notarai/tpay, $TpayApi, VAT $Vat"
} else {
    Write-Host "   platnosci TPay: brak sekretu notarai/tpay - zakup pakietow wylaczony" -ForegroundColor Yellow
}

# Ksiegi wieczyste z EKW: sekret notarai/apify zaklada infra\zapisz-sekret-apify.ps1
# (klucz token). Jak przy TPay czytamy tylko ARN - wartosc zostaje w AWS.
if (Czy-Aws secretsmanager describe-secret --secret-id notarai/apify) {
    $apifyArn = Uruchom-Aws secretsmanager describe-secret --secret-id notarai/apify --query ARN --output text
    $parametry += "ApifySekretArn=$apifyArn"
    Write-Host "   ksiegi z EKW: sekret notarai/apify"
} else {
    Write-Host "   ksiegi z EKW: brak sekretu notarai/apify, pobieranie wylaczone" -ForegroundColor Yellow
}

# Finance You jako dostawca tresci KW (ma pierwszenstwo przed Apify): sekret
# notarai/finyou zaklada infra\zapisz-sekret-finyou.ps1, adres API parametrem.
if (Czy-Aws secretsmanager describe-secret --secret-id notarai/finyou) {
    $finyouArn = Uruchom-Aws secretsmanager describe-secret --secret-id notarai/finyou --query ARN --output text
    $parametry += "FinyouSekretArn=$finyouArn"
    $parametry += "FinyouAdres=$FinyouAdres"
    Write-Host "   ksiegi z EKW przez Finance You: sekret notarai/finyou, adres $FinyouAdres"
} else {
    Write-Host "   ksiegi z EKW przez Finance You: brak sekretu notarai/finyou" -ForegroundColor Yellow
}

# Leady z formularzy Meta (meta_leady.py): sekret notarai/meta, JSON z kluczami
# verify, app_secret, token. Zaklada go wlasciciel konta Meta w Secrets Manager.
if (Czy-Aws secretsmanager describe-secret --secret-id notarai/meta) {
    $metaArn = Uruchom-Aws secretsmanager describe-secret --secret-id notarai/meta --query ARN --output text
    $parametry += "MetaSekretArn=$metaArn"
    Write-Host "   leady z Meta: sekret notarai/meta"
} else {
    Write-Host "   leady z Meta: brak sekretu notarai/meta, webhook wylaczony" -ForegroundColor Yellow
}

# SES: wlacz dopiero po weryfikacji adresu lub domeny i wyjsciu z sandbox.
if ($EmailNadawcy) { $parametry += "EmailNadawcy=$EmailNadawcy" }
if ($EmailZgloszen) { $parametry += "EmailZgloszen=$EmailZgloszen" }

Write-Host "== Stos notarai-aplikacja (zwykle 5-10 minut przy pierwszym wdrozeniu)" -ForegroundColor Cyan
Uruchom-Aws cloudformation deploy --stack-name notarai-aplikacja `
    --template-file "$korzen\infra\notarai-aplikacja.yaml" `
    --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai `
    --no-fail-on-empty-changeset `
    --parameter-overrides @parametry | Out-Host

# CloudFormation zakonczył aktualizację; wymagamy jeszcze stabilnej usługi ECS
# i dokładnie tego obrazu, który przygotowano z commita wydania.
$klaster = Wyjscie notarai-aplikacja Klaster
$usluga = Wyjscie notarai-aplikacja Usluga
Uruchom-Aws ecs wait services-stable --cluster $klaster --services $usluga | Out-Null
$definicja = Uruchom-Aws ecs describe-services --cluster $klaster --services $usluga --query "services[0].taskDefinition" --output text
$obraz = Uruchom-Aws ecs describe-task-definition --task-definition $definicja --query "taskDefinition.containerDefinitions[0].image" --output text
if ($obraz.Trim() -ne "$($repo):$Tag") {
    throw "ECS używa obrazu $obraz; oczekiwano $($repo):$Tag. Wydanie przerwane."
}

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
