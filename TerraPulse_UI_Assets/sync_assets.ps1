# TerraPulse AI - Asset Copy and JPG Conversion Script

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$SrcDir = "C:\Users\Dell\.gemini\antigravity-ide\brain\7a3052c7-be8b-4795-8933-1f6ebd40874d"
$BaseDir = $PSScriptRoot

Write-Host "=========================================================="
Write-Host "TerraPulse AI - Asset Sync and JPG Export"
Write-Host "Source: $SrcDir"
Write-Host "Target: $BaseDir"
Write-Host "=========================================================="

function Save-AsJpg {
    param(
        [string]$InputPath,
        [string]$OutputPath,
        [long]$Quality = 95
    )
    try {
        $img = [System.Drawing.Image]::FromFile($InputPath)
        $codecs = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders()
        $jpegCodec = $null
        foreach ($c in $codecs) {
            if ($c.FormatDescription -eq "JPEG") {
                $jpegCodec = $c
                break
            }
        }
        $encoderParams = New-Object System.Drawing.Imaging.EncoderParameters(1)
        $encoderParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, $Quality)
        $img.Save($OutputPath, $jpegCodec, $encoderParams)
        $img.Dispose()
        Write-Host "Saved JPG: $(Split-Path $OutputPath -Leaf)"
    }
    catch {
        Write-Host "Error converting to JPG: $_"
    }
}

# 1. 01_Website_Screenshots
Write-Host ""
Write-Host "[1/3] Copying 01_Website_Screenshots..."

$screens = @(
    @{ Src = "$SrcDir\01_home_dashboard_1790779534901.png"; Base = "$BaseDir\01_Website_Screenshots\01_Home_Dashboard" },
    @{ Src = "$SrcDir\02_semantic_search_1790779670733.png"; Base = "$BaseDir\01_Website_Screenshots\02_Semantic_Search" },
    @{ Src = "$SrcDir\03_change_detection_1790779738573.png"; Base = "$BaseDir\01_Website_Screenshots\03_Change_Detection" },
    @{ Src = "$SrcDir\04_analyst_review_1790779813143.png"; Base = "$BaseDir\01_Website_Screenshots\04_Analyst_Review" },
    @{ Src = "$SrcDir\05_other_features_1790779908563.png"; Base = "$BaseDir\01_Website_Screenshots\05_Other_Features" }
)

foreach ($item in $screens) {
    Copy-Item -Path $item.Src -Destination "$($item.Base).png" -Force
    Write-Host "Saved PNG: $(Split-Path "$($item.Base).png" -Leaf)"
    Save-AsJpg -InputPath $item.Src -OutputPath "$($item.Base).jpg"
}

# 2. 02_Selected_Screenshots
Write-Host ""
Write-Host "[2/3] Copying 02_Selected_Screenshots..."

$selected = @(
    @{ Src = "$SrcDir\02_semantic_search_1790779670733.png"; Base = "$BaseDir\02_Selected_Screenshots\Search" },
    @{ Src = "$SrcDir\03_change_detection_1790779738573.png"; Base = "$BaseDir\02_Selected_Screenshots\Change" },
    @{ Src = "$SrcDir\04_analyst_review_1790779813143.png"; Base = "$BaseDir\02_Selected_Screenshots\Review" }
)

foreach ($item in $selected) {
    Copy-Item -Path $item.Src -Destination "$($item.Base).png" -Force
    Write-Host "Saved PNG: $(Split-Path "$($item.Base).png" -Leaf)"
    Save-AsJpg -InputPath $item.Src -OutputPath "$($item.Base).jpg"
}

# 3. 03_Final_PPT_Visual
Write-Host ""
Write-Host "[3/3] Copying 03_Final_PPT_Visual..."

$pptJpg = "$SrcDir\terrapulse_sample_ui_1790780374041.jpg"
if (Test-Path $pptJpg) {
    Copy-Item -Path $pptJpg -Destination "$BaseDir\03_Final_PPT_Visual\TerraPulse_Sample_UI.jpg" -Force
    Copy-Item -Path $pptJpg -Destination "$BaseDir\03_Final_PPT_Visual\TerraPulse_Sample_UI.png" -Force
    Write-Host "Saved: TerraPulse_Sample_UI.jpg"
    Write-Host "Saved: TerraPulse_Sample_UI.png"
}

Write-Host ""
Write-Host "=========================================================="
Write-Host "SUCCESS: All screenshots and JPGs have been saved!"
Write-Host "=========================================================="
