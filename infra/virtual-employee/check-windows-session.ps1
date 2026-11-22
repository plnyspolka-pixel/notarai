#Requires -Version 5.1
# Execute inside pilot VM or via SSM Run Command. Metadata only, no case data.
$ErrorActionPreference = 'Stop'
$agent = Get-Service -Name AmazonSSMAgent -ErrorAction SilentlyContinue
$os = Get-CimInstance Win32_OperatingSystem
$rdp = Get-Service -Name TermService -ErrorAction SilentlyContinue
$sessionList = & quser.exe 2>&1
Write-Output ('OS: ' + $os.Caption)
Write-Output ('SSM: ' + $(if ($agent) { $agent.Status } else { 'missing' }))
Write-Output ('RDP service: ' + $(if ($rdp) { $rdp.Status } else { 'missing' }))
# Never print account names or session identifiers to central logs.
$active = @($sessionList | Where-Object { $_ -match '\sActive\s' }).Count
$disconnected = @($sessionList | Where-Object { $_ -match '\sDisc\s' }).Count
Write-Output ("Active sessions: {0}; disconnected sessions: {1}" -f $active, $disconnected)
if (-not $agent -or $agent.Status -ne 'Running') { exit 2 }
if ($active -lt 1) {
    Write-Warning 'No active interactive desktop. GUI automation cannot be claimed to work unattended.'
    exit 3
}
Write-Output 'GUI session is present; test actual UIA automation before accepting environment.'
