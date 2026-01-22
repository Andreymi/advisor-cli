#!/bin/bash
# Ruff auto-format hook for Claude Code
# Reads JSON from stdin, extracts file path, runs ruff on .py files

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)

if [[ -n "$FILE" && "$FILE" == *.py && -f "$FILE" ]]; then
    ruff format "$FILE" 2>/dev/null
    ruff check --fix "$FILE" 2>/dev/null
fi

exit 0
