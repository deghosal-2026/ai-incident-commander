"""Tests for graph.py routing functions: _is_resolved, _approval_router, etc."""

from __future__ import annotations

from incident_commander.graph import (
    _approval_router,
    _is_resolved,
    _postmortem_router,
    _remediation_router,
)
from incident_commander.models.state import IncidentState


class TestIsResolved:
    """_is_resolved — conditional edge after produce_output."""

    def test_resolved_true_returns_remediate(self) -> None:
        """resolved=True -> returns 'remediate'."""
        state = IncidentState(resolved=True)
        assert _is_resolved(state) == "remediate"

    def test_resolved_false_returns_continue(self) -> None:
        """resolved=False -> returns 'continue'."""
        state = IncidentState(resolved=False)
        assert _is_resolved(state) == "continue"


class TestApprovalRouter:
    """_approval_router — stakeholder update approval gate."""

    def test_approved_returns_approved(self) -> None:
        """update_approved=True -> returns 'approved'."""
        state = IncidentState(update_approved=True)
        assert _approval_router(state) == "approved"

    def test_not_approved_returns_rejected(self) -> None:
        """update_approved=False -> returns 'rejected'."""
        state = IncidentState(update_approved=False)
        assert _approval_router(state) == "rejected"


class TestRemediationRouter:
    """_remediation_router — remediation approval gate."""

    def test_approved_returns_approved(self) -> None:
        """remediation_approved=True -> returns 'approved'."""
        state = IncidentState(remediation_approved=True)
        assert _remediation_router(state) == "approved"

    def test_not_approved_returns_rejected(self) -> None:
        """remediation_approved=False -> returns 'rejected'."""
        state = IncidentState(remediation_approved=False)
        assert _remediation_router(state) == "rejected"


class TestPostmortemRouter:
    """_postmortem_router — postmortem approval gate."""

    def test_approved_returns_approved(self) -> None:
        """postmortem_approved=True -> returns 'approved'."""
        state = IncidentState(postmortem_approved=True)
        assert _postmortem_router(state) == "approved"

    def test_not_approved_returns_rejected(self) -> None:
        """postmortem_approved=False -> returns 'rejected'."""
        state = IncidentState(postmortem_approved=False)
        assert _postmortem_router(state) == "rejected"
