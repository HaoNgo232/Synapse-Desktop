"""Tests for import parser utilities."""

import importlib
from pathlib import Path
from typing import Protocol, cast


class _ExtractLocalImportsFn(Protocol):
    def __call__(self, file_path: Path, workspace_root: Path) -> list[str]: ...


class _GetRelatedFilesFn(Protocol):
    def __call__(
        self,
        changed_files: list[str],
        workspace_root: Path,
        depth: int = 1,
        max_files: int = 20,
    ) -> list[str]: ...


_import_parser_module = importlib.import_module("shared.utils.import_parser")

extract_local_imports = cast(
    _ExtractLocalImportsFn,
    getattr(_import_parser_module, "extract_local_imports"),
)
get_related_files = cast(
    _GetRelatedFilesFn,
    getattr(_import_parser_module, "get_related_files"),
)


def test_python_imports(tmp_path: Path) -> None:
    file = tmp_path / "src" / "app.py"
    file.parent.mkdir(parents=True)
    file.write_text(
        """
import os
import sys
from src.utils import helper
from src.models.user import User
from ..config import settings
import requests
""",
        encoding="utf-8",
    )

    (tmp_path / "src" / "utils.py").write_text("def helper():\n    return True\n")
    (tmp_path / "src" / "models").mkdir(parents=True)
    (tmp_path / "src" / "models" / "user.py").write_text("class User:\n    pass\n")

    imports = extract_local_imports(file, tmp_path)

    assert "src/utils.py" in imports or "src/utils/__init__.py" in imports
    assert "src/models/user.py" in imports or "src/models/user/__init__.py" in imports
    assert all("requests" not in path for path in imports)


def test_typescript_imports(tmp_path: Path) -> None:
    file = tmp_path / "src" / "App.tsx"
    file.parent.mkdir(parents=True)
    file.write_text(
        """
import React from 'react';
import { helper } from './utils';
import { User } from '../models/User';
const config = require('./config');
""",
        encoding="utf-8",
    )

    (tmp_path / "src" / "utils.ts").write_text("export const helper = () => true;\n")
    (tmp_path / "models").mkdir(parents=True)
    (tmp_path / "models" / "User.ts").write_text("export type User = { id: string };\n")
    (tmp_path / "src" / "config.ts").write_text("export const value = 1;\n")

    imports = extract_local_imports(file, tmp_path)

    assert any("utils" in p for p in imports)
    assert any("User" in p for p in imports)
    assert not any("react" in p for p in imports)


def test_related_files_depth_1(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("from src.utils import helper\n", encoding="utf-8")
    (src / "utils.py").write_text(
        "from src.helpers import do_thing\n", encoding="utf-8"
    )
    (src / "helpers.py").write_text("def do_thing():\n    pass\n", encoding="utf-8")

    related = get_related_files(["src/app.py"], tmp_path, depth=1)
    assert any("utils" in f for f in related)
    assert not any("helpers" in f for f in related)


def test_related_files_depth_2(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("from src.utils import helper\n", encoding="utf-8")
    (src / "utils.py").write_text(
        "from src.helpers import do_thing\n", encoding="utf-8"
    )
    (src / "helpers.py").write_text("def do_thing():\n    pass\n", encoding="utf-8")

    related = get_related_files(["src/app.py"], tmp_path, depth=2)
    assert any("utils" in f for f in related)
    assert any("helpers" in f for f in related)
