"""Inventario estático reproducible de módulos y entrypoints del proyecto.

El análisis es deliberadamente conservador: sólo sigue imports representables
por el AST de Python. No interpreta ``importlib``, rutas construidas en runtime
ni el efecto funcional de una bandera. El JSON resultante sirve como evidencia
de due diligence, no como autorización automática para borrar código.
"""

from __future__ import annotations

import argparse
import ast
from collections import deque
import json
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable


IGNORED_PARTS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache"})
OFFLINE_ROOTS = frozenset({"deployment", "scripts", "tools"})
TLS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CERT" "_NONE", re.compile(r"\b(?:ssl\.)?CERT" r"_NONE\b")),
    ("check_hostname_false", re.compile(r"\bcheck_hostname\s*=\s*False\b")),
)


def _is_ignored(path: Path) -> bool:
    return bool(IGNORED_PARTS.intersection(path.parts))


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _python_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*.py") if not _is_ignored(path)),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _resolve_internal(candidate: str, modules: set[str]) -> str | None:
    value = candidate.strip(".")
    while value:
        if value in modules:
            return value
        value = value.rpartition(".")[0]
    return None


def _relative_base(current: str, *, is_package: bool, level: int) -> list[str]:
    package = current.split(".") if is_package else current.split(".")[:-1]
    remove = max(level - 1, 0)
    if remove > len(package):
        return []
    return package[: len(package) - remove] if remove else package


def _static_imports(
    path: Path,
    root: Path,
    current: str,
    modules: set[str],
) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    found: set[str] = set()
    is_package = path.name == "__init__.py"
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = _relative_base(
                    current, is_package=is_package, level=node.level,
                )
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    candidates.append(".".join(filter(None, (base, alias.name))))
            candidates.append(base)
        for candidate in candidates:
            resolved = _resolve_internal(candidate, modules)
            if resolved and resolved != current:
                found.add(resolved)
    return sorted(found)


def _has_main_guard(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        try:
            expression = ast.unparse(node.test)
        except Exception:  # pragma: no cover - defensa por versión de AST
            continue
        if "__name__" in expression and "__main__" in expression:
            return True
    return False


def _target_module(target: str) -> str:
    value = target.split(":", 1)[0].strip()
    if value.endswith(".py"):
        return value[:-3].replace("/", ".")
    return value.replace("/", ".")


def _declared_entrypoints(root: Path, modules: set[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        for name, raw_target in sorted(scripts.items()):
            target = str(raw_target)
            module = _target_module(target)
            entries.append({
                "kind": "poetry_script",
                "name": name,
                "target": target,
                "module": module,
                "exists": module in modules,
            })

    render = root / "render.yaml"
    dockerfiles: set[Path] = set()
    if render.is_file():
        text = render.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"^\s*dockerfilePath:\s*(\S+)\s*$", text, re.MULTILINE):
            dockerfiles.add(root / match.group(1).removeprefix("./"))
        for match in re.finditer(
            r"^\s*(?:startCommand|command):\s*[^\n]*?streamlit\s+run\s+(\S+\.py)",
            text,
            re.MULTILINE,
        ):
            target = match.group(1).strip("'\"")
            module = _target_module(target)
            entries.append({
                "kind": "render_command",
                "name": "render",
                "target": target,
                "module": module,
                "exists": module in modules,
            })

    if not dockerfiles and (root / "Dockerfile").is_file():
        dockerfiles.add(root / "Dockerfile")
    for dockerfile in sorted(dockerfiles):
        if not dockerfile.is_file():
            continue
        text = dockerfile.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"streamlit\s+run\s+([^\s'\"\]]+\.py)", text):
            target = match.group(1)
            module = _target_module(target)
            entries.append({
                "kind": "docker_command",
                "name": dockerfile.relative_to(root).as_posix(),
                "target": target,
                "module": module,
                "exists": module in modules,
            })

    unique = {
        (entry["kind"], entry["name"], entry["target"]): entry
        for entry in entries
    }
    return [unique[key] for key in sorted(unique)]


def _reachable(seeds: Iterable[str], graph: dict[str, list[str]]) -> set[str]:
    visited: set[str] = set()
    queue = deque(sorted(set(seeds)))
    while queue:
        current = queue.popleft()
        if current in visited or current not in graph:
            continue
        visited.add(current)
        queue.extend(graph[current])
    return visited


def _tls_bypasses(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        if "tests" in path.relative_to(root).parts:
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1,
        ):
            for name, pattern in TLS_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "path": path.relative_to(root).as_posix(),
                        "line": line_number,
                        "rule": name,
                    })
    return sorted(findings, key=lambda value: (value["path"], value["line"], value["rule"]))


def build_inventory(root: str | Path) -> dict[str, Any]:
    project_root = Path(root).resolve()
    paths = _python_files(project_root)
    module_paths = {
        _module_name(path, project_root): path
        for path in paths
        if _module_name(path, project_root)
    }
    all_modules = set(module_paths)
    runtime_modules = {
        module for module, path in module_paths.items()
        if "tests" not in path.relative_to(project_root).parts
    }
    test_modules = all_modules - runtime_modules
    graph = {
        module: _static_imports(path, project_root, module, all_modules)
        for module, path in module_paths.items()
    }
    entries = _declared_entrypoints(project_root, runtime_modules)
    production_seeds = {
        entry["module"] for entry in entries if entry["exists"]
        and entry["kind"] in {"render_command", "docker_command"}
    }
    production = _reachable(production_seeds, graph)
    test_seeds = {
        dependency
        for module in test_modules
        for dependency in graph[module]
        if dependency in runtime_modules
    }
    tests_reachable = _reachable(test_seeds, graph)

    inbound_runtime: dict[str, set[str]] = {module: set() for module in runtime_modules}
    inbound_tests: dict[str, set[str]] = {module: set() for module in runtime_modules}
    for consumer, dependencies in graph.items():
        destination = inbound_tests if consumer in test_modules else inbound_runtime
        for dependency in dependencies:
            if dependency in runtime_modules:
                destination[dependency].add(consumer)

    records: list[dict[str, Any]] = []
    self_declared: list[dict[str, Any]] = []
    entry_modules = {entry["module"] for entry in entries if entry["exists"]}
    for module in sorted(runtime_modules):
        path = module_paths[module]
        relative = path.relative_to(project_root)
        main_guard = _has_main_guard(path)
        if main_guard:
            self_declared.append({
                "kind": "python_main_guard",
                "name": relative.as_posix(),
                "target": relative.as_posix(),
                "module": module,
                "exists": True,
            })
        top = relative.parts[0]
        if top == "shadow":
            status = "shadow"
        elif module in production:
            status = "productive"
        elif top in OFFLINE_ROOTS or main_guard:
            status = "offline"
        elif module in tests_reachable:
            status = "tests_only"
        else:
            status = "orphan"
        records.append({
            "module": module,
            "path": relative.as_posix(),
            "lines": len(path.read_text(encoding="utf-8", errors="ignore").splitlines()),
            "status": status,
            "declared_entrypoint": module in entry_modules,
            "main_guard": main_guard,
            "imports": [value for value in graph[module] if value in runtime_modules],
            "inbound_runtime": sorted(inbound_runtime[module]),
            "inbound_tests": sorted(inbound_tests[module]),
        })

    entries = sorted(
        entries + self_declared,
        key=lambda value: (value["kind"], value["name"], value["target"]),
    )
    nonexistent = [entry for entry in entries if not entry["exists"]]
    no_consumers = [
        record["module"] for record in records
        if not record["inbound_runtime"] and not record["inbound_tests"]
        and not record["declared_entrypoint"] and not record["main_guard"]
    ]
    tests_only = [record["module"] for record in records if record["status"] == "tests_only"]
    orphan = [record["module"] for record in records if record["status"] == "orphan"]
    status_counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("productive", "shadow", "offline", "tests_only", "orphan")
    }
    return {
        "schema_version": 1,
        "analysis": {
            "root": ".",
            "scope": "static_python_imports",
            "dynamic_imports_resolved": False,
            "status_precedence": [
                "shadow", "productive", "offline", "tests_only", "orphan",
            ],
            "production_entrypoint_kinds": ["docker_command", "render_command"],
            "offline_roots": sorted(OFFLINE_ROOTS),
        },
        "summary": {
            "runtime_modules": len(records),
            "runtime_lines": sum(record["lines"] for record in records),
            "test_modules": len(test_modules),
            "test_lines": sum(
                len(module_paths[module].read_text(
                    encoding="utf-8", errors="ignore",
                ).splitlines())
                for module in test_modules
            ),
            "status_counts": status_counts,
        },
        "entrypoints": entries,
        "modules": records,
        "findings": {
            "nonexistent_entrypoints": nonexistent,
            "tls_bypasses": _tls_bypasses(paths, project_root),
            "modules_without_consumers": sorted(no_consumers),
            "tests_only_modules": sorted(tests_only),
            "orphan_modules": sorted(orphan),
        },
    }


def _serialize(report: dict[str, Any], *, pretty: bool) -> str:
    return json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="Raíz del proyecto a inventariar.",
    )
    parser.add_argument("--output", type=Path, help="Archivo JSON de salida.")
    parser.add_argument("--pretty", action="store_true", help="JSON indentado.")
    parser.add_argument(
        "--fail-on-security",
        action="store_true",
        help="Retorna 2 si detecta bypass TLS; no falla por huérfanos.",
    )
    args = parser.parse_args()
    report = build_inventory(args.root)
    payload = _serialize(report, pretty=args.pretty)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if args.fail_on_security and report["findings"]["tls_bypasses"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
