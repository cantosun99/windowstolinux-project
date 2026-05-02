"""Migrationsbericht mit Jinja2 als HTML-String rendern."""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from windowstolinux.models import Report

logger = logging.getLogger(__name__)

_TEMPLATE_DIR  = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "report.html.j2"

# Jinja2-Umgebung wird einmalig erstellt und für alle Aufrufe wiederverwendet.
_env: jinja2.Environment | None = None


def _get_env() -> jinja2.Environment:
    global _env
    if _env is None:
        _env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=jinja2.select_autoescape(["html", "j2"]),
            undefined=jinja2.StrictUndefined,
        )
    return _env


def render_html(report: Report) -> str:
    """Rendert den Bericht als selbstenthaltenen HTML-String."""
    template = _get_env().get_template(_TEMPLATE_NAME)
    html = template.render(report=report)
    logger.debug(f"HTML gerendert ({len(html)} Bytes)")
    return html
