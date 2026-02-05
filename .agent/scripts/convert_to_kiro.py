#!/usr/bin/env python3
"""
Antigravity to Kiro Converter
=============================
Converts the Antigravity Kit file structure (.agent/) into a single JSON configuration 
compatible with Kiro CLI/Code environments.

Parses:
- Agents (.agent/agents/*.md)
- Skills (.agent/skills/*/SKILL.md)
- Workflows (.agent/workflows/*.md)

Usage:
    python .agent/scripts/convert_to_kiro.py [output_path]
    
Default output: .kiro/agent_config.json
"""

import os
import json
import argparse
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

def print_step(text: str):
    print(f"{Colors.BLUE}🔄 {text}{Colors.ENDC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse markdown frontmatter (YAML-like style between ---)
    Returns (metadata_dict, body_content)
    """
    if not content.startswith('---'):
        return {}, content.strip()

    try:
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content.strip()

        frontmatter_raw = parts[1].strip()
        body = parts[2].strip()

        metadata = {}
        for line in frontmatter_raw.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Handle lists (e.g., tools: Read, Write)
                if ',' in value:
                    metadata[key] = [v.strip() for v in value.split(',')]
                else:
                    # Clean quotes
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    metadata[key] = value

        return metadata, body
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Error parsing frontmatter: {e}{Colors.ENDC}")
        return {}, content

def scan_agents(root_dir: Path) -> List[Dict]:
    """Scan and parse agent definitions with Kiro-standard formatting."""
    agents = []
    agents_dir = root_dir / "agents"
    
    if not agents_dir.exists():
        return []

    print_step(f"Scanning agents in {agents_dir}...")
    
    for file_path in agents_dir.glob("*.md"):
        try:
            content = file_path.read_text(encoding='utf-8')
            meta, body = parse_frontmatter(content)
            
            # Format description
            description = meta.get("description", "")
            if isinstance(description, list):
                description = " ".join(description)
            
            # KIRO TOOL MAPPING
            raw_tools = meta.get("tools", [])
            kiro_tools = []
            tool_map = {
                "bash": "shell",
                "terminal": "shell",
                "edit": "write",
                "replace_file_content": "write",
                "multi_replace_file_content": "write",
                "create_file": "write",
                "write_to_file": "write"
            }
            
            for t in raw_tools:
                t_low = t.lower()
                kiro_tools.append(tool_map.get(t_low, t_low))
            
            # Deduplicate tools
            kiro_tools = list(dict.fromkeys(kiro_tools))

            # SKILLS TO RESOURCES
            # Kiro uses skill:// protocol for lazy loading skills
            agent_skills = meta.get("skills", [])
            resources = []
            for skill_id in agent_skills:
                # We will place skills in .kiro/skills/
                resources.append(f"skill://.kiro/skills/{skill_id}/SKILL.md")

            # STRICT KIRO SCHEMA
            agent = {
                "name": meta.get("name", file_path.stem),
                "description": description,
                "prompt": body,
                "tools": kiro_tools
            }
            if resources:
                agent["resources"] = resources
            
            # SMART MODEL SELECTION
            # Define which agents are suitable for the cheaper model (claude-haiku-4.5)
            haiku_agents = [
                "documentation-writer",
                "seo-specialist",
                "explorer-agent",
                "product-owner",
                "product-manager",
                "code-archaeologist"
            ]
            
            model_val = meta.get("model", "")
            
            # 1. Check if we should force Haiku for this agent
            if file_path.stem in haiku_agents:
                agent["model"] = "claude-haiku-4.5"
            # 2. Otherwise, check if it's "inherit" (to be omitted for auto)
            elif model_val and model_val.lower() != "inherit":
                agent["model"] = model_val
            
            # Add internal ID for file naming
            agents.append({"_id": file_path.stem, "data": agent})
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to parse agent {file_path.name}: {e}{Colors.ENDC}")

    return agents

def scan_skills(root_dir: Path) -> List[Dict]:
    """Scan skill definitions and keep them as individual files for Kiro."""
    skills = []
    skills_dir = root_dir / "skills"
    
    if not skills_dir.exists():
        return []

    print_step(f"Scanning skills in {skills_dir}...")
    
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
            
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            # We just need the ID and path to copy it later
            skills.append({
                "id": skill_dir.name,
                "path": skill_file,
                "relative_path": skill_dir.name + "/SKILL.md"
            })
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to process skill {skill_dir.name}: {e}{Colors.ENDC}")

    return skills

def scan_workflows(root_dir: Path) -> List[Dict]:
    """Scan and parse workflows."""
    workflows = []
    workflows_dir = root_dir / "workflows"
    
    if not workflows_dir.exists():
        return []

    print_step(f"Scanning workflows in {workflows_dir}...")
    
    for file_path in workflows_dir.glob("*.md"):
        try:
            content = file_path.read_text(encoding='utf-8')
            meta, body = parse_frontmatter(content)
            
            # Format description
            description = meta.get("description", "")
            if isinstance(description, list):
                description = " ".join(description)

            workflow = {
                "command": f"/{file_path.stem}",
                "description": description,
                "prompt": body
            }
            workflows.append(workflow)
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to parse workflow {file_path.name}: {e}{Colors.ENDC}")

    return workflows

def main():
    parser = argparse.ArgumentParser(description="Convert Antigravity agents to Kiro format")
    parser.add_argument("output_dir", nargs="?", help="Output directory path (e.g. .kiro/)")
    parser.add_argument("--root", default=".agent", help="Path to .agent directory")
    parser.add_argument("--single-file", action="store_true", help="Output to a single JSON file instead of multiple files")
    
    args = parser.parse_args()
    
    root_path = Path(args.root).resolve()
    if not root_path.exists():
        print(f"{Colors.RED}❌ Agent root not found at: {root_path}{Colors.ENDC}")
        return

    # Determine base directory
    base_dir = Path(args.output_dir or ".kiro")
    if not base_dir.exists():
        base_dir.mkdir(parents=True)

    try:
        print(f"\n{Colors.HEADER}🏗️  Building Kiro Configuration...{Colors.ENDC}")
        
        agents = scan_agents(root_path)
        skills = scan_skills(root_path)
        workflows = scan_workflows(root_path)

        if args.single_file:
            # Single file output
            output_path = base_dir / "agent_config.json"
            config = {
                "meta": {
                    "generator": "Antigravity-to-Kiro Converter",
                    "version": "1.3.0"
                },
                "agents": [a["data"] for a in agents]
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print_success(f"Conversion complete! Single config saved to: {output_path}")
        else:
            # Multi-file output (Kiro Standard)
            print_step("Writing agents and skills...")
            
            # 1. Individual Agents in .kiro/agents/
            kiro_agents_dir = base_dir / "agents"
            if not kiro_agents_dir.exists():
                kiro_agents_dir.mkdir(parents=True)
            
            for agent_obj in agents:
                agent_id = agent_obj["_id"]
                agent_data = agent_obj["data"]
                agent_file = kiro_agents_dir / f"{agent_id}.json"
                with open(agent_file, 'w', encoding='utf-8') as f:
                    json.dump(agent_data, f, indent=2, ensure_ascii=False)
            
            # 2. Individual Skills in .kiro/skills/
            kiro_skills_dir = base_dir / "skills"
            for skill in skills:
                dest_dir = kiro_skills_dir / skill["id"]
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True)
                
                # Copy the SKILL.md file
                dest_file = dest_dir / "SKILL.md"
                with open(skill["path"], 'r', encoding='utf-8') as src, \
                     open(dest_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())

            # 3. Workflows in .kiro/steering/ (Standard Kiro pattern for context)
            steering_dir = base_dir / "steering"
            if workflows:
                if not steering_dir.exists():
                    steering_dir.mkdir(parents=True)
                
                for wf in workflows:
                    cmd_name = wf["command"].replace("/", "")
                    wf_file = steering_dir / f"{cmd_name}.md"
                    with open(wf_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Workflow: {wf['command']}\n\n{wf['description']}\n\n{wf['prompt']}")
                    
            print_success(f"Conversion complete! Files saved in: {base_dir}")

        # Summary
        print(f"\n{Colors.HEADER}📊 Summary:{Colors.ENDC}")
        print(f"  • Agents: {len(agents)}")
        print(f"  • Skills: {len(skills)}")
        print(f"  • Workflows: {len(workflows)}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"{Colors.RED}❌ Fatal error: {e}{Colors.ENDC}")

if __name__ == "__main__":
    main()