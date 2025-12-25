# Taskbot – Testing Guide

This directory contains all test files for the **Taskbot** application.  
The goal of this test suite is to ensure correctness, reliability, scalability, security, and performance of the system across all layers.

---

## Directory Structure

tests/
├── api/           # Single API endpoint tests (component-level)
├── integration/   # Integration tests (API ↔ DB, API ↔ Queue, API ↔ external services)
├── e2e/           # End-to-end tests (real user workflows)
├── stress/        # Stress tests (breaking point & recovery)
├── load/          # Load tests (expected peak traffic)
├── security/      # Security tests (auth, abuse, vulnerabilities)
├── performance/   # Performance tests (latency & throughput)

---

## General Testing Assumptions

- Taskbot is an API-first backend system.
- It includes authentication, task management, database persistence, async workers, and external integrations (LLM/MCP).
- Tests should be deterministic, repeatable, and environment-independent.
- Test environments must **never** use production data or credentials.

---

## API Tests (`tests/api`)

### Purpose
Validate that **each API endpoint works exactly as expected**, independently.

These tests ensure:
- Correct request/response contracts
- Proper validation and error handling
- Authorization behavior at the endpoint level

### What to Test
- Request validation (required fields, types, limits)
- Success responses and HTTP status codes
- Error responses for invalid input
- Authentication and authorization checks
- Idempotency (where applicable)

### How to Test
- Real HTTP requests to the API
- Test database
- External dependencies mocked (LLM, queues, workers)

### Example Scenarios
- `POST /tasks` returns `201` for valid payload
- `POST /tasks` returns `400` for invalid payload
- `GET /tasks/:id` returns `403` for unauthorized user
- `DELETE /tasks/:id` returns `404` for non-existent task

### Acceptance Criteria
- Response schema is correct
- HTTP status codes are accurate
- Errors are explicit and consistent
- No unintended side effects

---

## INTEGRATION Tests (`tests/integration`)

### Purpose
Verify **interaction between components**.

### What to Test
- API ↔ Database behavior
- API ↔ Queue / background workers
- API ↔ external services (mocked or sandboxed)
- Transactions and rollbacks

### How to Test
- Use real test databases
- Use test queues or in-memory substitutes
- External services must be mocked or sandboxed

### Example Scenarios
- Creating a task persists correct DB records
- Updating a task reflects in DB correctly
- Background job triggered on task creation
- Retry and idempotency behavior
- Graceful handling of external service failures

### Acceptance Criteria
- Data consistency guaranteed
- No duplicate side effects
- Clear error propagation

---

## E2E Tests (`tests/e2e`)

### Purpose
Validate **realistic user workflows** from start to finish.

### What to Test
- Authentication → action → persistence → async processing
- Cross-service interactions
- Authorization boundaries

### How to Test
- Black-box testing
- Minimal mocking
- Prefer API-level flows

### Core User Journeys
1. User authenticates
2. Creates a task
3. Assigns the task
4. Updates task progress
5. Completes the task

### Failure Scenarios
- Network interruption mid-request
- Worker crash during processing
- External integration failure

### Acceptance Criteria
- System remains consistent
- User receives actionable errors
- No data corruption

---

## LOAD Tests (`tests/load`)

### Purpose
Validate behavior under **expected peak usage**.

### What to Test
- Concurrent users
- Read-heavy and write-heavy traffic
- Queue buildup under load

### How to Test
- Gradual ramp-up
- Sustained peak load

### Metrics to Track
- p95 / p99 latency
- Error rate
- DB connections and CPU usage
- Queue depth

### Acceptance Criteria
- Stable performance under expected load
- No significant error spikes
- System remains responsive

---

## STRESS Tests (`tests/stress`)

### Purpose
Identify **system limits and recovery behavior**.

### What to Test
- Traffic beyond expected limits
- Resource exhaustion scenarios
- Sudden traffic spikes

### Example Scenarios
- 10× normal traffic
- Massive queue backlog
- Database connection saturation

### Acceptance Criteria
- Graceful degradation
- Automatic recovery after load drops
- No data loss or corruption

---

## PERFORMANCE Tests (`tests/performance`)

### Purpose
Measure **latency and throughput of critical paths**.

### What to Test
- API endpoint response times
- Background job execution time
- External call overhead (LLM/MCP)

### How to Test
- Micro-benchmarks
- Warm vs cold runs

### Acceptance Criteria
- Critical endpoints meet defined latency SLAs
- Background jobs complete within acceptable time

---

## SECURITY Tests (`tests/security`)

### Purpose
Protect against **abuse, data leaks, and unauthorized access**.

### What to Test

#### Authentication & Authorization
- Token expiration
- Role escalation attempts
- Cross-tenant access

#### Input & API Security
- SQL injection
- Over-posting fields
- Prompt injection (LLM-specific)

#### Infrastructure
- Secrets exposure
- Debug or admin endpoints
- Misconfigured CORS or headers

### Acceptance Criteria
- Unauthorized access always blocked
- Sensitive data never exposed
- Security events are logged

---

## High-Risk Areas (Priority Testing)

- Async job duplication or race conditions
- Authorization and tenant isolation
- External service failures (LLM/MCP)
- Database schema changes and migrations
- Partial failures across services

---

## Missing or Unclear Requirements (Must Be Clarified)

Testing may be incomplete until the following are defined:
1. Authentication mechanism (JWT, API key, etc.)
2. Role and permission model
3. Multi-tenancy isolation rules
4. SLA targets (latency, throughput, error budgets)
5. Retry and idempotency guarantees
6. Data retention and deletion policies
7. External integration failure handling strategy

---

## QA Execution Recommendation

If resources are limited:
1. Ensure **unit + integration tests** are solid
2. Add **one golden E2E flow**
3. Run **basic load and security tests**
4. Expand to stress and deep performance testing later

This ensures maximum risk reduction early while keeping testing practical and actionable.