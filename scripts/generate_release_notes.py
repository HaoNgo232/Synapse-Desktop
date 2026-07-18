# scripts/generate_release_notes.py
import os
import subprocess
import sys
import json
import requests

def get_git_commit_log():
    """
    Lấy danh sách các commit từ git tag gần nhất đến HEAD.
    Nếu không có tag cũ, lấy toàn bộ commit history (tối đa 50 commit).
    """
    try:
        # Lấy tag gần nhất
        tag_match = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "HEAD^"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        last_tag = tag_match.stdout.strip()
        print(f"Detecting last tag: {last_tag}")
        commit_range = f"{last_tag}..HEAD"
    except subprocess.CalledProcessError:
        print("No previous tag found, taking recent commits...")
        commit_range = "HEAD~50..HEAD"

    # Lấy commit logs
    log_cmd = ["git", "log", commit_range, "--oneline"]
    try:
        logs = subprocess.run(
            log_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return logs.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error fetching git logs: {e.stderr}")
        return ""

def generate_notes_with_mistral(api_key, commits):
    """
    Gọi Mistral API (model mistral-large-latest) để tạo Release Note chuyên nghiệp.
    """
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Prompt chỉ định cấu trúc Release Notes chuẩn chuyên nghiệp dạng Plain Text theo ý người dùng
    system_prompt = (
        "You are an expert software release manager. Your task is to generate professional, structured "
        "and clean release notes for a desktop app named 'Synapse Desktop'.\n"
        "Use ONLY plain-text formatting (no markdown header symbols like #, ##, ###, no bolding with **). "
        "Use numbered sections like '1. Summary', '2. Features', '3. Included Binaries' for headers.\n"
        "Keep the language natural, concise, and focused on developers."
    )

    user_prompt = f"""Please write the release notes based on the following recent git commits:

{commits}

Ensure the output matches this exact plain-text structure:

Synapse Desktop [VERSION] Latest
released by [USER]

This is the release of Synapse Desktop — a local desktop tool for developers who use AI coding assistants. It lets you manually select project files, package them into a structured prompt, and send that context to any AI web chat for planning, analysis, or patch generation.

Architecture Support
Target Platform: Optimized and built for x86_64 (AMD64) architectures.
ARM Support: ARM architectures are currently untested and not officially supported in this build.

Key Features
1. Visual File Selection: Open a project folder and tick files in a tree view. Token count updates in real time.
2. Real-Time Token Counter: Live token usage bar with context window tracking.
3. Context Presets: Save/load file selections and instructions as named presets.
4. Related Files Auto-Detection: Automatically add imported files at configurable depth (1–5).
5. Improve Instructions: Automatically rewrite and optimize raw prompts using LLM API in plain text format.
6. Smart Context Mode: Copy code structure only (signatures, docstrings, declarations) — ~70% token savings.
7. Apply Tab — Patch Workflow: Paste Search/Replace blocks from AI, preview visual diffs, apply with automatic backups.
8. History Tab: Full history of apply operations with re-apply support.
9. Git Diff Integration: Append staged/unstaged changes to context.
10. Secret Scanning: Built-in detect-secrets scanning prevents accidental credential exposure.

Included Binaries
- Synapse-[VERSION]-windows-x64.exe (Windows x86_64 executable)
- Synapse-[VERSION]-linux-x86_64.AppImage (Linux x86_64 portable AppImage)
"""

    payload = {
        "model": "mistral-large-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"API Request to Mistral failed: {e}")
        sys.exit(1)

def main():
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("[ERROR] MISTRAL_API_KEY environment variable is missing.")
        sys.exit(1)

    # Lấy tag hiện tại làm version
    version = os.getenv("GITHUB_REF_NAME", "v1.0.0")

    print("Fetching commit logs...")
    commits = get_git_commit_log()
    if not commits:
        commits = "Initial development and improvements."

    print("Calling Mistral AI to generate release notes...")
    notes = generate_notes_with_mistral(api_key, commits)

    # Thay thế version động
    notes = notes.replace("[VERSION]", version)
    notes = notes.replace("[USER]", os.getenv("GITHUB_ACTOR", "HaoNgo232"))

    # Lưu vào file build/release_notes.txt để workflow sử dụng
    os.makedirs("build", exist_ok=True)
    with open("build/release_notes.txt", "w", encoding="utf-8") as f:
        f.write(notes)

    print("Release notes generated successfully in build/release_notes.txt!")
    print("----------------------------------------")
    print(notes)
    print("----------------------------------------")

if __name__ == "__main__":
    main()
