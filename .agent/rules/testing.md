---
trigger: manual
description: Comprehensive testing strategy (Unit, Integration, E2E, Load).
---

# Testing Strategy & Rules

## 1. Testing Pyramid
We strictly adhere to the testing pyramid:
- **Unit Tests**: 70% of tests. Fast, isolated, covers business logic.
- **Integration Tests**: 20% of tests. Covers DB, API, and component interactions.
- **E2E Tests**: 10% of tests. Covers critical user flows (Playwright).

## 2. Unit Testing Rules
- **Coverage Goal**: Minimum 80% line coverage for all business logic files.
- **Isolation**: MUST NOT hit the database or external APIs. Use mocks/stubs.
- **Speed**: Entire unit test suite must run in < 2 minutes.

## 3. Integration Testing Rules
- **Scope**: Verify that components talk to each other correctly (e.g., API -> DB).
- **Database**: Use a separate test database. Reset state between tests (transaction rollback preferred).
- **Contracts**: Verify API response shapes match expected contracts.

## 4. End-to-End (E2E) UI Testing (Playwright)
**Persona**: Expert QA Engineer.
**Focus**: Critical User Flows (Login, Checkout, Signup).

### Best Practices
- **Selectors**: ALWAYS use `data-testid` attributes. NEVER use fragile CSS/XPath selectors.
- **Stability**: Use Playwright's auto-waiting. Avoid fixed `sleep()` calls.
- **Mocking**: Use `page.route` to mock difficult upstream dependencies if necessary for stability.

### Example Pattern
```typescript
test('should login successfully', async ({ page }) => {
  await page.goto('/login');
  await page.getByTestId('username').fill('user');
  await page.getByTestId('password').fill('pass');
  await page.getByTestId('submit').click();
  await expect(page).toHaveURL('/dashboard');
});
```

## 5. Load & Performance Testing
**Mandatory for**: Login, Checkout, High-traffic public endpoints.
- **Tool**: k6 or Locust.
- **Thresholds**:
    - P95 Latency < 500ms at 100 concurrent users.
    - Error rate < 0.1%.
- **Frequency**: Run on every major release or infrastructure change.

## 6. Test Data Management
- **Factories**: Use libraries (e.g., `factory_boy`, `faker`) to generate test data.
- **Hard-coding**: AVOID hard-coded IDs or data that assumes specific DB state.
- **Cleanup**: Tests must clean up their own data or use transaction rollbacks.