param([Parameter(Mandatory=$true)][string]$InputPptx,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $InputPptx).Path
$target=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $target){throw 'Use a new preview directory; existing output is preserved.'}
$application=$null;$presentation=$null
try {
    try {$application=New-Object -ComObject PowerPoint.Application} catch {throw 'PowerPoint is not installed or its automation is unavailable. Open the PPTX in your presentation software to render and review; no additional Skill is required.'}
    New-Item -ItemType Directory -Path $target | Out-Null
    $presentation=$application.Presentations.Open($source,$true,$false,$false)
    $presentation.Export($target,'PNG',1280,720)
    [PSCustomObject]@{rendered=$true;slides=$presentation.Slides.Count;renderer='Microsoft PowerPoint';output=$target;classroom_accepted=$false} | ConvertTo-Json
} finally {
    if($presentation){$presentation.Close();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)}
    if($application){$application.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($application)}
}
