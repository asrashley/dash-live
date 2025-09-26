function Die {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

$UserGID = [System.Security.Principal.WindowsIdentity]::GetCurrent().Groups | Where-Object { $_.Value -like "*S-1-5-32-545" } | ForEach-Object { $_.Translate([System.Security.Principal.NTAccount]).Value }
$UserUID = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value

$volumes = ""
$argsArray = $args

for ($i = 0; $i -lt $argsArray.Length - 1; $i++) {
    $cmdArg = ""
    $arg = $argsArray[$i]

    switch ($arg) {
        "-o" { $cmdArg = "output" }
        "--output" { $cmdArg = "output" }
        "--subtitles" { $cmdArg = "subtitles" }
        "--input" { $cmdArg = "input" }
        "-i" { $cmdArg = "input" }
    }

    if ($cmdArg -eq "") {
        continue
    }

    $filename = $argsArray[$i + 1]

    if ($cmdArg -eq "output") {
        if (-not (Test-Path $filename -PathType Container)) {
                try {
                    New-Item -ItemType Directory -Path $filename -Force | Out-Null
                } catch {
                    Die "Failed to create output directory $filename"
                }
        }
    } elseif (-not (Test-Path $filename)) {
        Write-Error "Failed to find $cmdArg file $filename"
        exit 1
    }

    $fname = Resolve-Path $filename -ErrorAction SilentlyContinue
    if (-not $fname) {
        $fname = $filename
    } else {
        $fname = $fname.Path
    }

    if ($cmdArg -eq "output") {
        $volumes += " -v ${fname}:$arg"
    } else {
        $volumes += " -v ${fname}:$arg`:ro"
    }
}

docker run $volumes -e USER_GID=$UserGID -e USER_UID=$UserUID -t dashlive/encoder:latest $args
