#!/usr/bin/env bash
# Print uv index credentials for the skillsai/packages PyPI repo.
# Usage: eval "$(./scripts/codeartifact-login.sh)"
set -euo pipefail

DOMAIN="${CODEARTIFACT_DOMAIN:-skillsai}"
DOMAIN_OWNER="${CODEARTIFACT_DOMAIN_OWNER:-957156516811}"
REGION="${CODEARTIFACT_REGION:-${AWS_REGION:-us-east-1}}"

TOKEN="$(aws codeartifact get-authorization-token \
  --domain "$DOMAIN" \
  --domain-owner "$DOMAIN_OWNER" \
  --region "$REGION" \
  --query authorizationToken \
  --output text)"

printf 'export UV_INDEX_CODEARTIFACT_USERNAME=%q\n' "aws"
printf 'export UV_INDEX_CODEARTIFACT_PASSWORD=%q\n' "$TOKEN"
