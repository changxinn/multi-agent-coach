[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$projectName = "nutrition-smoke-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$compose = @("compose", "--project-name", $projectName, "--file", "docker-compose.yml")

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & docker @compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Assert-Health {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][int]$ContainerPort,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $mapping = (& docker @compose port $Service $ContainerPort 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or $mapping -notmatch '^(?<host>.+):(?<port>\d+)$') {
        throw "Could not determine the published port for $Service."
    }

    $host = $Matches.host.Trim('[', ']')
    $port = [int]$Matches.port
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://${host}:$port$Path"
    if ($response.StatusCode -ne 200) {
        throw "$Service $Path returned HTTP $($response.StatusCode), expected 200."
    }
}

try {
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is unavailable. Start Docker Desktop and rerun this script."
    }

    Invoke-Compose config --quiet
    Invoke-Compose up --build --wait --wait-timeout 180

    $migration = (& docker @compose ps --all --format json migrations | ConvertFrom-Json)
    if ($migration.State -ne "exited" -or $migration.ExitCode -ne 0) {
        throw "Migration job did not complete successfully (state=$($migration.State), exitCode=$($migration.ExitCode))."
    }

    Assert-Health -Service api -ContainerPort 8000 -Path "/health/live"
    Assert-Health -Service api -ContainerPort 8000 -Path "/health/ready"
    Assert-Health -Service nutrition-agent -ContainerPort 8003 -Path "/health/live"
    Assert-Health -Service nutrition-agent -ContainerPort 8003 -Path "/health/ready"

    $nutritionPort = (& docker @compose port nutrition-agent 8003 | Select-Object -First 1)
    if ($nutritionPort -notmatch '^127\.0\.0\.1:') {
        throw "Nutrition Agent must be published only on loopback; got '$nutritionPort'."
    }

    Write-Host "Compose deployment smoke test passed for project $projectName." -ForegroundColor Green
}
finally {
    & docker @compose down --volumes --remove-orphans *> $null
}