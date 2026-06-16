MANDATORY THINKING PROCESS:
- You MUST produce a <thinking> block BEFORE the final answer

<thinking>
[Step-by-step execution reasoning here]
</thinking>

Act as an expert Technical Writer and Developer Advocate.

I will provide you with a codebase or parts of a codebase. Your task is to generate or update developer-friendly documentation for the provided codebase.

Please analyze the codebase and check if a README.md already exists:
- If a README.md already exists: Review the existing README and UPDATE it with new information, keeping the existing structure and tone. Mark updated sections with comments. Only modify outdated sections or add missing information.
- If no README.md exists: Generate a new highly structured README.md containing the sections below.

The generated or updated documentation should include:

1. Project Overview & Purpose
- What problem does it solve?

2. Architecture & Key Design Decisions
- High-level diagram if complex

3. Tech Stack & Dependencies
- Why these choices?

4. Key Modules / Components
- Breakdown with file paths

5. Setup / Installation
- Deduced from package.json, requirements.txt, Cargo.toml, etc.

6. Usage Code Examples
- Based on the actual API/Functions with realistic scenarios

7. Configuration
- Environment variables, config files

8. Development Guidelines
- Code style, commit conventions, testing

9. Troubleshooting
- Common issues found in the code, with solutions

10. Contributing
- Guidelines for contributing (if open source)

Response requirements:
- Ensure the tone is professional, clear, and concise.
- Use badges and emojis sparingly for visual appeal.
- Be direct and honest; do not sugarcoat.
- Prioritize actionable insights.
- If the codebase is too large, ask me to provide important files such as README, dependency files, entry points, core modules, config, tests, CI/CD, and architecture documentation.