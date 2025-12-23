---
trigger: manual
description: Universal coding standards and AI interaction rules. Enforced globally.
---

# Global Coding Standards

## 1. Code Quality & Style
- **No Magic Numbers**: You must replace hard-coded numeric or string values with named constants.
- **Naming**: Variables, functions, and classes must use descriptive names that reveal intent. Do not use single-letter names (except for loop counters `i`, `j`).
- **Comments**: Do not describe *what* code does (the code must speak for itself). You must comment *why* a complex or non-obvious decision was made.
- **Single Responsibility**: Functions must perform exactly one logical task. If a function description requires "and", split it.
- **DRY Principle**: Do not duplicate logic. Extract shared code into reusable utilities.

## 2. Structure & Encapsulation
- **Directory Structure**: strict adherence to the project's folder structure (e.g. `src`, `tests`, `docs`) is mandatory.
- **Encapsulation**: Do not expose internal implementation details. Use private/protected members where applicable.
- **File Hierarchy**: distinct files for models, services, and controllers.

## 3. Performance & Scalability (10k Users)
- **N+1 Query Prevention**: NEVER use database queries inside loops. Use `JOINs` or eager loading (e.g., `select_related`, `prefetch_related`).
- **Pagination**: API endpoints correctly returning lists MUST be paginated. Default limit: 50 items.
- **Indexing**: Foreign keys and frequently queried columns must be indexed.
- **Timeouts**: All external network calls (HTTP, DB, Redis) MUST have a timeout configured. Default: 5 seconds.

## 4. Reliability & Error Handling
- **No Silent Failures**: NEVER swallow exceptions with `pass`. Log the error and re-raise or handle gracefully.
- **Structured Errors**: API responses must follow a standard error envelope (e.g., `{ "error": "code", "message": "human readable", "details": {...} }`).
- **Retries**: Use exponential backoff for transient failures (network, 3rd party APIs).

## 5. Observability & Logging
- **Structured Logging**: Use JSON-formatted logging for all production logs.
- **Levels**:
    - `debug`: Internal state, high volume.
    - `info`: Key business events (User Login, Order Placed).
    - `warning`: unexpected but recoverable state.
    - `error`: action failed, intervention may be needed.
- **No PII**: NEVER log passwords, tokens, or unmasked PII (emails, phone numbers).

## 6. Maintenance & Safety
- **Refactoring**: You must clean up technical debt immediately when touching related code. "Leave it cleaner than you found it."
- **Testing**: Tests are required for all bug fixes and new features.
- **Version Control**: Commits must be small, focused, and have descriptive messages following Conventional Commits (e.g., `feat:`, `fix:`, `refactor:`).

## 7. AI Behavior & Interaction (Non-Negotiable)
- **File Management**: You must check the content of files before editing. Do not assume content.
- **Incremental Changes**: Make changes file-by-file. do not edit multiple files blindly without context.
- **No Apologies**: Do not apologize. Correct the error and proceed.
- **Verification**: Do not ask the user to verify code you can verify yourself.
- **Scope Control**: Do not invent features. Implement exactly what is requested.
- **Context Freshness**: Do not rely on stale memory of files; read them if unsure.
- **Links**: usage of `x.md` or placeholders is forbidden. Use real file paths.
- **Single Chunk Edits**: Provide the complete file content or a single complete diff chunk for an edit. Do not split edits of a single file into multiple partial explanation steps.