---
name: solution-testing
description: End-to-end and acceptance testing: Playwright browser automation (page object model, locator strategy), API E2E flows, BDD with Gherkin/Cucumber, smoke tests for post-deployment verification, flakiness prevention, and CI integration.
---

# Solution Testing

End-to-end and acceptance testing techniques for verifying that a feature works correctly across the full stack — browser, API, and data layer — from the user's perspective.

## When to Activate

- Writing browser automation tests for user journeys
- Verifying a full feature works end-to-end (UI through DB)
- Setting up Playwright or Cypress for a project
- Writing BDD feature files with Gherkin syntax
- Designing smoke tests for post-deployment verification
- Debugging flaky E2E tests
- Deciding how many E2E tests to write for a feature

## E2E vs Integration: The Boundary

E2E tests cover things integration tests cannot:

- Real browser rendering and JavaScript execution (layout, event handling, hydration)
- Full stack traversal: UI → API → DB → UI response cycle
- Multi-step user journeys across pages, sessions, and auth boundaries

### Cost of Each Test Level

| Type        | Speed         | Flakiness Risk | Maintenance Cost |
|-------------|---------------|----------------|------------------|
| Unit        | ms            | Very low       | Low              |
| Integration | seconds       | Low            | Medium           |
| E2E         | 10s–minutes   | High           | High             |

### The Honeycomb Model

Prefer more service-level integration tests over E2E tests. E2E tests are expensive to write, slow to run, and prone to flakiness. Use them sparingly.

- Write E2E tests only for critical user journeys: login, checkout, core business workflows
- Do not write E2E tests for every edge case — cover those with unit and integration tests
- Aim for: many unit tests → more integration tests → few targeted E2E tests

## Playwright Setup and Patterns

### Project Setup

```bash
npm init playwright@latest
# or add to an existing project:
npm install -D @playwright/test
npx playwright install
```

Config (`playwright.config.ts`):

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: [['html'], ['list']],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

### Page Object Model (POM)

Each page or major component has a class that encapsulates its selectors and actions. Test files use POM methods — never raw locators.

```typescript
// pages/login.page.ts
import { Page, Locator } from '@playwright/test';

export class LoginPage {
  private readonly emailInput: Locator;
  private readonly passwordInput: Locator;
  private readonly submitButton: Locator;

  constructor(private page: Page) {
    this.emailInput = page.getByLabel('Email');
    this.passwordInput = page.getByLabel('Password');
    this.submitButton = page.getByRole('button', { name: 'Sign in' });
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}

// e2e/auth.spec.ts
import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/login.page';

test('user can log in with valid credentials', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login('user@example.com', 'password123');
  await expect(page).toHaveURL('/dashboard');
});
```

### Locator Strategy (Priority Order)

| Locator         | Example                                          | Why preferred / when to use                                  |
|-----------------|--------------------------------------------------|--------------------------------------------------------------|
| `getByRole`     | `getByRole('button', { name: 'Submit' })`        | Accessibility-based, most stable, mirrors how users perceive UI |
| `getByLabel`    | `getByLabel('Email address')`                    | Form inputs — semantically tied to label text                |
| `getByText`     | `getByText('Welcome back')`                      | Unique visible text content                                  |
| `getByTestId`   | `getByTestId('submit-btn')`                      | When no semantic selector works; use `data-testid` attribute |
| CSS selector    | `locator('.btn-primary')`                        | Last resort — fragile, breaks on markup changes, avoid       |

```typescript
// BAD
page.locator('#root > div > form > button:nth-child(2)')
// Fragile CSS path — breaks on any DOM restructure

// GOOD
page.getByRole('button', { name: 'Submit' })
// Semantic, resilient, matches accessibility tree
```

### Waiting Strategy

Never use hardcoded sleeps. Always wait for an observable UI state.

```typescript
// BAD
await page.click('#submit');
await page.waitForTimeout(2000);  // never do this — hides real timing issues

// GOOD
await page.click('#submit');
await expect(page.getByText('Payment confirmed')).toBeVisible();
// or wait for navigation:
await page.waitForURL('/confirmation');
```

## API E2E Tests

Test complete API workflows over the network — not just service-level unit behavior. This verifies the full auth lifecycle, serialization, and routing.

Key patterns:
- Obtain an auth token, use it in subsequent requests, refresh before expiry
- Use Playwright's `request` fixture for co-located API and browser tests
- Assert on response status, body shape, and downstream side effects

```typescript
test('create and retrieve payment', async ({ request }) => {
  // authenticate
  const authRes = await request.post('/api/auth/token', {
    data: { email: 'test@example.com', password: 'password' }
  });
  const { access_token } = await authRes.json();

  // create resource
  const createRes = await request.post('/api/payments', {
    headers: { Authorization: `Bearer ${access_token}` },
    data: { amount: 100, currency: 'USD' }
  });
  expect(createRes.ok()).toBeTruthy();
  const { id } = await createRes.json();

  // retrieve and verify
  const getRes = await request.get(`/api/payments/${id}`, {
    headers: { Authorization: `Bearer ${access_token}` }
  });
  const payment = await getRes.json();
  expect(payment.amount).toBe(100);
});
```

## BDD with Gherkin

### When to Use BDD

Use BDD when:
- A product owner, QA, and developer need shared, readable test documentation
- Business rules are complex and non-engineers need to verify coverage

Do not use BDD when:
- The team is small and tickets already capture intent clearly
- The overhead of step definitions outweighs the communication benefit

### Feature File Structure

```gherkin
Feature: User Authentication
  As a registered user
  I want to log in with my credentials
  So that I can access my account

  Background:
    Given a user exists with email "user@example.com"

  Scenario: Successful login
    When I submit valid credentials for "user@example.com"
    Then I should be redirected to the dashboard
    And I should see a welcome message

  Scenario: Failed login - wrong password
    When I submit the wrong password for "user@example.com"
    Then I should see "Invalid credentials"
    And I should remain on the login page

  Scenario Outline: Login with various invalid inputs
    When I submit email "<email>" and password "<password>"
    Then I should see error "<error>"

    Examples:
      | email            | password | error                    |
      | invalid-email    | pass123  | Invalid email format     |
      |                  | pass123  | Email is required        |
      | user@example.com |          | Password is required     |
```

### BDD Tooling

| Language   | Tool                    |
|------------|-------------------------|
| Node.js    | `@cucumber/cucumber`    |
| Python     | `behave`                |
| Go         | `godog`                 |
| Java       | `Cucumber-JVM`          |

Use tags to filter test runs: `@smoke`, `@regression`, `@wip`.

```bash
# Run only smoke-tagged scenarios
npx cucumber-js --tags @smoke

# Skip work-in-progress scenarios
npx cucumber-js --tags "not @wip"
```

## Smoke Tests

Smoke tests answer one question: "Is the deployed system alive?" They are not comprehensive — they verify only the critical path. If a smoke test fails, the deployment must be rolled back or halted immediately.

Run smoke tests automatically after every deployment to staging and production.

Criteria for inclusion: if this breaks, the system is unusable for most users.

```typescript
test.describe('Smoke', () => {
  test('health endpoint returns 200', async ({ request }) => {
    const res = await request.get('/health');
    expect(res.status()).toBe(200);
  });

  test('home page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });

  test('user can log in', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(process.env.SMOKE_USER!, process.env.SMOKE_PASSWORD!);
    await expect(page).toHaveURL('/dashboard');
  });
});
```

Run with:

```bash
npx playwright test --grep @smoke
```

Tag smoke tests with `@smoke` in Playwright using `test.describe` metadata or a custom tag fixture so they can be selected independently from the full suite.

## Flakiness Prevention

### Root Causes and Fixes

| Cause                                        | Fix                                                              |
|----------------------------------------------|------------------------------------------------------------------|
| Hardcoded `waitForTimeout`                   | Replace with observable state assertions (`toBeVisible`, etc.)  |
| Shared test data across parallel tests       | Use unique IDs per test run (e.g., `Date.now()` suffix)          |
| Tests depend on execution order              | Each test must set up its own state in `beforeEach`             |
| Timezone or locale sensitivity               | Fix locale in test environment config                           |
| Race conditions in UI during animation       | Use `toBeVisible()` / `toBeEnabled()` — not `isVisible()`       |
| Network variability in CI                    | Increase timeouts in CI config, not with `waitForTimeout`       |

### Quarantine Pattern

When a test is flaky and cannot be fixed immediately, quarantine it rather than deleting it. Deletion loses coverage history; quarantine preserves intent and tracks remediation.

```typescript
test.fixme('payment flow — FLAKY: race condition in payment widget', async ({ page }) => {
  // tracked in: https://github.com/org/repo/issues/123
  // do not delete — re-enable once widget stabilised
});
```

`test.fixme` skips the test and marks it as expected to fail. Remove the `.fixme` once the underlying issue is resolved.

## Test Data Management

Never use production accounts or shared test users in E2E tests. Shared state causes interference between parallel runs and makes failures non-deterministic.

### API-Driven Setup and Teardown

```typescript
let testUser: { id: string; email: string };

test.beforeEach(async ({ request }) => {
  // create an isolated test user for this test run
  const res = await request.post('/api/test/users', {
    data: { email: `test-${Date.now()}@example.com` }
  });
  testUser = await res.json();
});

test.afterEach(async ({ request }) => {
  // clean up — do not leave test data in the database
  await request.delete(`/api/test/users/${testUser.id}`);
});
```

### Rules for Test Data

- Test data helper endpoints (`/api/test/*`) must only be available in `test` and `staging` environments
- Gate them with a `NODE_ENV` check in the server — never expose in production
- Prefer creating data via API over direct DB mutations for portability
- Do not rely on seed data that may change — generate data at test time

```typescript
// server-side guard (Express example)
if (process.env.NODE_ENV !== 'test' && process.env.NODE_ENV !== 'staging') {
  throw new Error('Test helpers only available in test/staging environments');
}
```

## CI Integration

### Recommended CI Configuration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test
        env:
          CI: true
          BASE_URL: http://localhost:3000
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: playwright-report/
```

Key CI settings:
- Set `CI=true` so Playwright applies `retries: 2` from config
- Upload `playwright-report/` as artifact on failure for post-mortem debugging
- Run smoke tests as a separate faster job on staging deploy; run full suite on PRs

## Checklist

- [ ] E2E tests cover only critical user journeys (login, core workflows, checkout)
- [ ] Page Object Model used — no raw locators in test files
- [ ] Locators use `getByRole` / `getByLabel` — no fragile CSS selectors
- [ ] No `waitForTimeout` — all waits are based on observable state
- [ ] Tests are fully isolated — no shared mutable state between tests
- [ ] Smoke tests defined and run automatically after every deployment
- [ ] Flaky tests are quarantined with `test.fixme` and a tracking issue, not deleted
- [ ] Test data created via API in `beforeEach` and cleaned up in `afterEach`
- [ ] CI retries E2E tests 2x before failing (`retries: 2` in CI config)
- [ ] Screenshots and video captured on failure for debugging (`playwright.config.ts`)
- [ ] Test data endpoints are gated and unavailable in production
- [ ] BDD feature files reviewed by a non-engineer to confirm readability
