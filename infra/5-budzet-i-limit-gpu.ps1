# 5-budzet-i-limit-gpu.ps1 - jedno uruchomienie, dwa efekty:
#  1. alarm budzetowy AWS dla Amazon Bedrock (e-mail przy 80% wydanych i 100% prognozy),
#  2. wniosek o limit instancji GPU spot (rodzina G) w eu-central-1 pod stanowisko ComfyUI
#     (infra/notarai-gpu-komfy.yaml). Nowe konta maja limit 0 vCPU, bez wniosku pod nie wystartuje.
# Wymaga: AWS CLI zalogowane jak do 3-wdroz-aplikacje.ps1 (ten sam profil operatora).
# Nic nie kosztuje: budzet jest darmowy (do 2 budzetow), wniosek o limit tez.
param(
    [string]$Email = (Read-Host "E-mail na alarmy budzetowe"),
    [int]$LimitUsd = 60,
    [int]$GpuVcpu = 8,        # 8 vCPU = jedna g6.2xlarge albo dwie g6.xlarge naraz
    [string]$Region = "eu-central-1"
)
$ErrorActionPreference = "Stop"
$tu = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "1/3 Kto jest zalogowany:" -ForegroundColor Cyan
aws sts get-caller-identity --output table

Write-Host "2/3 Budzet Bedrock ($LimitUsd USD/mies., alarmy na $Email)" -ForegroundColor Cyan
aws cloudformation deploy `
    --stack-name notarai-budzet `
    --template-file (Join-Path $tu "notarai-budzet.yaml") `
    --parameter-overrides "Email=$Email" "LimitUsd=$LimitUsd" `
    --region $Region
Write-Host "   Potwierdz subskrypcje w mailu od AWS Notifications." -ForegroundColor Yellow

Write-Host "3/3 Wniosek o limit GPU spot (All G and VT Spot Instance Requests -> $GpuVcpu vCPU)" -ForegroundColor Cyan
$kod = "L-3819A6DF"   # kod kwoty: All G and VT Spot Instance Requests (sprawdz w Service Quotas, gdy odrzuci)
$obecny = aws service-quotas get-service-quota --service-code ec2 --quota-code $kod --region $Region --query "Quota.Value" --output text
Write-Host "   obecny limit: $obecny vCPU"
if ([double]$obecny -ge $GpuVcpu) {
    Write-Host "   limit juz wystarcza - wniosek pominiety." -ForegroundColor Green
} else {
    aws service-quotas request-service-quota-increase --service-code ec2 --quota-code $kod --desired-value $GpuVcpu --region $Region --output table
    Write-Host "   AWS odpowiada zwykle w 1-2 dni (mail). Potem: aws cloudformation deploy --stack-name notarai-gpu-komfy ..." -ForegroundColor Yellow
}
Write-Host "Gotowe." -ForegroundColor Green
