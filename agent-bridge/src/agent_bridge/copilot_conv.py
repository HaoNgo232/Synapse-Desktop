import os
from pathlib import Path
from typing import Dict, Tuple, List, Any

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    if not content.startswith('---'):
        return {}, content.strip()
    try:
        parts = content.split('---', 2)
        if len(parts) < 3: return {}, content.strip()
        frontmatter_raw = parts[1].strip()
        body = parts[2].strip()
        metadata = {}
        for line in frontmatter_raw.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
        return metadata, body
    except:
        return {}, content

def get_glob_for_context(context_id: str) -> str:
    """Map agent/skill domain to file globs for Copilot."""
    mapping = {
        "frontend-specialist": "**/*.{ts,tsx,js,jsx,css,scss,html}",
        "frontend-design": "**/*.{ts,tsx,js,jsx,css,scss,html}",
        "backend-specialist": "**/*.{py,js,ts,go,rs,php,api,server}",
        "api-patterns": "**/*.{py,js,ts,go,rs,php,api,server}",
        "database-architect": "**/prisma/**, **/drizzle/**, **/schema/**, **/*.sql",
        "database-design": "**/prisma/**, **/drizzle/**, **/schema/**, **/*.sql",
        "test-engineer": "**/*.test.{ts,tsx,js,jsx}, **/test_*.py, **/tests/**, **/__tests__/**",
        "testing-patterns": "**/*.test.{ts,tsx,js,jsx}, **/test_*.py, **/tests/**, **/__tests__/**",
        "devops-engineer": "**/docker/**, **/ci/**, **/.github/workflows/**, Dockerfile, *.yaml, *.yml",
        "seo-specialist": "**/public/**, **/pages/**, **/metadata/**, robots.txt, sitemap.xml",
        "seo-fundamentals": "**/public/**, **/pages/**, **/metadata/**, robots.txt, sitemap.xml",
        "mobile-developer": "**/ios/**, **/android/**, **/*.{swift,kt,java}",
        "mobile-design": "**/ios/**, **/android/**, **/*.{swift,kt,java}",
        "security-auditor": "**/*.{ts,js,py,go,rs,auth}",
        "vulnerability-scanner": "**/*.{ts,js,py,go,rs,auth}",
        "clean-code": "**/*",
        "node-best-practices": "**/*.{js,ts,json}",
        "react-best-practices": "**/*.{ts,tsx,jsx,js}",
        "python-patterns": "**/*.py",
        "rust-pro": "**/*.rs",
        "bash-linux": "**/*.sh"
    }
    return mapping.get(context_id, None)

def convert_copilot(source_dir: str, output_unused: str):
    root_path = Path(source_dir).resolve()
    # Official GitHub Copilot directories
    github_dir = Path(".github").resolve()
    agents_out_dir = github_dir / "agents"
    skills_out_dir = github_dir / "skills"

    print(f"{Colors.HEADER}🏗️  Converting to Official GitHub Copilot Spec...{Colors.ENDC}")

    # 1. PROCESS AGENTS -> .github/agents/<agent>.md
    agents_src_dir = root_path / "agents"
    if agents_src_dir.exists():
        if not agents_out_dir.exists(): agents_out_dir.mkdir(parents=True)
        for agent_file in agents_src_dir.glob("*.md"):
            try:
                meta, body = parse_frontmatter(agent_file.read_text(encoding='utf-8'))
                name = meta.get("name", agent_file.stem)
                desc = meta.get("description", "")
                if isinstance(desc, list): desc = " ".join(desc)
                
                glob = get_glob_for_context(agent_file.stem)
                
                lines = [
                    "---",
                    f"name: {name}",
                    f"description: {desc}"
                ]
                if glob:
                    lines.append(f"applyTo: \"{glob}\"")
                lines.append("---")
                lines.append("\n# Prompt")
                lines.append(f"\n{body}")

                with open(agents_out_dir / f"{agent_file.stem}.md", 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                print(f"{Colors.BLUE}  🔹 Agent: {agent_file.stem}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.RED}  ❌ Failed agent {agent_file.name}: {e}{Colors.ENDC}")

    # 2. PROCESS SKILLS -> .github/skills/<skill>/SKILL.md
    skills_src_dir = root_path / "skills"
    if skills_src_dir.exists():
        if not skills_out_dir.exists(): skills_out_dir.mkdir(parents=True)
        for skill_dir in skills_src_dir.iterdir():
            if not skill_dir.is_dir(): continue
            src_skill_file = skill_dir / "SKILL.md"
            if src_skill_file.exists():
                try:
                    meta, body = parse_frontmatter(src_skill_file.read_text(encoding='utf-8'))
                    name = meta.get("name", skill_dir.name)
                    desc = meta.get("description", "")
                    if isinstance(desc, list): desc = " ".join(desc)
                    
                    # Copilot skills REQUIRE a 'usage' field in frontmatter
                    usage = meta.get("usage", f"Use this skill for {desc or name} tasks.")
                    glob = get_glob_for_context(skill_dir.name)

                    lines = [
                        "---",
                        f"name: {name}",
                        f"description: {desc or name}",
                        f"usage: \"{usage}\""
                    ]
                    if glob:
                        lines.append(f"applyTo:\n  - \"{glob}\"")
                    lines.append("---")
                    lines.append("\n# Instructions")
                    lines.append(f"\n{body}")

                    dest_dir = skills_out_dir / skill_dir.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    with open(dest_dir / "SKILL.md", 'w', encoding='utf-8') as f:
                        f.write("\n".join(lines))
                    print(f"{Colors.BLUE}  🔸 Skill: {skill_dir.name}{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.RED}  ❌ Failed skill {skill_dir.name}: {e}{Colors.ENDC}")

    # Cleanup old non-spec files if they exist
    old_instr_file = github_dir / "copilot-instructions.md"
    if old_instr_file.exists(): old_instr_file.unlink()
    old_instr_dir = github_dir / "instructions"
    if old_instr_dir.exists():
        import shutil
        shutil.rmtree(old_instr_dir)

    print(f"{Colors.GREEN}✅ Official Copilot Spec conversion complete!{Colors.ENDC}")
