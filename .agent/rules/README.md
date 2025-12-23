---
trigger: manual
description: Index and guide for the AI Rules System.
---

# Rules System Documentation

## Purpose
This directory contains the "Constitution" and operating laws for the AI agents working on this project. These rules are designed to ensure safety, scalability (10,000+ users), and maintainability.

## Reading Order
For any new developer or AI agent, read the documents in this order:

1.  **[ai-rules.md](./ai-rules.md)**: The Core Constitution. Non-negotiable behavior rules.
2.  **[coding-standards.md](./coding-standards.md)**: Universal code style, performance, and structure rules.
3.  **[security.md](./security.md)**: Mandatory security protocols (Auth, OWASP, Data).
4.  **[testing.md](./testing.md)**: The Testing Pyramid and requirements for PRs.
5.  **[rule_creator.md](./rule_creator.md)**: (Meta) Rules for creating new rules.

## Usage
- **Global Rules**: Apply to everything.
- **Context Rules**: Apply only when specific components are touched (e.g., Security rules when touching Auth).
