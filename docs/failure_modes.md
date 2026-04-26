# Failure Modes Documentation

This document describes the failure modes supported by the Decision Authority Infrastructure (DAI) SDK.

## Overview
Failures in decision-making shouldn't just be logged and lost. DAI elevates failures to first-class decision events, enabling comprehensive Article 19 logging even when systems fail.

## Failure Mode Structure

A `FailureMode` consists of:
- **`code`**: A unique string identifying the error (e.g. `NETWORK_ERROR`).
- **`severity`**: Defined by `FailureSeverity` (`warning`, `error`, `critical`).
- **`description`**: Human-readable context about what went wrong.
- **`traceback`**: (Optional) The raw stack trace for debugging.

## Exception Handling Workflow
1. When an exception occurs within the `Decision` context block before `with_outcome` is called, DAI automatically records a conservative fallback.
2. The outcome is recorded as `escalated`.
3. The exception is marked as applied (`exception_applied=True`), with the type `conservative_fallback`.

## Operator Responses
- **Warning**: Review logs. No immediate intervention required.
- **Error**: Investigate cause. Usually isolated to a single decision.
- **Critical**: Systemic issue. Agent might be paused.

## Common Codes
- `TIMEOUT`: System took too long to respond.
- `API_UNAVAILABLE`: External dependency is down.
- `DATA_MISSING`: Required context data could not be retrieved.
