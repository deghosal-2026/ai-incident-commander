"""Markdown formatters for all incident output types."""

from __future__ import annotations

from typing import Any

from incident_commander.models.state import (
    CostReport,
    Postmortem,
    RemediationSuggestion,
    StakeholderUpdate,
)


def format_summary_md(result: dict[str, Any]) -> str:
    """Incident summary table + key events."""
    lines = [
        "# Incident Summary\n",
    ]
    thread = result.get("thread_id", "unknown")
    lines.append(f"- **Incident ID:** {result.get('incident_id', thread)}")
    lines.append(f"- **Service:** {result.get('service', 'unknown')}")
    lines.append(f"- **Severity:** {result.get('severity', 'SEV3')}")

    postmortem = result.get("postmortem")
    if postmortem:
        lines.append(f"- **Resolved:** {'Yes' if postmortem.get('resolved_at') else 'No'}")
        mttr = postmortem.get("mttr_minutes")
        if mttr is not None:
            lines.append(f"- **MTTR:** {mttr} min")

    cost = result.get("cost_report")
    if cost:
        lines.append(f"- **Total Cost:** ${cost.get('total_estimated_cost_usd', 0):.4f}")
        models = cost.get("models_used", [])
        if models:
            lines.append(f"- **Models Used:** {', '.join(models)}")

    dc = result.get("deploy_correlations", [])
    if dc:
        c = dc[0]
        pr = c.get("pr_number")
        cs = c.get("correlation_strength", "")
        lines.append(f"- **Deploy Correlation:** PR #{pr} ({cs})")

    lines.append(f"- **Session:** {thread}")

    updates = result.get("stakeholder_updates", [])
    if updates:
        lines.append("\n## Key Events")
        for u in updates:
            # Truncate impact to 100 chars so the summary table stays readable
            lines.append(f"- **Update {u.get('update_number')}:** {u.get('impact', '')[:100]}")

    lines.append("")
    return "\n".join(lines)


def format_timeline_md(timeline: list[dict[str, Any]] | None) -> str:
    """Chronological timeline table."""
    if not timeline:
        return "# Timeline\n\nNo timeline events recorded.\n"

    lines = [
        "# Timeline\n",
        "| Time | Source | Event | Trust | Deploy Correlation |",
        "|------|--------|-------|-------|--------------------|",
    ]
    for e in timeline:
        ts = e.get("timestamp", "")
        source = e.get("source", "")
        content = e.get("content", "")
        trust = e.get("trust_level", "")
        dc = "Yes" if e.get("deploy_correlation") else ""
        lines.append(f"| {ts} | {source} | {content} | {trust} | {dc} |")

    lines.append("")
    return "\n".join(lines)


def format_updates_md(updates: list[StakeholderUpdate] | None) -> str:
    """Stakeholder updates in consequence-first format."""
    if not updates:
        return "# Stakeholder Updates\n\nNo stakeholder updates drafted.\n"

    lines = ["# Stakeholder Updates\n"]
    for u in updates:
        lines.append(f"## Update {u.update_number}")
        lines.append(f"- **Impact:** {u.impact}")
        lines.append(f"- **Root Cause:** {u.root_cause_hypothesis}")
        lines.append(f"- **Action:** {u.action}")
        lines.append(f"- **Next Update:** {u.next_update_time}")
        lines.append(f"- **Confidence:** {u.confidence:.2f}")
        if u.approved:
            lines.append("- **Status:** ✅ Approved")
        lines.append("")

    return "\n".join(lines)


def format_remediation_md(suggestions: list[RemediationSuggestion] | None) -> str:
    """Remediation suggestions with citations."""
    if not suggestions:
        return "# Remediation\n\nNo remediation suggestions.\n"

    lines = ["# Remediation\n"]
    for s in suggestions:
        lines.append(f"## {s.action}")
        lines.append(f"- **Citation:** {s.citation}")
        lines.append(f"- **Confidence:** {s.confidence:.2f}")
        if s.dry_run_outcome:
            lines.append(f"- **Expected Outcome:** {s.dry_run_outcome}")
        if s.similar_incidents:
            lines.append(f"- **Similar Incidents:** {', '.join(s.similar_incidents)}")
        lines.append(f"- **Approved:** {'Yes' if s.approved else 'No'}")
        lines.append("")

    return "\n".join(lines)


def _section_md(
    section: dict[str, Any] | None,
    label: str,
) -> list[str]:
    """Render a single PostmortemSection as markdown lines."""
    if section is None:
        return []
    # Tag each postmortem section with its provenance so human reviewers know what to trust
    ai_tag = (
        " *[AI-GENERATED — review carefully]*"
        if section.get("ai_generated")
        else " *[From session data]*"
    )
    return [
        f"## {section.get('title', label)}{ai_tag}",
        section.get("content", ""),
        "",
    ]


def format_postmortem_md(postmortem: Postmortem | None) -> str:
    """COE-format postmortem with AI section labels."""
    if postmortem is None:
        return "# Postmortem\n\nNo postmortem generated.\n"

    lines = [
        f"# Postmortem: {postmortem.incident_id}",
        f"- **Service:** {postmortem.service}",
        f"- **Severity:** {postmortem.severity}",
        f"- **Date:** {postmortem.incident_date}",
        "",
    ]

    lines.extend(_section_md(postmortem.summary.model_dump(), "Summary"))
    ci = postmortem.customer_impact
    lines.extend(_section_md(ci.model_dump() if ci else None, "Customer Impact"))
    lines.extend(_section_md(postmortem.timeline.model_dump(), "Timeline"))
    lines.extend(_section_md(postmortem.root_cause_analysis.model_dump(), "Root Cause Analysis"))
    lines.extend(
        _section_md(
            postmortem.systemic_contributing_factors.model_dump(),
            "Systemic Contributing Factors",
        )
    )

    if postmortem.action_items:
        lines.append("## Action Items")
        for ai in postmortem.action_items:
            ai_gen = " *[AI-generated]*" if ai.ai_generated else ""
            lines.append(
                f"- **{ai.description}** — owner: {ai.suggested_owner},"
                f" priority: {ai.priority}{ai_gen}"
            )
        lines.append("")

    scl = postmortem.stakeholder_communication_log
    lines.extend(
        _section_md(
            scl.model_dump() if scl else None,
            "Stakeholder Communication Log",
        )
    )
    rci = postmortem.regulatory_compliance_impact
    lines.extend(
        _section_md(
            rci.model_dump() if rci else None,
            "Regulatory/Compliance Impact",
        )
    )

    if postmortem.mttr_minutes is not None:
        lines.append(f"- **MTTR:** {postmortem.mttr_minutes} minutes")

    # AI Section Labels summary
    lines.append("\n---\n")
    lines.append("### AI Section Labels")
    lines.append("| Section | Source |")
    lines.append("|---------|--------|")
    sections_to_label = [
        ("Summary", postmortem.summary.ai_generated),
        ("Timeline", postmortem.timeline.ai_generated),
        ("Root Cause Analysis", postmortem.root_cause_analysis.ai_generated),
        ("Systemic Factors", postmortem.systemic_contributing_factors.ai_generated),
    ]
    if postmortem.customer_impact:
        sections_to_label.append(("Customer Impact", postmortem.customer_impact.ai_generated))
    if postmortem.stakeholder_communication_log:
        sections_to_label.append(
            ("Stakeholder Comm Log", postmortem.stakeholder_communication_log.ai_generated)
        )
    if postmortem.regulatory_compliance_impact:
        sections_to_label.append(
            ("Regulatory Impact", postmortem.regulatory_compliance_impact.ai_generated)
        )

    for title, ai_generated in sections_to_label:
        source = "AI-generated" if ai_generated else "Session data"
        lines.append(f"| {title} | {source} |")
    lines.append("")

    return "\n".join(lines)


def format_cost_md(cost_report: CostReport | None) -> str:
    """Cost report with summary and per-node breakdown."""
    if cost_report is None:
        return "# Cost Report\n\nNo cost data available.\n"

    lines = [
        "# Cost Report\n",
        "### Summary",
        f"- **Total Input Tokens:** {cost_report.total_input_tokens:,}",
        f"- **Total Output Tokens:** {cost_report.total_output_tokens:,}",
        f"- **Total Tokens:** {cost_report.total_tokens:,}",
        f"- **Total Estimated Cost:** ${cost_report.total_estimated_cost_usd:.6f}",
        f"- **Models Used:** {', '.join(cost_report.models_used)}",
        "",
    ]

    if cost_report.per_node:
        lines.append("### Per-Node Breakdown")
        lines.append("| Node | Model | Input | Output | Total | Cost (USD) | Latency (ms) |")
        lines.append("|------|-------|-------|--------|-------|------------|--------------|")
        for node in cost_report.per_node:
            lines.append(
                f"| {node.node_name} | {node.llm_model} "
                f"| {node.input_tokens:,} | {node.output_tokens:,} "
                f"| {node.total_tokens:,} | ${node.estimated_cost_usd:.6f} "
                f"| {node.latency_ms} |"
            )
        lines.append("")

    return "\n".join(lines)
