# notarai - wnioski o zwiekszenie limitow AWS (Service Quotas) pod testy
# na wiekszej liczbie kancelarii.
#
# Uruchom z katalogu notarai, z profilem, ktory ma uprawnienia administratora
# (np. notarai-admin):
#   powershell -ExecutionPolicy Bypass -File infra\zwieksz-limity.ps1 -Profil notarai-admin
#     -> tylko pokazuje obecne limity i to, o co skrypt by wnioskowal
#   powershell -ExecutionPolicy Bypass -File infra\zwieksz-limity.ps1 -Profil notarai-admin -Wyslij
#     -> sklada wnioski
#
# Co obejmuje:
#  - Bedrock: tokeny i zapytania na minute dla modelu z config.MODEL
#    (domyslnie profil eu.anthropic.claude-opus-4-6-v1, czyli limity
#    "Cross-region model inference ... Claude Opus 4.6"),
#  - Fargate: liczba vCPU On-Demand (ECS: LiczbaKopii x Cpu, a przy
#    wdrozeniu chwilowo 2x tyle, bo MaximumPercent = 200).
# Wszystko w eu-central-1. Wniosek nie zmienia infrastruktury ani kosztow
# sam w sobie - placisz dopiero za faktyczne zuzycie.
param(
    [string]$Profil = "",
    [string]$Region = "eu-central-1",
    # Fragment nazwy modelu w nazwie limitu Bedrock.
    [string]$Model = "Claude Opus 4.6",
    # Ile razy wiecej niz obecny limit Bedrock.
    [int]$MnoznikBedrock = 4,
    # Docelowa liczba vCPU Fargate (6 kopii x 2 vCPU x 2 przy wdrozeniu = 24).
    [int]$VcpuFargate = 32,
    [switch]$Wyslij
)
$ErrorActionPreference = "Stop"

function Aws-Json {
    $ErrorActionPreference = "Continue"
    $opcje = @("--region", $Region, "--output", "json")
    if ($Profil) { $opcje += @("--profile", $Profil) }
    $wynik = & aws @args @opcje 2>&1
    if ($LASTEXITCODE -ne 0) { throw "aws $($args[0]) $($args[1]): $wynik" }
    return ($wynik | Out-String | ConvertFrom-Json)
}

function Limity([string]$Usluga) {
    $wszystkie = @()
    $token = $null
    do {
        $arg = @("service-quotas", "list-service-quotas", "--service-code", $Usluga)
        if ($token) { $arg += @("--starting-token", $token) }
        $s = Aws-Json @arg
        $wszystkie += $s.Quotas
        $token = $s.NextToken
    } while ($token)
    return $wszystkie
}

function Otwarty-Wniosek($l) {
    $h = Aws-Json service-quotas list-requested-service-quota-change-history-by-quota `
        --service-code $l.ServiceCode --quota-code $l.QuotaCode
    return @($h.RequestedQuotas | Where-Object { $_.Status -in @("PENDING", "CASE_OPENED") }).Count -gt 0
}

Write-Host "== Konto i region" -ForegroundColor Cyan
$ja = Aws-Json sts get-caller-identity
Write-Host "   $($ja.Arn)  ($Region)"

$plan = @()

Write-Host "== Bedrock: limity dla '$Model'" -ForegroundColor Cyan
$bedrock = Limity "bedrock" | Where-Object {
    $_.QuotaName -like "*$Model*" -and
    $_.QuotaName -match "(tokens|requests) per minute" -and
    $_.QuotaName -match "Cross-region"
}
if (-not $bedrock) { Write-Host "   Nie znaleziono limitow - sprawdz parametr -Model." -ForegroundColor Yellow }
foreach ($l in $bedrock) {
    $plan += [pscustomobject]@{ L = $l; Cel = [double]$l.Value * $MnoznikBedrock }
}

Write-Host "== Fargate: vCPU On-Demand" -ForegroundColor Cyan
$fargate = Limity "fargate" | Where-Object { $_.QuotaName -like "*On-Demand vCPU*" }
foreach ($l in $fargate) {
    if ([double]$l.Value -lt $VcpuFargate) { $plan += [pscustomobject]@{ L = $l; Cel = [double]$VcpuFargate } }
    else { Write-Host "   $($l.QuotaName): $($l.Value) - wystarczy" }
}

Write-Host ""
Write-Host "== Plan" -ForegroundColor Cyan
foreach ($p in $plan) {
    $l = $p.L
    $uwagi = if (-not $l.Adjustable) { "NIE DA SIE przez Service Quotas -> wniosek w AWS Support" } else { "" }
    "{0,-80} {1,14} -> {2,14}  {3}" -f $l.QuotaName, $l.Value, $p.Cel, $uwagi | Write-Host
}

if (-not $Wyslij) {
    Write-Host ""
    Write-Host "Tryb podgladu. Dodaj -Wyslij, zeby zlozyc wnioski." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "== Skladam wnioski" -ForegroundColor Cyan
foreach ($p in $plan) {
    $l = $p.L
    if (-not $l.Adjustable) { Write-Host "   pomijam (nieregulowany): $($l.QuotaName)" -ForegroundColor Yellow; continue }
    if (Otwarty-Wniosek $l) { Write-Host "   juz czeka wniosek: $($l.QuotaName)"; continue }
    try {
        $r = Aws-Json service-quotas request-service-quota-increase `
            --service-code $l.ServiceCode --quota-code $l.QuotaCode --desired-value $p.Cel
        Write-Host "   $($r.RequestedQuota.Status): $($l.QuotaName) -> $($p.Cel)" -ForegroundColor Green
    } catch {
        Write-Host "   BLAD: $($l.QuotaName): $_" -ForegroundColor Red
    }
}
Write-Host ""
Write-Host "Status wnioskow: konsola Service Quotas > Quota request history ($Region)"
Write-Host "albo: aws service-quotas list-requested-service-quota-change-history --region $Region"
