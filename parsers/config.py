"""Configuración externalizada para Parser Core 2.0.

Jerarquía (de menor a mayor prioridad):
  1. Defaults duros en código
  2. parser_config.toml
  3. Variables de entorno PARSER_*
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OcrConfig:
    engine: str = "tesseract"
    tesseract_path: str = "/usr/local/bin/tesseract"
    tessdata_dir: str = "/usr/local/share/tessdata"
    pdftoppm_path: str = "/usr/local/bin/pdftoppm"
    dpi: int = 250
    timeout_per_page: int = 120
    lang: str = "spa"


@dataclass
class DetectionConfig:
    code_format_sample_lines: int = 60
    separator_sample_lines: int = 80
    fuzzy_threshold: int = 92


@dataclass
class LayoutConfig:
    enable_detection: bool = True
    fallback_to_heuristic: bool = True
    header_lexicon: tuple[str, ...] = (
        "activo", "pasivo", "perdida", "ganancia",
        "deudor", "acreedor", "patrimonio", "resultado",
        "activos", "pasivos", "ingresos", "gastos",
        "cuenta", "cuentas", "codigo", "nombre",
        "saldo", "debe", "haber",
    )


@dataclass
class CachingConfig:
    enabled: bool = False
    cache_dir: str = ".parser_cache"
    ttl_days: int = 30


@dataclass
class ParserConfig:
    ocr: OcrConfig = field(default_factory=OcrConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    caching: CachingConfig = field(default_factory=CachingConfig)

    _env_prefix: str = "PARSER_"

    @classmethod
    def from_toml(cls, path: str | Path) -> ParserConfig:
        cfg = cls()
        p = Path(path)
        if not p.exists():
            return cfg
        raw: dict[str, Any]
        with open(p, "rb") as f:
            raw = tomllib.load(f)
        _merge(raw, cfg)
        return cfg

    @classmethod
    def load(cls, toml_path: str | Path | None = None) -> ParserConfig:
        cfg = cls.from_toml(toml_path) if toml_path else cls()
        _apply_env(cfg, cls._env_prefix)
        return cfg


_SEARCH_PATHS = [
    "parser_config.toml",
    "config/parser_config.toml",
    os.path.expanduser("~/.homologacion/parser_config.toml"),
    os.environ.get("PARSER_CONFIG_PATH", ""),
]


def load_config(path: str | Path | None = None) -> ParserConfig:
    if path:
        return ParserConfig.load(path)
    for sp in _SEARCH_PATHS:
        if sp and Path(sp).exists():
            return ParserConfig.load(sp)
    return ParserConfig.load()


# ─── Merge helpers ───

_NESTED_MAP = {
    "ocr": "ocr",
    "detection": "detection",
    "layout": "layout",
    "caching": "caching",
}


def _merge(raw: dict, cfg: ParserConfig) -> None:
    for key, attr in _NESTED_MAP.items():
        section = raw.get(key, {})
        if not section:
            continue
        target = getattr(cfg, attr)
        for k, v in section.items():
            if hasattr(target, k):
                setattr(target, k, v)


def _apply_env(cfg: ParserConfig, prefix: str) -> None:
    for attr_name in ("ocr", "detection", "layout", "caching"):
        section = getattr(cfg, attr_name)
        for field_name in [f for f in dir(section) if not f.startswith("_")]:
            env_key = f"{prefix}{attr_name.upper()}_{field_name.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                _coerce_set(section, field_name, val)


def _coerce_set(obj, field: str, val: str):
    current = getattr(obj, field)
    if isinstance(current, bool):
        setattr(obj, field, val.lower() in ("1", "true", "yes"))
    elif isinstance(current, int):
        setattr(obj, field, int(val))
    elif isinstance(current, float):
        setattr(obj, field, float(val))
    else:
        setattr(obj, field, val)
