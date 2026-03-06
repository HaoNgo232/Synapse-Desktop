"""
Batch/parallel token counting - Pure utility functions.

REFACTORED: Toan bo logic batch processing da duoc chuyen sang
services.tokenization_service.TokenizationService.

Module nay chi chua cac ham tien ich con duoc re-export
boi TokenizationService:
- get_worker_count(): Tinh so workers toi uu

DIP: Module nay KHONG import tu services layer.
"""

import os

# Worker initialization la expensive, nen dung it threads tru khi co nhieu files
TASKS_PER_WORKER = 100

# So file toi thieu de trigger parallel processing
MIN_FILES_FOR_PARALLEL = 10


def get_worker_count(num_tasks: int) -> int:
    """
    Tinh so luong workers toi uu dua tren so luong tasks va CPU cores.

    Logic port tu Repomix:
    - Moi worker xu ly ~100 tasks.
    - Khong vuot qua so CPU cores.
    - Toi thieu 1 worker.

    Args:
        num_tasks: So luong tasks can xu ly.

    Returns:
        So luong workers toi uu.
    """
    cpu_count = os.cpu_count() or 4
    calculated = (num_tasks + TASKS_PER_WORKER - 1) // TASKS_PER_WORKER
    return max(1, min(cpu_count, calculated))
