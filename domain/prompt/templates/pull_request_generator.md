### 4. RISK MITIGATION & ROLLBACK PLANNING
**Deployment Safety Measures:**
- Rollback strategy: Revert complexity assessment, data migration reversibility, dependency chain implications
- Gradual rollout approach: Feature flags, canary deployment, percentage-based traffic routing, kill switch implementation
- Monitoring checkpoints: Key metrics to watch, alerting thresholds, SLO validation, performance baselines
- Emergency procedures: Incident response contacts, rollback commands, communication protocols, postmortem triggers

**Breaking Change Management:**
- API versioning implications: Client migration timeline, backward compatibility window, deprecation schedule
- Database schema impact: Migration rollback scripts, data consistency verification, constraint validation
- Consumer notification: Affected services identification, integration testing requirements, migration assistance
- Risk acceptance: Documented trade-offs, compensating controls, stakeholder approval for acceptable risks

### 5. REVIEWER GUIDANCE & CONTEXT PROVISION
**Review Efficiency Optimization:**
- Critical review areas: Security-sensitive changes, performance-critical paths, business logic modifications, error handling completeness
- Architecture alignment: Design pattern adherence, SOLID principles compliance, existing abstraction usage
- Testing validation: Manual scenarios, integration requirements, performance benchmarking, edge case coverage
- AI code quality: Pattern consistency, hallucination detection, proper error handling, integration with existing systems

**Cross-Functional Impact Assessment:**
- Frontend implications: API contract changes, new data structures, error response handling, UI state management
- Backend implications: Database query patterns, service dependencies, caching strategy, performance characteristics  
- Infrastructure implications: Resource requirements, configuration changes, monitoring updates, deployment procedures
- Documentation needs: API docs, architecture diagrams, runbooks, changelog entries, migration guides

## CONTEXT-SPECIFIC PR RULES
- **NO GENERIC SUMMARIES:** Extract actual changed functions, classes, endpoints from git diff analysis
- **BUSINESS LANGUAGE FIRST:** Describe changes using domain terminology and business impact, not just technical details
- **RISK-FOCUSED COMMUNICATION:** Highlight failure modes, edge cases, concurrency issues, security considerations
- **ACTIONABLE GUIDANCE:** Provide specific test scenarios, deployment steps, rollback procedures

## Output format
- Emit your ENTIRE response inside a single fenced ```plaintext ... ``` block.
- Do NOT place any text, explanation, or commentary outside the fenced block.
- Inside the block, write in PLAIN TEXT only:
  - Write the entire response in Vietnamese (tiếng Việt có dấu). Keep IT terms in English where appropriate.
  - Use UPPERCASE headings (e.g., PR TITLE, BUSINESS CONTEXT, KEY CHANGES, RISK ASSESSMENT).
  - Use dashes (-) for bullet lists and indentation for sub-items.
  - Reference files as path/to/file.ext format when listing changes.
  - Do NOT use Markdown syntax (no #, **, ```, etc.) inside the block.
- Structure PR description as follows:
  - PR TITLE: Conventional Commits format (feat/fix/refactor/chore/docs: brief description)
  - BUSINESS CONTEXT: Why this change is needed, problem being solved, expected business outcome
  - TECHNICAL SUMMARY: High-level approach, architectural decisions, key trade-offs
  - KEY CHANGES: Categorized by impact area (Backend Logic, API Contracts, Database, Infrastructure, Frontend)
  - BREAKING CHANGES: Explicit warnings with migration steps if applicable, or "Không có breaking changes"
  - DEPLOYMENT REQUIREMENTS: Infrastructure needs, feature flags, migration scripts, configuration changes
  - TESTING STRATEGY: Manual test scenarios using real entities, automated test coverage, performance validation
  - RISK ASSESSMENT: Potential failure modes, rollback complexity, monitoring requirements, blast radius
  - REVIEWER GUIDANCE: Critical review focus areas, testing validation points, architectural considerations
- Extract actual file paths and function names from git diff context
- Focus on WHY decisions were made and WHAT business value is delivered
- Include specific test scenarios using real project entities and workflows
