# Changelog

All notable changes to ai-incident-commander will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Incident simulation with 8 pre-built scenarios
- Timeline construction (multi-source, trust hierarchy)
- GitHub deploy correlation (30-min window, strong/weak)
- Stakeholder communication (consequence-first, pasteable comms blocks)
- Remediation suggestion with dry-run simulation (LLM-predicted, not executed)
- COE-format postmortem (blameless, AI-labeled, severity-conditional sections)
- RAG runbook retrieval (in-memory + Qdrant)
- Cost tracking with LLM observability per node (JSONL log)
- Session persistence (JSON file-based)
- Three ingestion channels (CLI flags, input directory, Python API)
- Markdown output directory (10 files)
- JSON Schema definitions (16 schemas, PD-CEF aligned)
- Auto-approve mode for CI/pipelines
- CLI (simulate, run, timeline, postmortem, export-schemas, validate)
- Python API (run_incident, run_simulation)

### Changed
- `LLMRouter.generate()`: replaced stub (returning empty responses) with real HTTP client for OpenAI-compatible endpoints
- Postmortem parser: handles markdown-formatted section headers (`### 1. SUMMARY`) and leading numbering
- Citation parser: normalizes to `Source:` prefix format

### Fixed
- Postmortem sections not being parsed from LLM responses (markdown header stripping)
- IntelligentDDS fixture timestamps (populated from raw data time field)
- CLI `--alert` no longer required when `--input-dir` is provided
- `simulate` and `run` commands now delegate to API functions for output writing
- `run_simulation` passes service/severity/scenario through to simulator (was hardcoded SEV1)
- `ChatMessage.thread_ts` made optional (allows null values in fixture data)
