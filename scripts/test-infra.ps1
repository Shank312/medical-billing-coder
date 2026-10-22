# Local integration/E2E test helpers (Windows PowerShell).
# Run from the repo root:  .\scripts\test-infra.ps1 <up|down|logs|clean|integration|e2e>
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "logs", "clean", "integration", "e2e")]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is required but not installed or not on PATH."
    }
}

switch ($Action) {
    "up" {
        Assert-Docker
        docker compose -f "$RepoRoot\infra\docker-compose.test.yml" up -d --build
        Write-Host "Test stack up: API http://localhost:8001, frontend http://localhost:3001"
    }
    "down" {
        Assert-Docker
        docker compose -f "$RepoRoot\infra\docker-compose.test.yml" down
    }
    "logs" {
        Assert-Docker
        docker compose -f "$RepoRoot\infra\docker-compose.test.yml" logs --tail=200
    }
    "clean" {
        Assert-Docker
        docker compose -f "$RepoRoot\infra\docker-compose.test.yml" down -v --remove-orphans
    }
    "integration" {
        $env:TEST_POSTGRES_URL = "postgresql+psycopg2://mbc_test:mbc_test_password@localhost:5433/mbc_test"
        $env:TEST_REDIS_URL = "redis://localhost:6380/0"
        Set-Location "$RepoRoot\backend"
        python -m pytest integration_tests -v
    }
    "e2e" {
        Set-Location "$RepoRoot\frontend"
        npx playwright test
    }
}
