"""Data ingestion: input directory loader, log parser, notes parser, normalizer."""

# Planned ingestion modules (S4):
#   loader.py
#     load_input_dir(path) -> RawInput
#       Discover and read all supported files in the input directory.
#   log_parser.py
#     parse_logs(raw_files) -> list[LogEvent]
#       Parse structured (JSON/CSV) and unstructured (text) log files
#       into timestamped log events.
#   chat_parser.py
#     parse_chat_export(raw_files) -> list[ChatMessage]
#       Parse Slack/Teams/chat exports into speaker-attributed messages
#       with timestamps.
#   notes_parser.py
#     parse_notes(raw_files) -> list[ManualEvent]
#       Parse free-form notes and manual event entries (e.g. on-call
#       notes, runbook annotations) into timestamped events.
#   normalizer.py
#     normalize(raw_input) -> NormalizedTimeline
#       Merge log events, chat messages, and manual events into a single
#       deduplicated, chronologically sorted timeline.
