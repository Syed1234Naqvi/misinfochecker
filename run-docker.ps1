$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$emulatorRoot = "$env:USERPROFILE\.aws\emulator"
$emulatorDir = "$env:USERPROFILE\.aws\emulator\9297"
$imageName = "misinfochecker:local"
$networkName = "misinfochecker-net"
$redisContainer = "misinfochecker-redis"
$apiContainer = "misinfochecker-api"
$workerContainer = "misinfochecker-worker"
$openAiModel = if ($env:OPENAI_MODEL) { $env:OPENAI_MODEL } else { "gpt-4o-mini" }

function Assert-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. Install it and reopen PowerShell."
    }
}

Assert-Command "docker"
Assert-Command "aws"

if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is not set. Run: `$env:OPENAI_API_KEY = 'your-key'"
}

if (-not (Test-Path "$emulatorDir\emulator_credentials")) {
    throw "AWS Emulator credentials were not found. Start AWS Emulator first."
}

if (-not (Test-Path "$emulatorDir\ca.pem")) {
    throw "AWS Emulator CA certificate was not found. Start AWS Emulator first."
}

Push-Location $repoRoot
try {
    if (Test-Path ".\setup-emulator.ps1") {
        . .\setup-emulator.ps1
    }

    $awsEndpointUrl = "https://host.docker.internal:9297"
    $queueUrl = "$awsEndpointUrl/000000000000/analyze-queue"
    $networkArguments = @(
        "--network", $networkName,
        "--add-host", "host.docker.internal:host-gateway"
    )
    $apiPortArguments = @("-p", "5000:5000")

    $networkExists = docker network ls --format "{{.Name}}" |
        Where-Object { $_ -eq $networkName }
    if (-not $networkExists) {
        docker network create $networkName
        if ($LASTEXITCODE -ne 0) {
            throw "Docker network creation failed."
        }
    }

    Write-Host "Building $imageName..."
    docker build -t $imageName .
    if ($LASTEXITCODE -ne 0) {
        throw "Docker image build failed."
    }

    docker rm -f $redisContainer $apiContainer $workerContainer 2>$null

    $commonArguments = @(
        "--env", "AWS_ENDPOINT_URL=$awsEndpointUrl",
        "--env", "AWS_SQS_QUEUE_URL=$queueUrl",
        "--env", "AWS_SSL_VERIFY=false",
        "--env", "AWS_DEFAULT_REGION=us-east-1",
        "--env", "AWS_REGION=us-east-1",
        "--env", "AWS_SHARED_CREDENTIALS_FILE=/root/.aws/emulator/9297/emulator_credentials",
        "--env", "AWS_CONFIG_FILE=/root/.aws/emulator/9297/config",
        "--env", "AWS_CA_BUNDLE=/root/.aws/emulator/9297/ca.pem",
        "--env", "AWS_EC2_METADATA_DISABLED=true",
        "--env", "AWS_DISABLE_HOST_PREFIX_INJECTION=true",
        "--env", "OPENAI_API_KEY=${env:OPENAI_API_KEY}",
        "--env", "OPENAI_MODEL=$openAiModel",
        "--volume", "${emulatorRoot}:/root/.aws/emulator:ro"
    )

    Write-Host "Starting Redis container..."
    docker run -d `
        --name $redisContainer `
        --network $networkName `
        redis:7-alpine
    if ($LASTEXITCODE -ne 0) {
        throw "Redis container failed to start."
    }

    $redisArguments = @(
        "--env", "CELERY_BROKER_URL=redis://${redisContainer}:6379/0",
        "--env", "CELERY_RESULT_BACKEND=redis://${redisContainer}:6379/1"
    )

    Write-Host "Starting API container..."
    docker run -d `
        --name $apiContainer `
        @networkArguments `
        @apiPortArguments `
        @commonArguments `
        @redisArguments `
        $imageName
    if ($LASTEXITCODE -ne 0) {
        throw "API container failed to start."
    }

    Write-Host "Starting Celery worker container..."
    docker run -d `
        --name $workerContainer `
        @networkArguments `
        @commonArguments `
        @redisArguments `
        $imageName `
        python -m celery -A celery_app.celery_app worker --loglevel=info
    if ($LASTEXITCODE -ne 0) {
        throw "Celery worker container failed to start."
    }

    Write-Host ""
    Write-Host "API:    http://localhost:5000"
    Write-Host "Logs:   docker logs -f $apiContainer"
    Write-Host "Worker: docker logs -f $workerContainer"
}
finally {
    Pop-Location
}
