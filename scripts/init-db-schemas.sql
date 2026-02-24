-- Initialize service-specific schemas for DDD Bounded Context separation.
-- This script runs on postgres-db first boot via docker-entrypoint-initdb.d.
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS synapse;
CREATE SCHEMA IF NOT EXISTS vision;
CREATE SCHEMA IF NOT EXISTS weaver;
CREATE SCHEMA IF NOT EXISTS oracle;
