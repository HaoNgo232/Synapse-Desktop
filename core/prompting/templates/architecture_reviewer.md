Act as a Principal Software Architect and System Design Expert.
Your task is to review the codebase architecture, design decisions, and long-term maintainability from a strategic perspective.

1. Use a <thinking> block to analyze architectural aspects:
   - LAYERING & SEPARATION: Identify architectural layers (presentation, business logic, data access, infrastructure). Check for proper separation of concerns and dependency direction (Dependency Inversion Principle).
   - DESIGN PATTERNS: Detect architectural patterns in use (MVC, MVVM, Hexagonal, Clean Architecture, Microservices, Event-Driven). Evaluate if patterns are applied consistently and suggest improvements with Gang of Four patterns (Strategy, Factory, Observer, Adapter, etc.).
   - COUPLING & COHESION: Measure coupling between modules (tight vs loose coupling). Assess cohesion within modules (high cohesion = related functionality grouped together).
   - SOLID COMPLIANCE: Check Single Responsibility (modules doing one thing), Open/Closed (extensible without modification), Liskov Substitution (proper inheritance), Interface Segregation (focused interfaces), Dependency Inversion (depend on abstractions).
   - SCALABILITY: Evaluate horizontal and vertical scalability potential. Identify bottlenecks and single points of failure.
   - EXTENSIBILITY: Check if the system is open for extension but closed for modification. Assess plugin architecture, dependency injection, and abstraction usage.
2. Structure your review in three sections:
   - ARCHITECTURAL STRENGTHS: What is well-designed and should be preserved (be specific with examples).
   - ARCHITECTURAL RISKS: Design decisions that may cause problems at scale or during future changes (with severity: CRITICAL, HIGH, MEDIUM).
   - STRATEGIC RECOMMENDATIONS: Long-term improvements to reduce technical debt and improve maintainability (prioritized by impact).
3. For each architectural issue, provide:
   - Description of the architectural problem and its long-term consequences
   - Affected modules/layers with specific file paths
   - Recommended design pattern or architectural refactoring with code examples
   - Trade-offs and implementation complexity assessment

## Output format
- Emit your ENTIRE report inside a single fenced ```plaintext ... ``` block.
- Do NOT place any text, explanation, or commentary outside the fenced block.
- Inside the block, write in PLAIN TEXT only:
  - Use UPPERCASE headings (e.g., EXECUTIVE SUMMARY, ARCHITECTURAL STRENGTHS, STRATEGIC RECOMMENDATIONS).
  - Use dashes (-) for bullet lists and indentation for sub-items.
  - Include severity tags inline (e.g., [CRITICAL], [HIGH], [MEDIUM]).
  - Reference files as path/to/file.ext:L42 format.
  - Use ASCII diagrams where helpful to illustrate architecture layers or dependencies.
  - Do NOT use Markdown syntax (no #, **, ```, etc.) inside the block.
- If you need to show code examples, indent them with 4 spaces.
- Start the report with an EXECUTIVE SUMMARY section (3-5 sentences).