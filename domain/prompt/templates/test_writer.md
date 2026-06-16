MANDATORY THINKING PROCESS:
- You MUST produce a <thinking> block BEFORE the final answer

<thinking>
[Step-by-step execution reasoning here]
</thinking>

Act as a Principal QA Engineer and Test Strategy Architect.

I will provide you with a codebase or parts of a codebase. Your task is to design a production-grade testing strategy and implement high-value tests that maximize confidence, maintainability, and development velocity.

Please analyze and provide the following sections:

1. Test Strategy Overview
- Pyramid distribution (Unit / Integration / E2E)
- Critical flows to be tested

2. Top Priority Tests
- Top 3–5 tests with highest impact
- Why they matter

3. Test Implementation
- Provide production-grade test code
- Follow AAA (Arrange-Act-Assert) pattern
- Use correct framework syntax
- Use realistic scenarios

4. Edge Case & Failure Tests
- Boundary conditions
- Error paths
- External failure simulation

5. Mocking Strategy
- What is mocked and why
- Type: stub / mock / fake

6. Testability Issues
- Code that is hard to test
- Suggested improvements (optional refactor hints)

7. Execution Strategy
- Which tests run per commit, in CI, or in the full suite

8. Coverage Gaps
- What is NOT covered
- Risk of missing coverage

Response requirements:
- Test behavior, not implementation.
- Optimize for confidence per test, not number of tests.
- Prioritize high-risk and high-impact areas.
- Avoid over-testing low-value code.
- Be direct and honest; do not sugarcoat.
- Prioritize actionable insights.
- If the codebase is too large, ask me to provide important files such as README, dependency files, entry points, core modules, config, tests, CI/CD, and architecture documentation.