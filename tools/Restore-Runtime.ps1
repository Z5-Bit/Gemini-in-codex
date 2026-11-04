param([Parameter(Mandatory=$true)][string]$ReleaseZip)
$ErrorActionPreference = 'Stop'
function Get-PublishHash([string]$Path) {
  $stream = [IO.File]::OpenRead($Path); $algorithm = [Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
  finally { $stream.Dispose(); $algorithm.Dispose() }
}
$publishRoot = Split-Path -Parent $PSScriptRoot
$release = Get-Content -LiteralPath (Join-Path $publishRoot 'RELEASE-ARTIFACT.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$archivePath = (Resolve-Path -LiteralPath $ReleaseZip).Path
if ((Get-PublishHash $archivePath) -ne $release.sha256) { throw 'Release ZIP checksum mismatch.' }
$runtime = Get-Content -LiteralPath (Join-Path $publishRoot 'RUNTIME-MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
  foreach ($item in $runtime.files.PSObject.Properties) {
    $destination = [IO.Path]::GetFullPath((Join-Path $publishRoot $item.Name))
    if (-not $destination.StartsWith([IO.Path]::GetFullPath($publishRoot) + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe runtime path.' }
    if (Test-Path -LiteralPath $destination) {
      if ((Get-PublishHash $destination) -ne $item.Value) { throw ('Existing runtime differs: ' + $item.Name) }
      continue
    }
    $entry = $archive.GetEntry($release.folder + '/' + $item.Name.Replace('\','/'))
    if ($null -eq $entry) { throw 'Incomplete runtime archive.' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$destination,$false)
    if ((Get-PublishHash $destination) -ne $item.Value) { throw 'Extracted runtime checksum mismatch.' }
  }
} finally { $archive.Dispose() }
Write-Output 'Verified portable runtime restored inside this checkout. No global software was installed.'
