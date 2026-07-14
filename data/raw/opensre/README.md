---
license: apache-2.0
language:
- en
pretty_name: OpenSRE Incident-Diagnosis Trajectories
size_categories:
- n<1K
task_categories:
- text-generation
tags:
- sre
- incident-response
- root-cause-analysis
- agent-trajectories
- reinforcement-learning
- rl
- hud
- postmortem
- llm-as-judge
- benchmark
source_datasets:
- original
annotations_creators:
- machine-generated
language_creators:
- machine-generated
configs:
- config_name: all
  default: true
  data_files:
  - split: train
    path: hud_trajectories.jsonl
- config_name: synthetic
  data_files:
  - split: train
    path: synthetic/*.jsonl
- config_name: real
  data_files:
  - split: train
    path: real/*.jsonl
dataset_info:
- config_name: all
  features:
  - name: model
    dtype: string
  - name: trace_id
    dtype: string
  - name: scenario_id
    dtype: string
  - name: incident
    dtype: string
  - name: source
    dtype: string
  - name: reward
    dtype: float32
  - name: subscores
    struct:
    - name: root_cause_category
      dtype: float32
    - name: evidence_keywords
      dtype: float32
    - name: ruled_out_red_herrings
      dtype: float32
    - name: remediation_tool
      dtype: float32
  - name: n_tool_calls
    dtype: int32
  - name: tools_used
    sequence: string
  - name: n_agent_steps
    dtype: int32
  - name: true_category
    dtype: string
  - name: difficulty
    dtype: int32
  - name: source_company
    dtype: string
  - name: source_url
    dtype: string
  - name: trap_actions
    sequence: string
  - name: answer
    dtype: string
  splits:
  - name: train
    num_examples: 197
- config_name: synthetic
  splits:
  - name: train
    num_examples: 83
- config_name: real
  splits:
  - name: train
    num_examples: 114
---

# OpenSRE Incident-Diagnosis Trajectories

Graded, multi-step **SRE incident-diagnosis** trajectories. A frozen LLM reads evidence through
diagnostic tools (`describe_pod` / `get_events` / `get_logs` / `get_metrics` / `query_traces` / …),
states a root cause + category + fix, and is scored on **substance** against ground truth. Built as a
HUD v6 RL environment with a deliberate model **spanning set** so difficulty is legible and the
within-group reward spread is real (the GRPO learning signal).

**197 trajectories** across a weak→strong model set and two splits:

- **`synthetic`** (83) — 15 single-fault incident types (`oom_kill`, `cpu_saturation`, `cache_flush`, …).
- **`real`** (114) — **19 verified real-world cascading outages** (CircleCI, Datadog, Slack, GitHub,
  Cloudflare, AWS, LaunchDarkly, incident.io). Each has a *misleading loud symptom*, a buried root
  cause, and a **trap action** (the naive fix that actually worsened the incident). Every real record
  carries `source_company` + `source_url` back to its first-party postmortem, plus `trap_actions`.

## Loading

```python
from datasets import load_dataset

ds      = load_dataset("<org>/opensre-incident-trajectories", split="train")              # all 197
real    = load_dataset("<org>/opensre-incident-trajectories", "real", split="train")      # 114
synth   = load_dataset("<org>/opensre-incident-trajectories", "synthetic", split="train") # 83
```

## Leaderboard (spanning set)

| model | n | mean reward | std |
|---|---|---|---|
| claude-opus-4-8 | 68 | 0.561 | 0.215 |
| kimi-k2p5 | 61 | 0.491 | 0.237 |
| claude-haiku-4-5 | 68 | 0.462 | 0.225 |

Split means: **synthetic** 0.511 · **real** 0.501. The real *individual* incidents are the hardest
(the genuine traps): `launchdarkly_legacy_routing_cold_cache` (0.20), `aws_dynamodb_dns_enactor`
(0.25), `github_mysql_semaphore_rename` (0.27), `aws_kinesis_cell_manager` (0.30),
`github_proxysql_fd_limit` (0.33), `circleci_kubeproxy_iptables` (0.35).

## Record schema (one JSON object per rollout)

```jsonc
{
  "model": "claude-opus-4-8",
  "trace_id": "5983a82035274898b48f0d101307a09d",
  "scenario_id": "104-slack_tgw_fd_exhaustion",
  "incident": "slack_tgw_fd_exhaustion",
  "source": "real",                       // "real" | "synthetic"
  "reward": 0.42,                          // weighted total in [0,1]
  "subscores": {                           // the four grader components
    "root_cause_category":  0.15,
    "evidence_keywords":    0.45,
    "ruled_out_red_herrings": 0.20,
    "remediation_tool":     0.00
  },
  "n_tool_calls": 7,
  "tools_used": ["get_alerts", "get_metrics", "..."],
  "n_agent_steps": 8,
  "true_category": "network_fault",
  "difficulty": 4,                         // real-only; 0 for synthetic
  "source_company": "Slack",               // real-only
  "source_url": "https://slack.engineering/slacks-outage-on-january-4th-2021/",
  "trap_actions": ["scale the web tier UP while the TGW is saturated ..."],
  "answer": "ROOT_CAUSE: ...\nROOT_CAUSE_CATEGORY: ...\nFIX: ..."
}
```

## Grading

The deterministic judge credits four components: the **correct root-cause category** (not the
misleading loud one), **evidence keywords** surfaced from the tool transcript, **ruled-out red
herrings**, and the **correct remediation tool**. `trap_actions` are included in the data so a
follow-up trap-fix-penalty grader can be added.

## Intended uses

- **Eval / benchmark** of LLM SRE root-cause reasoning under misleading symptoms.
- **RL / GRPO** fine-tuning data — the model spanning set yields real within-group reward spread.
- **Postmortem study** of real cascading outages with first-party source links.

## Limitations & ethics

- Trajectories come from a small set of frozen LLMs; not a human-annotated gold corpus.
- `real` incidents are reconstructed from public first-party postmortems (links provided); the
  simulated tool evidence approximates, and does not reproduce, the original production telemetry.
- Reward is an automatic proxy, not a human judgment of remediation quality.

## Citation

```bibtex
@misc{opensre_trajectories_2026,
  title  = {OpenSRE Incident-Diagnosis Trajectories},
  author = {SRE-Degrees RL Project},
  year   = {2026},
  howpublished = {HuggingFace Datasets},
  note   = {https://github.com/ashishranjan2404/infra-ops-agent}
}
```

Source + reproduction: `github.com/ashishranjan2404/infra-ops-agent` (branch `opensre-traj`).
