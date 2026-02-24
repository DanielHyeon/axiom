#!/bin/bash
# Check that domain/ package has zero infrastructure dependencies.
# This enforces the DDD layering rule: domain depends on nothing external.

DOMAIN_DIR="services/core/app/domain"

if [ ! -d "$DOMAIN_DIR" ]; then
  echo "SKIP: $DOMAIN_DIR does not exist"
  exit 0
fi

VIOLATIONS=$(grep -rn \
  "import sqlalchemy\|import redis\|import httpx\|import psycopg\|import aiohttp\|from app\.infrastructure\|from app\.api\|from app\.models\|from app\.core\.\|from app\.services\.\|from app\.workers\." \
  "$DOMAIN_DIR" 2>/dev/null | wc -l)

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "FAIL: domain/ package has $VIOLATIONS infrastructure dependency violations:"
  grep -rn \
    "import sqlalchemy\|import redis\|import httpx\|import psycopg\|import aiohttp\|from app\.infrastructure\|from app\.api\|from app\.models\|from app\.core\.\|from app\.services\.\|from app\.workers\." \
    "$DOMAIN_DIR"
  exit 1
fi

echo "PASS: domain/ package dependency rules OK (0 violations)"
