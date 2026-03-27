---
phase: quick
plan: "01"
subsystem: storage
tags: [sqlite, schema, refactor]
dependency_graph:
  requires: []
  provides: []
  affects: [src/storage/sqlite.py]
tech_stack:
  added: []
  patterns: []
key_files:
  - path: src/storage/sqlite.py
    description: Modified init_db() to include weight column directly in feeds CREATE TABLE
decisions: []
metrics:
  duration: "<1"
  completed: "2026-03-28"
---

# Quick Task 260328-3og: Remove Migration Init DB Summary

## One-liner

Removed ALTER TABLE migration pattern from init_db() - weight column now directly defined in feeds CREATE TABLE statement.

## Changes Made

**1. Added weight column to feeds CREATE TABLE (src/storage/sqlite.py)**
- Added `weight REAL DEFAULT 0.3` to feeds table schema
- Column is now defined inline in CREATE TABLE statement

**2. Removed ALTER TABLE migration block**
- Removed lines 149-154 that added weight via runtime migration
- Schema is now clean with direct definition

## Verification Results

| Check | Status |
|-------|--------|
| init_db imports successfully | PASS |
| No ALTER TABLE for weight in init_db | PASS |
| CREATE TABLE includes weight column | PASS |

## Commit

```
0dc9fb1 refactor(260328-3og): move weight column into feeds CREATE TABLE
```

## Self-Check: PASSED

- [x] src/storage/sqlite.py modified and committed
- [x] weight column in CREATE TABLE verified
- [x] No ALTER TABLE migration for weight verified
- [x] init_db() imports correctly
