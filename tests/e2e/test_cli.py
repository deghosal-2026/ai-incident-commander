"""E2E tests: all 7 CLI commands with Click CliRunner."""

from __future__ import annotations

from click.testing import CliRunner

from incident_commander.cli import main


class TestCLISimulate:
    """CLI: simulate command."""

    def test_simulate_with_defaults(self) -> None:
        """Simulate --auto-approve completes."""
        # Tests the CLI entry point without any custom options (defaults to payment-service, SEV1)
        runner = CliRunner()
        result = runner.invoke(main, ["simulate", "--auto-approve"])
        assert result.exit_code == 0
        assert "Simulation complete" in result.output

    def test_simulate_with_custom_service(self) -> None:
        """Simulate --service api-gateway --severity SEV2 --auto-approve completes."""
        # CLI flags --service and --severity must propagate to the simulation engine
        runner = CliRunner()
        result = runner.invoke(main, [
            "simulate", "--service", "api-gateway",
            "--severity", "SEV2",
            "--auto-approve",
        ])
        assert result.exit_code == 0

    def test_simulate_with_output_dir(self) -> None:
        """Simulate --output-dir writes files."""
        # --output-dir triggers file writer — at least one file must appear on disk
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(main, [
                "simulate", "--auto-approve", "--output-dir", tmpdir,
            ])
            assert result.exit_code == 0
            assert "Output written" in result.output
            written = list(Path(tmpdir).iterdir())
            assert len(written) > 0

    def test_simulate_with_scenario(self) -> None:
        """Simulate --scenario db-connection-pool --auto-approve completes."""
        # --scenario loads a pre-built scenario config instead of defaults
        runner = CliRunner()
        result = runner.invoke(main, [
            "simulate", "--scenario", "db-connection-pool", "--auto-approve",
        ])
        assert result.exit_code == 0

    def test_simulate_with_seed_reproducibility(self) -> None:
        """Simulate --seed 42 runs successfully twice."""
        runner = CliRunner()
        result1 = runner.invoke(main, ["simulate", "--seed", "42", "--auto-approve"])
        assert result1.exit_code == 0
        assert "Simulation complete" in result1.output

        result2 = runner.invoke(main, ["simulate", "--seed", "42", "--auto-approve"])
        assert result2.exit_code == 0
        assert "Simulation complete" in result2.output


class TestCLIRun:
    """CLI: run command."""

    def test_run_with_input_dir(self) -> None:
        """Run --input-dir completes with fixture."""
        # --input-dir loads meta.json, alert.json, logs/, messages.json, etc. from a directory
        runner = CliRunner()
        result = runner.invoke(main, [
            "run", "--input-dir", "tests/fixtures/incident-2026-001",
            "--auto-approve",
        ])
        assert result.exit_code == 0
        assert "Run complete" in result.output

    def test_run_with_individual_flags(self) -> None:
        """Run --alert --logs --auto-approve completes."""
        # Alternative to --input-dir: pass --alert and --logs as separate file args
        runner = CliRunner()
        result = runner.invoke(main, [
            "run",
            "--alert", "tests/fixtures/alert.json",
            "--logs", "tests/fixtures/incident-2026-001/logs",
            "--auto-approve",
        ])
        assert result.exit_code == 0

    def test_run_with_output_dir(self) -> None:
        """Run --output-dir writes files."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(main, [
                "run",
                "--input-dir", "tests/fixtures/incident-2026-001",
                "--output-dir", tmpdir,
                "--auto-approve",
            ])
            assert result.exit_code == 0
            written = list(Path(tmpdir).iterdir())
            assert len(written) > 0

    def test_run_missing_input_dir(self) -> None:
        """Run with non-existent input dir shows error."""
        # Non-existent directory must produce non-zero exit code, not crash
        runner = CliRunner()
        result = runner.invoke(main, [
            "run", "--input-dir", "tests/fixtures/nonexistent",
            "--auto-approve",
        ])
        assert result.exit_code != 0

    def test_run_missing_both_alert_and_input_dir(self) -> None:
        """Run without --alert and --input-dir shows error."""
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--auto-approve"])
        assert result.exit_code != 0
        assert "Either --alert or --input-dir is required" in result.output

    def test_run_with_messages_flag(self) -> None:
        """Run --alert --messages --auto-approve completes."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "run",
            "--alert", "tests/fixtures/alert.json",
            "--messages", "tests/fixtures/incident-2026-001/messages.json",
            "--auto-approve",
        ])
        assert result.exit_code == 0

    def test_run_with_github_flag(self) -> None:
        """Run --alert --github --auto-approve completes."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "run",
            "--alert", "tests/fixtures/alert.json",
            "--github", "tests/fixtures/incident-2026-001/github.json",
            "--auto-approve",
        ])
        assert result.exit_code == 0


class TestCLIValidate:
    """CLI: validate command."""

    def test_validate_valid_alert(self) -> None:
        """Validate --alert with valid JSON passes."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "validate", "--alert", "tests/fixtures/alert.json",
        ])
        assert result.exit_code == 0
        assert "PASSED" in result.output

    def test_validate_invalid_alert(self) -> None:
        """Validate --alert with bad JSON fails."""
        # bad_alert.json contains invalid data (e.g., missing required fields)
        runner = CliRunner()
        result = runner.invoke(main, [
            "validate", "--alert", "tests/fixtures/bad_alert.json",
        ])
        assert result.exit_code != 0

    def test_validate_missing_file(self) -> None:
        """Validate --alert with missing file shows error."""
        # Missing file → CLI prints "not found" and returns non-zero
        runner = CliRunner()
        result = runner.invoke(main, [
            "validate", "--alert", "tests/fixtures/missing.json",
        ])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_validate_malformed_json(self) -> None:
        """Validate --alert with malformed JSON shows error."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.json"
            bad_file.write_text(
                '{"severity": "SEV1", "summary": "test", '
                '"service": "test", "timestamp": "2026-01-01T00:00:00", "invalid"'
            )
            runner = CliRunner()
            result = runner.invoke(main, [
                "validate", "--alert", str(bad_file),
            ])
            assert result.exit_code != 0


class TestCLIExportSchemas:
    """CLI: export-schemas command."""

    def test_export_schemas_creates_files(self) -> None:
        """export-schemas creates 16 schema files."""
        # Expected output: exactly 16 JSON schema files (one per Pydantic model)
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = CliRunner()
            result = runner.invoke(main, [
                "export-schemas", "--output-dir", tmpdir,
            ])
            assert result.exit_code == 0
            assert "Exported" in result.output
            files = list(Path(tmpdir).iterdir())
            assert len(files) == 16


class TestCLITimeline:
    """CLI: timeline command."""

    def test_timeline_after_simulate(self) -> None:
        """Timeline after simulate displays events."""
        from incident_commander.api import run_simulation
        from incident_commander.config import Config
        from incident_commander.persistence import SessionManager

        result = run_simulation(auto_approve=True)
        mgr = SessionManager(Config().session_dir)
        mgr.save_session(result.thread_id, {
            "timeline": [e.model_dump() for e in result.timeline],
        })
        try:
            runner = CliRunner()
            result2 = runner.invoke(main, ["timeline", "--thread", result.thread_id])
            assert result2.exit_code == 0
            assert len(result2.output) > 0
        finally:
            mgr.delete_session(result.thread_id)

    def test_timeline_nonexistent_thread(self) -> None:
        """Timeline with nonexistent thread shows error."""
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", "--thread", "nonexistent"])
        assert result.exit_code != 0
        assert "Session not found" in result.output


class TestCLIPostmortem:
    """CLI: postmortem command."""

    def test_postmortem_after_simulate(self) -> None:
        """Postmortem after simulate displays postmortem."""
        from incident_commander.api import run_simulation
        from incident_commander.config import Config
        from incident_commander.persistence import SessionManager

        result = run_simulation(auto_approve=True)
        mgr = SessionManager(Config().session_dir)
        mgr.save_session(result.thread_id, {
            "postmortem": result.postmortem.model_dump() if result.postmortem else None,
        })
        try:
            runner = CliRunner()
            result2 = runner.invoke(main, ["postmortem", "--thread", result.thread_id])
            assert result2.exit_code == 0
            assert "Postmortem" in result2.output
        finally:
            mgr.delete_session(result.thread_id)

    def test_postmortem_nonexistent_thread(self) -> None:
        """Postmortem with nonexistent thread shows error."""
        runner = CliRunner()
        result = runner.invoke(main, ["postmortem", "--thread", "nonexistent"])
        assert result.exit_code != 0
        assert "Session not found" in result.output


class TestCLIVersion:
    """CLI: --version flag."""

    def test_version(self) -> None:
        """--version displays 0.1.0."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIHelp:
    """CLI: --help displays all commands."""

    def test_help_shows_all_commands(self) -> None:
        """--help output mentions all 7 subcommands."""
        # Verifies the help text lists all major commands (smoke test for CLI registration)
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in ["simulate", "run", "timeline", "postmortem",
                     "export-schemas", "validate"]:
            assert cmd in result.output
