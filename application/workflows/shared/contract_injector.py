"""
Contract Injector - Helper để load contract pack và inject vào workflow handoff.

Dùng cho tất cả workflow tools (rp_build, rp_design, rp_review, etc.)
để đảm bảo agent nhìn thấy workspace constraints.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from domain.contracts.contract_pack import ContractPack

if TYPE_CHECKING:
    from application.workflows.shared.handoff_formatter import HandoffContext

logger = logging.getLogger(__name__)


def load_and_format_contract_pack(workspace_root: Path) -> Optional[str]:
    """Load contract pack từ workspace và format cho prompt inclusion.

    Args:
        workspace_root: Workspace root path

    Returns:
        Formatted contract pack string, hoặc None nếu không có contract.
    """
    try:
        contract_file = workspace_root / ".synapse" / "contract_pack.json"
        if not contract_file.exists():
            return None

        import json

        data = json.loads(contract_file.read_text(encoding="utf-8"))
        pack = ContractPack.from_dict(data)

        formatted = pack.format_for_prompt()
        return formatted if formatted and formatted.strip() else None
    except Exception as e:
        logger.warning("Failed to load contract pack: %s", e)
        return None


def inject_contract_pack_to_handoff(
    handoff_context: "HandoffContext", workspace_root: Path
) -> None:
    """Inject contract pack vào HandoffContext.extra_sections.

    Modifies handoff_context in-place.

    Args:
        handoff_context: HandoffContext để inject vào
        workspace_root: Workspace root path
    """
    contract_formatted = load_and_format_contract_pack(workspace_root)
    if contract_formatted:
        handoff_context.extra_sections["contract_pack"] = contract_formatted
