$ErrorActionPreference = 'Stop'
function Get-PublishHash([string]$Path) {
  $stream = [IO.File]::OpenRead($Path); $algorithm = [Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
  finally { $stream.Dispose(); $algorithm.Dispose() }
}
$publishRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $publishRoot 'PUBLISH-MANIFEST.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$count = 0
foreach ($item in $manifest.files.PSObject.Properties) {
  $path = [IO.Path]::GetFullPath((Join-Path $publishRoot $item.Name))
  if (-not $path.StartsWith([IO.Path]::GetFullPath($publishRoot) + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe manifest path.' }
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing public file: ' + $item.Name) }
  if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked files are not permitted.' }
  if ((Get-PublishHash $path) -ne $item.Value) { throw ('Reviewed file changed: ' + $item.Name) }
  $count++
}
Write-Output ('PASS: ' + $count + ' reviewed public files match the release snapshot.')
Write-Output 'Only the manifest-listed files belong in the first Git commit. Runtime and personal data are excluded.'
