"""MarkdownOutputWriter — writes all incident output files to a directory."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from incident_commander.models.output import IncidentResult

from .comms_blocks import format_comms_blocks_md
from .formatters import (
    format_cost_md,
    format_postmortem_md,
    format_remediation_md,
    format_summary_md,
    format_timeline_md,
    format_updates_md,
)

logger = logging.getLogger(__name__)


class MarkdownOutputWriter:
    """Writes all incident output files to a directory.

    Produces 10 files per SPEC §13.5:
    - incident-summary.md, timeline.md, stakeholder-updates.md
    - comms-blocks.md, remediation.md, postmortem.md, cost-report.md
    - llm-calls.jsonl, session.json, meta.json
    """

    def __init__(self, output_dir: str | Path) -> None:
        """Initialize with an output directory."""
        self._output_dir = Path(output_dir).expanduser()

    def _ensure_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    def write_all(self, result: IncidentResult) -> list[Path]:
        """Write all output files and return their paths."""
        out = self._ensure_dir()
        files: list[Path] = []

        result_dict = result.model_dump()

        writers: list[tuple[str, str]] = [
            ("incident-summary.md", format_summary_md(result_dict)),
            ("timeline.md", format_timeline_md(
                [e.model_dump() for e in result.timeline] if result.timeline else None
            )),
            ("stakeholder-updates.md", format_updates_md(result.stakeholder_updates)),
            ("comms-blocks.md", format_comms_blocks_md(result)),
            ("remediation.md", format_remediation_md(result.remediation_suggestions)),
            ("postmortem.md", format_postmortem_md(result.postmortem)),
            ("cost-report.md", format_cost_md(result.cost_report)),
        ]

        for filename, content in writers:
            path = out / filename
            try:
                path.write_text(content)
                files.append(path)
            except OSError as exc:
                logger.error("Failed to write %s: %s", path, exc)
                raise

        # Write llm-calls.jsonl — copy from output dir if observer wrote there
        jsonl_path = out / "llm-calls.jsonl"
        try:
            if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
                jsonl_path.write_text("")
            files.append(jsonl_path)
        except OSError as exc:
            logger.error("Failed to write %s: %s", jsonl_path, exc)
            raise

        # Write session.json — full result snapshot; default=str handles datetimes and other non-serializable types
        session_path = out / "session.json"
        try:
            session_path.write_text(json.dumps(result_dict, indent=2, default=str))
            files.append(session_path)
        except OSError as exc:
            logger.error("Failed to write %s: %s", session_path, exc)
            raise

        # Write meta.json
        meta_path = out / "meta.json"
        try:
            meta = {
                "thread_id": result.thread_id,
                "generated_at": datetime.now().isoformat(),
                "version": "0.1.0",
            }
            meta_path.write_text(json.dumps(meta, indent=2))
            files.append(meta_path)
        except OSError as exc:
            logger.error("Failed to write %s: %s", meta_path, exc)
            raise

        return files
