param(
  [Parameter(Mandatory=$true)][string]$PublicName,
  [Parameter(Mandatory=$true)][string]$NoReplyEmail
)
$ErrorActionPreference = 'Stop'
$publishRoot = Split-Path -Parent $PSScriptRoot
if ($NoReplyEmail -notmatch '^[A-Za-z0-9+_.-]+@users\.noreply\.github\.com$') { throw 'Use your GitHub-provided noreply commit address, not a personal email.' }
if ([string]::IsNullOrWhiteSpace($PublicName) -or $PublicName.StartsWith('-')) { throw 'Choose a public commit display name.' }
if (Test-Path -LiteralPath (Join-Path $publishRoot '.git')) { throw 'Use a fresh repository folder; importing an existing Git history is intentionally refused.' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is needed for this optional command-line method. The publishing guide also describes browser upload.' }
& (Join-Path $PSScriptRoot 'Check-Publish.ps1')
$manifest = Get-Content -LiteralPath (Join-Path $publishRoot 'PUBLISH-MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
function Invoke-LocalGit([string[]]$Arguments) {
  & git -C $publishRoot @Arguments
  if ($LASTEXITCODE -ne 0) { throw 'Git operation failed; no upload was performed.' }
}
Invoke-LocalGit -Arguments @('init','-b','main')
Invoke-LocalGit -Arguments @('config','--local','user.name',$PublicName)
Invoke-LocalGit -Arguments @('config','--local','user.email',$NoReplyEmail)
$files = @($manifest.files.PSObject.Properties.Name) + @('PUBLISH-MANIFEST.json')
foreach ($file in $files) { Invoke-LocalGit -Arguments @('add','--',$file) }
# Explicit process-local identities also override inherited Git author variables.
$env:GIT_AUTHOR_NAME = $PublicName
$env:GIT_AUTHOR_EMAIL = $NoReplyEmail
$env:GIT_COMMITTER_NAME = $PublicName
$env:GIT_COMMITTER_EMAIL = $NoReplyEmail
Invoke-LocalGit -Arguments @('-c','core.hooksPath=NUL','-c','commit.gpgsign=false','commit','-m','Initial public release')
Write-Output 'Local public commit prepared with a noreply email. Nothing was uploaded.'
Write-Output 'Next: add your empty GitHub repository as origin, inspect the staged content, then push as described in PUBLISH-GUIDE.md.'
