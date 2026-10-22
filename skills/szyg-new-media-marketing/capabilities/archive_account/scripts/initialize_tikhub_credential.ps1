[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$automationRoot = Join-Path $resolvedProject '自动化'
if (-not (Test-Path -LiteralPath $automationRoot)) {
    throw "项目缺少自动化目录，请先安装运行时：$automationRoot"
}

$secureRoot = Join-Path $automationRoot 'secure'
$credentialPath = Join-Path $secureRoot 'tikhub-credential.xml'
New-Item -ItemType Directory -Force -Path $secureRoot | Out-Null

$secureKey = Read-Host '请输入受限 TikHub API Key' -AsSecureString
if ($secureKey.Length -eq 0) {
    throw 'API Key 不能为空。'
}
$secureKey | Export-Clixml -LiteralPath $credentialPath

[pscustomobject]@{
    CredentialPath = $credentialPath
    Encryption = 'Windows DPAPI current user'
} | ConvertTo-Json -Compress
