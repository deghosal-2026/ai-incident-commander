"""Tests for the cadence module: cadence_timer_node, _get_cadence_minutes."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from incident_commander.config import Config
from incident_commander.models.state import IncidentState
from incident_commander.nodes.cadence import _get_cadence_minutes, cadence_timer_node, init_config
from tests.conftest import make_sev1_alert, make_sev3_alert


class TestCadenceTimerNode:
    """cadence_timer_node — sets next_update_time based on severity."""

    def _reset_config(self) -> None:
        init_config(Config(cadence={"SEV1": 5, "SEV2": 15, "SEV3": 30}))

    def test_sev1_sets_5_min_cadence(self) -> None:
        """SEV1 alert -> next_update_time = alert.timestamp + 5min."""
        self._reset_config()
        alert = make_sev1_alert()
        state = IncidentState(alert=alert, severity="SEV1")
        result = cadence_timer_node(state)
        expected = alert.timestamp + timedelta(minutes=5)
        assert result.next_update_time == expected

    def test_sev2_sets_15_min_cadence(self) -> None:
        """SEV2 alert -> next_update_time = alert.timestamp + 15min."""
        self._reset_config()
        alert = make_sev1_alert()
        state = IncidentState(alert=alert, severity="SEV2")
        result = cadence_timer_node(state)
        expected = alert.timestamp + timedelta(minutes=15)
        assert result.next_update_time == expected

    def test_sev3_sets_30_min_cadence(self) -> None:
        """SEV3 alert -> next_update_time = alert.timestamp + 30min."""
        self._reset_config()
        alert = make_sev3_alert()
        state = IncidentState(alert=alert, severity="SEV3")
        result = cadence_timer_node(state)
        expected = alert.timestamp + timedelta(minutes=30)
        assert result.next_update_time == expected

    def test_uses_last_update_time_when_set(self) -> None:
        """When last_update_time is set, base is last_update_time."""
        self._reset_config()
        alert = make_sev1_alert()
        last_time = alert.timestamp + timedelta(minutes=10)
        state = IncidentState(alert=alert, severity="SEV1", last_update_time=last_time)
        result = cadence_timer_node(state)
        expected = last_time + timedelta(minutes=5)
        assert result.next_update_time == expected

    def test_fallback_to_datetime_now_when_no_alert_and_no_last_update(self) -> None:
        """No alert and no last_update_time -> base is datetime.now() (mocked)."""
        self._reset_config()
        fake_now = datetime(2026, 7, 13, 13, 0, 0)
        with patch("incident_commander.nodes.cadence.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.timedelta = timedelta
            state = IncidentState(alert=None, severity="SEV1")
            result = cadence_timer_node(state)
            expected = fake_now + timedelta(minutes=5)
            assert result.next_update_time == expected

    def test_unknown_severity_defaults_to_30_min(self) -> None:
        """Unknown severity -> 30 min default."""
        self._reset_config()
        alert = make_sev1_alert()
        state = IncidentState.model_construct(
            alert=alert, severity="UNKNOWN",
        )
        result = cadence_timer_node(state)
        expected = alert.timestamp + timedelta(minutes=30)
        assert result.next_update_time == expected

    def test_init_config_with_custom_cadence(self) -> None:
        """Custom cadence dict passed to init_config -> custom values honored."""
        init_config(Config(cadence={"SEV1": 1, "SEV2": 2, "SEV3": 3}))
        alert = make_sev1_alert()
        state = IncidentState(alert=alert, severity="SEV1")
        result = cadence_timer_node(state)
        expected = alert.timestamp + timedelta(minutes=1)
        assert result.next_update_time == expected


class TestGetCadenceMinutes:
    """_get_cadence_minutes — returns interval given severity."""

    def test_init_config_not_called_uses_default(self) -> None:
        """init_config not called -> uses DEFAULT_CADENCE values."""
        init_config(Config(cadence={"SEV1": 5, "SEV2": 15, "SEV3": 30}))
        assert _get_cadence_minutes("SEV1") == 5
        assert _get_cadence_minutes("SEV2") == 15
        assert _get_cadence_minutes("SEV3") == 30

    def test_custom_config_honored(self) -> None:
        """Custom cadence dict -> custom values honored."""
        init_config(Config(cadence={"SEV1": 10, "SEV2": 20, "SEV3": 60}))
        assert _get_cadence_minutes("SEV1") == 10
        assert _get_cadence_minutes("SEV2") == 20
        assert _get_cadence_minutes("SEV3") == 60

    def test_unknown_severity_returns_30(self) -> None:
        """Unknown severity -> returns 30."""
        init_config(Config(cadence={"SEV1": 5, "SEV2": 15, "SEV3": 30}))
        assert _get_cadence_minutes("SEV4") == 30
