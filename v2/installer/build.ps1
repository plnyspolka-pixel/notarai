param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot
$output = (New-Item -ItemType Directory -Force -Path $OutputDirectory).FullName
$stage = Join-Path ([IO.Path]::GetTempPath()) ('notarai-v2-' + [Guid]::NewGuid())
$payload = Join-Path $stage 'payload'
$runtime = Join-Path $payload 'runtime'
$compiler = Join-Path $stage 'inno'

function Receive-CheckedFile($Uri, $Destination, $Sha256) {
    Invoke-WebRequest -Uri $Uri -OutFile $Destination
    if ((Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -ne $Sha256) {
        throw "Invalid SHA-256 for $Uri"
    }
}

try {
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $embedded = Join-Path $stage 'python.zip'
    Receive-CheckedFile 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip' `
        $embedded '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
    Expand-Archive -LiteralPath $embedded -DestinationPath $runtime
    @('python314.zip', '.', '..', 'import site') |
        Set-Content -LiteralPath (Join-Path $runtime 'python314._pth') -Encoding ascii
    & python -c "import struct, sys; assert sys.version_info[:2] == (3, 14) and struct.calcsize('P') == 8"
    if ($LASTEXITCODE -ne 0) { throw 'Building requires a 64-bit Python 3.14 toolchain.' }
    & python -m pip --disable-pip-version-check install --only-binary=:all: --no-compile `
        --target (Join-Path $runtime 'Lib\site-packages') --constraint (Join-Path $source 'requirements.txt') `
        fastapi uvicorn cryptography pywin32 python-docx boto3 httpx websockets
    if ($LASTEXITCODE -ne 0) { throw 'Vendoring V2 dependencies failed.' }

    Copy-Item -LiteralPath (Join-Path $source 'worker') -Destination $payload -Recurse
    Get-ChildItem -LiteralPath (Join-Path $payload 'worker') -Filter '__pycache__' -Directory -Recurse |
        Remove-Item -Recurse -Force
    # Deterministic rules shared with V1 (code only): the fee engine and amounts in words.
    $shared = New-Item -ItemType Directory -Path (Join-Path $payload 'worker\_v1') -Force
    @('taksa.py', 'slownie.py') | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path (Split-Path $source) $_) -Destination $shared
    }
    @('launch.py', 'preview_instance.py', 'preset.json') | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $_) -Destination $payload
    }
    & (Join-Path $runtime 'python.exe') -X utf8 -c "import docx, win32crypt, uvicorn; from worker.api import create_app; from worker.domain import fee_catalog; assert fee_catalog()['rodzaje']"
    if ($LASTEXITCODE -ne 0) { throw 'The embedded runtime failed to import the preview.' }

    $innoSetup = Join-Path $stage 'innosetup-6.4.3.exe'
    Receive-CheckedFile 'https://github.com/jrsoftware/issrc/releases/download/is-6_4_3/innosetup-6.4.3.exe' `
        $innoSetup 'f3c42116542c4cc57263c5ba6c4feabfc49fe771f2f98a79d2f7628b8762723b'
    $setup = Start-Process -FilePath $innoSetup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$compiler`"" `
        -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Inno Setup returned code $($setup.ExitCode)." }
    $iscc = Join-Path $compiler 'ISCC.exe'
    & $iscc "/DPayloadDir=$payload" "/O$output" (Join-Path $PSScriptRoot 'NotarAI-V2.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Building NotarAI-V2-Setup-x64.exe failed.' }
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
