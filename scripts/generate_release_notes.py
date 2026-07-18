# scripts/generate_release_notes.py
import os
import subprocess
import sys
import requests


def get_last_published_release_tag() -> str:
    """
    Gọi GitHub API để lấy tag của bản release đã publish thành công gần nhất.
    Giúp tránh trùng lặp nội dung của các tag bị build lỗi trước đó.
    """
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        return None
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/releases"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        releases = response.json()
        # Lọc bỏ các bản nháp (draft), chỉ lấy các bản đã phát hành thực tế
        published = [r for r in releases if not r.get("draft")]
        if published:
            tag = published[0]["tag_name"]
            print(
                f"GitHub API: Detected last successfully published release tag: {tag}"
            )
            return tag
    except Exception as e:
        print(f"Failed to fetch latest release from GitHub API: {e}")
    return None


def get_git_commit_log():
    """
    Lấy danh sách các commit từ tag stable gần nhất (vX.Y.0) hoặc tag đã publish thành công đến HEAD.
    Nếu không có, lấy tag gần nhất bất kỳ. Nếu vẫn không có, lấy 50 commit gần nhất.
    """
    last_tag = get_last_published_release_tag()
    if last_tag:
        print(f"Using last successfully published release tag: {last_tag}")
    else:
        # 1. Thử tìm tag dạng vX.Y.0 (ví dụ: v1.0.0, v1.1.0) làm base
        try:
            tag_match = subprocess.run(
                [
                    "git",
                    "describe",
                    "--tags",
                    "--abbrev=0",
                    "--match",
                    "v[0-9]*.[0-9]*.0",
                    "HEAD^",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            last_tag = tag_match.stdout.strip()
            print(f"Detecting last stable base tag (fallback): {last_tag}")
        except subprocess.CalledProcessError:
            # 2. Fallback tìm tag bất kỳ gần nhất
            try:
                tag_match = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0", "HEAD^"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                last_tag = tag_match.stdout.strip()
                print(f"Detecting last tag (fallback 2): {last_tag}")
            except subprocess.CalledProcessError:
                pass

    if last_tag:
        commit_range = f"{last_tag}..HEAD"
    else:
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
            check=True,
        )
        return logs.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error fetching git logs: {e.stderr}")
        return ""


def generate_notes_with_mistral(api_key, commits, version, user):
    """
    Gọi API tương thích OpenAI (mặc định Mistral AI) để tạo Release Note chuyên nghiệp.
    """
    from openai import OpenAI

    # Hardcode cấu hình nhà cung cấp mặc định (Mistral AI)
    base_url = "https://api.mistral.ai/v1"
    model = "mistral-large-latest"

    client = OpenAI(api_key=api_key, base_url=base_url)

    repo_name = os.getenv("GITHUB_REPOSITORY", "HaoNgo232/Synapse-Desktop")

    # Prompt chỉ định cấu trúc Release Notes chuẩn chuyên nghiệp dạng Markdown
    system_prompt = (
        "You are an expert software release manager. Your task is to generate professional, structured "
        "and clean release notes in Markdown format for a desktop app named 'Synapse Desktop'.\n"
        "Use proper Markdown formatting: ## for section headers, **bold** for emphasis, - for bullet lists, etc.\n"
        f"CRITICAL: Do NOT invent or change the version or user name. You MUST use '{version}' as the version and '{user}' as the release actor.\n"
        "CRITICAL: Do NOT wrap the entire output in markdown code blocks like ```markdown or ```. Output the raw markdown content directly."
    )

    user_prompt = f"""Please write the release notes based on the following recent git commits:

{commits}

Ensure the output matches this exact Markdown structure (Do NOT wrap the output in ```markdown or ```):

## Synapse Desktop {version}

> Released automatically by **GitHub Actions Bot** (triggered by **{user}**)

Synapse Desktop is a local desktop tool for developers who use AI coding assistants. It lets you manually select project files, package them into a structured prompt, and send that context to any AI web chat for planning, analysis, or patch generation.

---

## What's Changed

(Analyze the commits above and generate a structured changelog here. Group into ### Features, ### Bug Fixes, etc. as appropriate. Use bullet points and keep it concise.
CRITICAL: For every change entry, you MUST extract the corresponding commit hash from the git log and append a GitHub commit reference link at the end of the line, formatted exactly as: `([short_hash](https://github.com/{repo_name}/commit/short_hash))`. Example: `Add security checks ([ee62371](https://github.com/{repo_name}/commit/ee62371))`.)

---

## Included Binaries

- `Synapse-{version}-windows-x64.exe` — Windows x86_64 executable
- `Synapse-{version}-linux-x86_64.AppImage` — Linux x86_64 portable AppImage
"""

    # Thử gọi API với model chính
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        # Nếu model chính bị lỗi (hết rate limit, nghẽn mạng...), tự động thử lại với model phụ (rẻ và nhanh hơn)
        fallback_model = "mistral-small-latest"
        print(
            f"Primary model '{model}' failed: {e}. Trying fallback model '{fallback_model}'..."
        )
        try:
            response = client.chat.completions.create(
                model=fallback_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            print(f"Fallback model '{fallback_model}' succeeded!")
            return response.choices[0].message.content
        except Exception as fallback_err:
            print(f"Fallback model '{fallback_model}' also failed: {fallback_err}")
            sys.exit(1)


def clean_llm_markdown(content: str) -> str:
    """
    Loại bỏ các ký tự bao bọc code block ```markdown ... ``` nếu LLM tự ý thêm vào.
    Điều này giúp GitHub Release render chuẩn Markdown thay vì hiển thị như một code block lớn.
    """
    content = content.strip()
    if content.startswith("```markdown"):
        content = content[len("```markdown") :].strip()
    elif content.startswith("```"):
        content = content[3:].strip()

    if content.endswith("```"):
        content = content[:-3].strip()
    return content


def main():
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("[ERROR] MISTRAL_API_KEY environment variable is missing.")
        sys.exit(1)

    # Lấy tag hiện tại làm version
    version = os.getenv("GITHUB_REF_NAME", "v1.0.0")
    user = os.getenv("GITHUB_ACTOR", "HaoNgo232")

    print("Fetching commit logs...")
    commits = get_git_commit_log()
    if not commits:
        commits = "Initial development and improvements."

    print("Calling Mistral AI to generate release notes...")
    notes = generate_notes_with_mistral(api_key, commits, version, user)
    notes = clean_llm_markdown(notes)

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
