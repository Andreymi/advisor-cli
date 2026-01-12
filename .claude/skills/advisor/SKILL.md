---
name: advisor
description: Get second opinion from alternative LLMs (Gemini, GPT, Ollama Cloud). Use for code review, architecture decisions, debugging help, or comparing approaches. Can read and analyze code before consulting experts.
user-invocable: true
context: fork
agent: general-purpose
allowed-tools:
  - Read
  - Glob
  - Grep
  - mcp__advisor_mcp__.*
---

# MCP Advisor - Second Opinion

Get alternative perspectives from other LLMs.

## Workflow

1. If question about code → **read it first** with Read/Glob/Grep
2. Call tool:
   - **One opinion** → `advisor_consult_expert(query, context)`
   - **Compare opinions** → `advisor_compare_experts(query, context)`
3. **Summarize** findings (don't dump raw output)

## Rules

- **Always pass code in `context`** when asking about code
- `query` = вопрос эксперту
- `context` = код или данные для анализа
- Highlight consensus and disagreements between experts

---

## For parent agent (after fork completes)

**Always show the full result to the user.** The forked execution saves context, but the user must see the expert's response.
