#!/bin/bash
# Protect .env files from being edited by Claude
# Returns exit code 2 to block the operation

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [[ -n "$FILE" && "$FILE" == *.env* ]]; then
    echo "BLOCKED: Cannot edit .env files - they contain API keys"
    exit 2
fi

exit 0
