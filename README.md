# misinfochecker

## AWS Emulator setup

The application uses AWS Emulator for local SQS and DynamoDB access. Start the
emulator, then configure the same PowerShell session used to run the API and
Celery worker:

```powershell
$emulatorDir = "$env:USERPROFILE\.aws\emulator\9297"
$env:AWS_ENDPOINT_URL = "https://127.0.0.1:9297"
$env:AWS_SHARED_CREDENTIALS_FILE = "$emulatorDir\emulator_credentials"
$env:AWS_CONFIG_FILE = "$emulatorDir\config"
$env:AWS_CA_BUNDLE = "$emulatorDir\ca.pem"
$env:AWS_EC2_METADATA_DISABLED = "true"
$env:AWS_DISABLE_HOST_PREFIX_INJECTION = "true"
$env:AWS_REGION = "us-east-1"
$env:AWS_DEFAULT_REGION = "us-east-1"

Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY,
  Env:AWS_SESSION_TOKEN, Env:AWS_PROFILE -ErrorAction SilentlyContinue
```

Create the required resources with the AWS CLI while those variables are set:

```powershell
aws dynamodb create-table `
  --table-name RateLimits `
  --attribute-definitions AttributeName=limit_key,AttributeType=S `
  --key-schema AttributeName=limit_key,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table `
  --table-name CeleryResults `
  --attribute-definitions AttributeName=task_id,AttributeType=S `
  --key-schema AttributeName=task_id,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST

aws sqs create-queue --queue-name analyze-queue
```

The code uses `AWS_SQS_QUEUE_URL` when it is set. Otherwise it uses the
standard AWS Emulator queue URL:

```powershell
$env:AWS_SQS_QUEUE_URL = "https://127.0.0.1:9297/000000000000/analyze-queue"
```

The repository includes an idempotent setup script that configures the
environment and creates the tables and queue:

```powershell
cd "C:\Users\saad-\OneDrive\Documents\misinfochecker\misinfochecker"
. .\setup-emulator.ps1
```

The leading dot and space preserve the environment variables in the current
PowerShell session. Run this after starting AWS Emulator.

To build and start Redis, the API, and the Celery worker in Linux containers,
set the OpenAI key and run:

```powershell
$env:OPENAI_API_KEY = "your-key"
# Optional: override the default OpenAI model.
# $env:OPENAI_MODEL = "gpt-4o-mini"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\run-docker.ps1
```

The script replaces containers named `misinfochecker-redis`,
`misinfochecker-api`, and `misinfochecker-worker`. Redis is used only as the
local Celery broker; DynamoDB continues to use AWS Emulator. TLS verification
is disabled only for the local emulator connection inside these containers.

Never commit AWS credentials or real AWS service URLs. AWS Emulator generates
credentials and a CA certificate under
`$env:USERPROFILE\.aws\emulator\9297` each time it starts.
