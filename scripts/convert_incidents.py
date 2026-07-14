"""Convert public incident datasets into ai-incident-commander fixture format."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq


FIXTURE_DIR = Path("tests/fixtures/real-data")
DATASET_DIR = Path("data/raw")


# ── Helpers ──────────────────────────────────────────────────────────


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, data: object) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _log(msg: str) -> None:
    print(f"  {msg}")


# ── OpenRCA2 Converter ───────────────────────────────────────────────


def convert_openrca2(count: int) -> None:
    """Convert OpenRCA2 v1-500 cases into fixtures.

    Selectively downloads only the files needed for each case
    (injection.json, env.json, causal_graph.json, abnormal_logs.parquet)
    — ~50-100MB total for 50 cases, not the full 3.6GB dataset.
    """
    from huggingface_hub import hf_hub_download

    repo_id = "lincyaw/openrca2-v1-500"
    repo_type = "dataset"
    needed_files = ["injection.json", "env.json", "causal_graph.json",
                    "abnormal_logs.parquet", "conclusion.parquet"]

    _log("Downloading MANIFEST...")
    manifest_path = hf_hub_download(repo_id=repo_id, repo_type=repo_type,
                                     filename="MANIFEST.json")
    manifest = json.loads(Path(manifest_path).read_text())
    cases = manifest["cases"][:count]
    converted = 0

    for case in cases:
        name = case["name"]
        _log(f"Downloading {name}...")
        case_dir = _ensure_dir(DATASET_DIR / "openrca2" / name)
        try:
            for fname in needed_files:
                try:
                    hf_hub_download(repo_id=repo_id, repo_type=repo_type,
                                    filename=f"{name}/{fname}",
                                    local_dir=str(DATASET_DIR / "openrca2"))
                except Exception:
                    pass  # file not available for this case
            _convert_one_openrca2(case, case_dir)
            converted += 1
        except Exception as e:
            _log(f"  Error converting {name}: {e}")

    _log(f"Converted {converted}/{len(cases)} OpenRCA2 cases")


def _convert_one_openrca2(case: dict, case_dir: Path) -> None:
    name = case["name"]
    system = case.get("system", "unknown")
    chaos_family = case.get("chaos_family", "unknown")
    slug = f"openrca-{name.lower()}"

    out_dir = _ensure_dir(FIXTURE_DIR / slug)

    # Load injection.json for ground truth
    inj_path = case_dir / "injection.json"
    injection = json.loads(inj_path.read_text()) if inj_path.exists() else {}

    # Extract root cause from engine_config
    engine_config = injection.get("engine_config", [])
    if isinstance(engine_config, str):
        try:
            engine_config = json.loads(engine_config)
        except (json.JSONDecodeError, TypeError):
            engine_config = []

    ground_truth = injection.get("ground_truth", injection.get("description", ""))
    if isinstance(ground_truth, dict):
        ground_truth = str(ground_truth)

    root_cause = ground_truth or f"{chaos_family} failure in {system}"
    root_cause_key_terms = []
    for cfg in engine_config if isinstance(engine_config, list) else []:
        app = cfg.get("app", "")
        chaos_type = cfg.get("chaos_type", "")
        if app:
            root_cause_key_terms.append(app)
        if chaos_type:
            root_cause_key_terms.append(chaos_type)

    # Build alert.json
    start_time = case.get("start_time", "")
    if start_time:
        try:
            dt = datetime.fromisoformat(start_time)
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    affected_services = case.get("root_services", [system])

    alert = {
        "severity": "SEV1",
        "service": affected_services[0] if affected_services else system,
        "summary": f"{chaos_family} anomaly in {system} affecting {', '.join(affected_services)}",
        "source": f"openrca2/{system}",
        "timestamp": dt.isoformat(),
        "metadata": {
            "system": system,
            "chaos_family": chaos_family,
            "affected_services": affected_services,
        },
    }

    # Build meta.json
    meta = {
        "incident_id": f"OPENRCA-{name[-12:]}",
        "source_type": "openrca2",
        "service": alert["service"],
        "severity": "SEV1",
        "start_time": alert["timestamp"],
        "system": system,
        "chaos_family": chaos_family,
    }

    # Convert logs from parquet
    logs = []
    log_path = case_dir / "abnormal_logs.parquet"
    if log_path.exists():
        try:
            table = pq.read_table(str(log_path))
            for row in table.to_pylist():
                ts = row.get("timestamp", "")
                if isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                logs.append({
                    "timestamp": ts,
                    "level": str(row.get("level", row.get("severity", "INFO"))).upper(),
                    "message": str(row.get("body", row.get("message", ""))),
                    "source": str(row.get("service", row.get("source", system))),
                })
        except Exception as e:
            _log(f"  Warning: couldn't parse logs for {name}: {e}")

    # Build ground_truth.json
    ground_truth_data = {
        "schema_version": "1.0",
        "incident_id": meta["incident_id"],
        "source_type": "openrca2",
        "source_url": f"https://huggingface.co/datasets/lincyaw/openrca2-v1-500",
        "company": f"OpenRCA2 ({system})",
        "root_cause": root_cause,
        "root_cause_key_terms": root_cause_key_terms,
        "timeline_events": [],
        "action_items": [],
        "impact": f"{chaos_family} failure in {system} for Duration unknown",
        "severity": "SEV1",
        "service": alert["service"],
    }

    _write_json(out_dir / "meta.json", meta)
    _write_json(out_dir / "alert.json", alert)
    _write_json(out_dir / "logs.json", logs)
    _write_json(out_dir / "ground_truth.json", ground_truth_data)

    # README
    (out_dir / "README.md").write_text(
        f"# {name}\n\n"
        f"**Source:** OpenRCA2 v1-500\n"
        f"**System:** {system}\n"
        f"**Chaos family:** {chaos_family}\n"
        f"**Services:** {', '.join(affected_services)}\n"
    )


# ── opensre-incident-trajectories Converter ──────────────────────────


def convert_opensre(count: int) -> None:
    """Convert opensre-incident-trajectories into fixtures.

    Uses already-downloaded data in data/raw/opensre/ (1.1MB).
    Selects 'real' incidents first, then 'synthetic' to fill.
    """
    raw_dir = DATASET_DIR / "opensre"
    incidents = []

    real_path = raw_dir / "real" / "real.jsonl"
    if real_path.exists():
        with open(real_path) as f:
            for line in f:
                if line.strip():
                    incidents.append(json.loads(line))

    if len(incidents) < count:
        synth_path = raw_dir / "synthetic" / "synthetic.jsonl"
        if synth_path.exists():
            with open(synth_path) as f:
                for line in f:
                    if line.strip() and len(incidents) < count:
                        incidents.append(json.loads(line))

    incidents = incidents[:count]
    converted = 0
    for inc in incidents:
        try:
            _convert_one_opensre(inc)
            converted += 1
        except Exception as e:
            _log(f"  Error converting {inc.get('scenario_id', '?')}: {e}")

    _log(f"Converted {converted}/{len(incidents)} opensre incidents")


def _convert_one_opensre(inc: dict) -> None:
    sid = inc.get("scenario_id", "unknown")
    slug = f"opensre-{sid}"
    out_dir = _ensure_dir(FIXTURE_DIR / slug)

    source_company = inc.get("source_company", "unknown")
    source_url = inc.get("source_url", "")
    answer = inc.get("answer", "")
    trap_actions = inc.get("trap_actions", [])

    meta = {
        "incident_id": sid,
        "source_type": "opensre",
        "service": source_company.lower().replace(" ", "-"),
        "severity": "SEV1",
        "start_time": "",
        "company": source_company,
    }

    alert = {
        "severity": "SEV1",
        "service": meta["service"],
        "summary": f"Incident at {source_company}: {answer[:100]}",
        "source": f"opensre/{source_company.lower().replace(' ', '-')}",
        "timestamp": "",
    }

    logs = []
    for tool_call in inc.get("tool_transcripts", []):
        logs.append({
            "timestamp": "",
            "level": "INFO",
            "message": str(tool_call),
            "source": "opensre-simulated",
        })

    ground_truth = {
        "schema_version": "1.0",
        "incident_id": sid,
        "source_type": "opensre",
        "source_url": source_url,
        "company": source_company,
        "root_cause": answer,
        "root_cause_key_terms": [],
        "timeline_events": [],
        "action_items": [],
        "trap_actions": trap_actions,
        "impact": f"Incident at {source_company}",
        "severity": "SEV1",
        "service": meta["service"],
    }

    _write_json(out_dir / "meta.json", meta)
    _write_json(out_dir / "alert.json", alert)
    _write_json(out_dir / "logs.json", logs)
    _write_json(out_dir / "ground_truth.json", ground_truth)
    (out_dir / "README.md").write_text(
        f"# {sid}\n\n"
        f"**Source:** opensre-incident-trajectories\n"
        f"**Company:** {source_company}\n"
        f"**Postmortem:** {source_url}\n"
    )


# ── IntelligentDDS Converter ─────────────────────────────────────────


def convert_intelligentdds(count: int) -> None:
    """Convert IntelligentDDS structured postmortems into fixtures."""
    raw_dir = DATASET_DIR / "intelligentdds" / "anomaly_collection"
    all_incidents = []

    for provider_dir in sorted(raw_dir.iterdir()):
        if not provider_dir.is_dir():
            continue
        for f in sorted(provider_dir.iterdir()):
            if f.suffix == ".json":
                data = json.loads(f.read_text())
                for incident_id, incident in data.items():
                    incident["_provider"] = provider_dir.name
                    incident["_id"] = incident_id
                    all_incidents.append(incident)

    all_incidents = all_incidents[:count]
    converted = 0
    for inc in all_incidents:
        try:
            _convert_one_intelligentdds(inc)
            converted += 1
        except Exception as e:
            _log(f"  Error converting {inc.get('_id', '?')}: {e}")

    _log(f"Converted {converted}/{len(all_incidents)} IntelligentDDS incidents")


def _convert_one_intelligentdds(inc: dict) -> None:
    inc_id = inc.get("_id", "unknown")
    provider = inc.get("_provider", "unknown")
    slug = f"intelligentdds-{provider}-{inc_id}"
    out_dir = _ensure_dir(FIXTURE_DIR / slug)

    title = inc.get("title", "")
    summary = inc.get("summary", "")
    details = inc.get("details", "")
    root_cause_text = summary or details[:500]
    services = inc.get("service_name", [])
    impact = inc.get("impact_symptom", [])
    time_str = inc.get("time", "")

    # Parse date from time field (e.g. "06/04/2011" -> ISO)
    from datetime import datetime, timezone
    try:
        dt = datetime.strptime(time_str, "%m/%d/%Y").replace(tzinfo=timezone.utc)
        timestamp = dt.isoformat()
    except (ValueError, TypeError):
        timestamp = datetime.now(timezone.utc).isoformat()

    meta = {
        "incident_id": inc_id,
        "source_type": "intelligentdds",
        "service": services[0] if services else provider,
        "severity": "SEV1",
        "start_time": timestamp,
        "provider": provider,
    }

    alert = {
        "severity": "SEV1",
        "service": meta["service"],
        "summary": title,
        "source": f"intelligentdds/{provider}",
        "timestamp": timestamp,
    }

    ground_truth = {
        "schema_version": "1.0",
        "incident_id": inc_id,
        "source_type": "intelligentdds",
        "source_url": "",
        "company": provider.upper(),
        "root_cause": root_cause_text,
        "root_cause_key_terms": services,
        "timeline_events": [],
        "action_items": [],
        "impact": ", ".join(impact) if impact else summary[:200],
        "severity": "SEV1",
        "service": meta["service"],
    }

    _write_json(out_dir / "meta.json", meta)
    _write_json(out_dir / "alert.json", alert)
    _write_json(out_dir / "logs.json", [])
    _write_json(out_dir / "ground_truth.json", ground_truth)
    (out_dir / "README.md").write_text(f"# {title}\n\n**Source:** IntelligentDDS ({provider})\n")


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert incident datasets to fixtures")
    parser.add_argument("--source", required=True,
                        choices=["openrca2", "opensre", "intelligentdds", "blog", "all"])
    parser.add_argument("--count", type=int, default=10,
                        help="Number of incidents to convert (default: 10)")
    args = parser.parse_args()

    _ensure_dir(FIXTURE_DIR)

    converters = {
        "openrca2": convert_openrca2,
        "opensre": convert_opensre,
        "intelligentdds": convert_intelligentdds,
    }

    if args.source == "all":
        for name, fn in converters.items():
            _log(f"\n=== Converting {args.count} from {name} ===")
            fn(args.count)
    else:
        _log(f"Converting {args.count} incidents from {args.source}...")
        converters[args.source](args.count)

    _log("Done.")


if __name__ == "__main__":
    main()
