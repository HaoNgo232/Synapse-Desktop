import sys
import re
from pathlib import Path

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python scratch/task_brief.py PLAN_FILE TASK_NUMBER [OUTFILE]")
        sys.exit(2)

    plan_path = Path(sys.argv[1])
    task_num = sys.argv[2]
    
    if not plan_path.exists():
        print(f"No such plan file: {plan_path}", file=sys.stderr)
        sys.exit(2)

    if len(sys.argv) == 4:
        out_path = Path(sys.argv[3])
    else:
        # Default OUTFILE: .git/sdd/task-N-brief.md
        out_path = Path(".git/sdd") / f"task-{task_num}-brief.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(plan_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    task_lines = []
    in_fence = False
    in_task = False

    # Regex to match task heading like: "### Task 1: Asset Downloader"
    task_header_re = re.compile(rf"^#+\s+Task\s+{task_num}(?:[^0-9]|$)", re.IGNORECASE)
    any_task_header_re = re.compile(r"^#+\s+Task\s+\d+", re.IGNORECASE)

    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
        
        if not in_fence:
            if task_header_re.match(line):
                in_task = True
            elif any_task_header_re.match(line) and in_task:
                # Reached next task heading
                break
        
        if in_task:
            task_lines.append(line)

    if not task_lines:
        print(f"Task {task_num} not found in {plan_path}", file=sys.stderr)
        sys.exit(3)

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(task_lines)

    print(f"Wrote {out_path}: {len(task_lines)} lines")

if __name__ == "__main__":
    main()
