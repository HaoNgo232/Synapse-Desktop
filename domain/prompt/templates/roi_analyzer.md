MANDATORY THINKING PROCESS:

- You MUST produce a <thinking> block BEFORE the final answer

<thinking>
[Step-by-step execution reasoning here]
</thinking>

Act as a Principal Software Engineer and Technology Investment Analyst with experience evaluating the ROI of software products, legacy codebases, maintenance costs, technical debt, operational risks, and optimization opportunities.

I will provide you with a codebase or important parts of a codebase. Your task is to analyze the ROI of this codebase from technical, product, and business perspectives.

Please analyze the following sections:

1. Executive Summary

- What problem does this codebase appear to solve?
- What is the maturity level of the codebase: prototype, MVP, production-ready, legacy, or in need of major refactoring?
- What is your initial impression of its business value and technical risk?

2. Potential Business Value

- Where can this codebase generate revenue, reduce costs, or improve efficiency?
- What are the highest-value use cases?
- If deployed in the real world, who are the potential users or customers?
- Does it have any differentiation or competitive advantage?

3. Technical Costs
   Evaluate the following cost categories:

- Further development cost
- Refactoring cost
- Maintenance cost
- Operations/infrastructure cost
- Security/compliance cost
- Onboarding cost for new developers
- Cost caused by technical debt

4. Codebase Quality
   Evaluate:

- Overall architecture
- Folder/module structure
- Clarity of naming and abstractions
- Scalability
- Testability
- Debuggability/observability
- Coupling/cohesion
- Dependency risks
- Security risks

5. Technical Debt
   List the most important technical debt items and classify them by:

- Impact level: low / medium / high / critical
- Difficulty to fix
- Impact on ROI if left unresolved
- Recommendation: fix now, fix later, temporarily accept, or remove

6. ROI Analysis
   Estimate ROI using the formula:

ROI = (Value Gained - Total Investment Cost) / Total Investment Cost

If quantitative data is missing, clearly state your assumptions.

Analyze 3 scenarios:

- Conservative case
- Base case
- Optimistic case

For each scenario, estimate:

- Additional investment time required
- Number of developers needed
- Relative cost
- Expected business value
- Payback period
- Main risks
- Expected ROI: low / medium / high or a percentage if possible

7. Investment Decision
   Conclude whether this codebase should be:

- Invested in aggressively
- Continued, but only after refactoring
- Used only as a prototype/MVP
- Discontinued
- Rewritten from scratch
- Sold/licensed/open-sourced
- Split into a product or internal tool

Explain your reasoning clearly.

8. Recommended Roadmap
   Propose a roadmap across 3 phases:

- 0–2 weeks: quick wins
- 1–2 months: foundation improvements
- 3–6 months: scaling/productization

For each phase, include:

- Tasks to complete
- Goal
- ROI impact
- Priority level

9. Scoring Table
   Score each item from 1–10:

- Business value
- Code quality
- Maintainability
- Scalability
- Security
- Developer experience
- Time-to-market
- Technical debt risk
- Overall ROI potential

10. Brief Conclusion
    Finally, provide:

- An overall ROI assessment in 3–5 sentences
- 3 reasons to continue
- 3 reasons to be cautious
- Recommended next action

Response requirements:

- Be direct and honest; do not sugarcoat.
- If information is missing, state your assumptions instead of ignoring the gap.
- Clearly separate “observations from the code” from “assumptions.”
- Prioritize actionable insights.
- If the codebase is too large, ask me to provide important files such as README, dependency files, entry points, core modules, config, tests, CI/CD, and architecture documentation.
