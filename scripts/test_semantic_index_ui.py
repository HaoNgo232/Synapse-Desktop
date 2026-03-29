import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from application.services.prompt_build_service import PromptBuildService
from infrastructure.filesystem.ignore_engine import IgnoreEngine
from application.services.graph_service import GraphService
from application.services.tokenization_service import TokenizationService


def test_formats():
    workspace = Path(__file__).parent.parent

    ignore_engine = IgnoreEngine()
    graph_service = GraphService(ignore_engine=ignore_engine)

    print("Building graph...")
    graph_service.ensure_built(workspace)

    tokenizer = TokenizationService()
    service = PromptBuildService(
        tokenization_service=tokenizer, graph_service=graph_service
    )

    test_files = [workspace / "application" / "services" / "prompt_build_service.py"]

    for fmt in ["plain", "xml"]:
        prompt, _, _ = service.build_prompt(
            file_paths=test_files,
            workspace=workspace,
            instructions="Refactor this",
            output_format=fmt,
            include_git_changes=True,
            use_relative_paths=True,
        )
        with open(f"scripts/out_{fmt}.txt", "w") as f:
            f.write(prompt)
        print(f"Generated {fmt}")


if __name__ == "__main__":
    test_formats()
