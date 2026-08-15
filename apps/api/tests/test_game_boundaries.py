from __future__ import annotations

import ast
from pathlib import Path
import unittest


GAME_PACKAGE = Path(__file__).parents[1] / "app" / "game"
FORBIDDEN_ROOTS = {
    "asgi",
    "fastapi",
    "httpx",
    "js",
    "javascript",
    "sqlite3",
    "starlette",
    "websockets",
    "workers",
}


class PureDomainBoundaryTests(unittest.TestCase):
    def test_game_package_has_no_platform_or_transport_imports(self) -> None:
        violations: list[str] = []
        for path in sorted(GAME_PACKAGE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported: list[str] = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = [node.module]
                for module in imported:
                    if module.split(".", 1)[0] in FORBIDDEN_ROOTS:
                        violations.append(f"{path.relative_to(GAME_PACKAGE)}: {module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
