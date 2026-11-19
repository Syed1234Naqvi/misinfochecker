$ErrorActionPreference = "Stop"

$emulatorDir = "$env:USERPROFILE\.aws\emulator\9297"
$env:AWS_ENDPOINT_URL = "https://127.0.0.1:9297"
$env:AWS_SHARED_CREDENTIALS_FILE = "$emulatorDir\emulator_credentials"
$env:AWS_CONFIG_FILE = "$emulatorDir\config"
$env:AWS_CA_BUNDLE = "$emulatorDir\ca.pem"
$env:AWS_EC2_METADATA_DISABLED = "true"
$env:AWS_DISABLE_HOST_PREFIX_INJECTION = "true"
$env:AWS_REGION = "us-east-1"
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:AWS_SQS_QUEUE_URL = "$env:AWS_ENDPOINT_URL/000000000000/analyze-queue"

Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY,
    Env:AWS_SESSION_TOKEN, Env:AWS_PROFILE -ErrorAction SilentlyContinue

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI was not found. Install AWS CLI, reopen PowerShell, and run this script again."
}

if (-not (Test-Path $env:AWS_SHARED_CREDENTIALS_FILE)) {
    throw "AWS Emulator credentials were not found at $env:AWS_SHARED_CREDENTIALS_FILE. Start AWS Emulator first."
}

if (-not (Test-Path $env:AWS_CA_BUNDLE)) {
    throw "AWS Emulator CA certificate was not found at $env:AWS_CA_BUNDLE. Start AWS Emulator first."
}

function Invoke-AwsCreateIfMissing {
    param(
        [string]$Description,
        [scriptblock]$Describe,
        [scriptblock]$Create
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Describe 2>$null
    $describeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference

    if ($describeExitCode -eq 0) {
        Write-Host "$Description already exists."
        return
    }

    & $Create
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create $Description."
    }

    Write-Host "Created $Description."
}

Invoke-AwsCreateIfMissing `
    -Description "RateLimits table" `
    -Describe { aws dynamodb describe-table --table-name RateLimits } `
    -Create {
        aws dynamodb create-table `
            --table-name RateLimits `
            --attribute-definitions AttributeName=limit_key,AttributeType=S `
            --key-schema AttributeName=limit_key,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST
    }

Invoke-AwsCreateIfMissing `
    -Description "CeleryResults table" `
    -Describe { aws dynamodb describe-table --table-name CeleryResults } `
    -Create {
        aws dynamodb create-table `
            --table-name CeleryResults `
            --attribute-definitions AttributeName=task_id,AttributeType=S `
            --key-schema AttributeName=task_id,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST
    }

Invoke-AwsCreateIfMissing `
    -Description "analyze-queue queue" `
    -Describe { aws sqs get-queue-url --queue-name analyze-queue } `
    -Create {
        aws sqs create-queue --queue-name analyze-queue
    }

Write-Host "AWS Emulator resources are ready."
Write-Host "AWS_SQS_QUEUE_URL=$env:AWS_SQS_QUEUE_URL"
