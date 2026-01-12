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
  - Bash(mgrep:*)
  - mcp__advisor_mcp__.*
---

# MCP Advisor - Second Opinion

Get alternative perspectives from other LLMs.

## Workflow

1. If question about code → **find and read it first**:
   - `mgrep "query"` — semantic search (fast, by meaning)
   - `Grep` — exact text match
   - `Glob` — find by file pattern
   - `Read` — read specific file
2. Call tool:
   - **One opinion** → `advisor_consult_expert(query, context)`
   - **Compare opinions** → `advisor_compare_experts(query, context)`
3. **Summarize** findings (don't dump raw output)

## Rules

- **Always pass code in `context`** when asking about code
- `query` = вопрос эксперту
- `context` = код или данные для анализа
- Highlight consensus and disagreements between experts

## Expert Role Selection

**Set `role` parameter based on task type** — specialized roles give deeper answers:

| Task | Role |
|------|------|
| Security review | "Ты Senior Security Engineer. Найди уязвимости." |
| Code review | "Ты Staff Engineer. Оцени качество кода." |
| Architecture | "Ты Solution Architect. Оцени масштабируемость." |
| Performance | "Ты Performance Engineer. Найди узкие места." |
| API design | "Ты API Designer. Оцени удобство и консистентность." |
| Testing | "Ты QA Lead. Предложи тест-кейсы." |
| Database | "Ты DBA. Оцени схему и запросы." |
| DevOps | "Ты DevOps Engineer. Оцени CI/CD и инфраструктуру." |

Example: `advisor_consult_expert(query="...", context="...", role="Ты Senior Security Engineer...")`

---

## For parent agent (after fork completes)

**Always show the full result to the user.** The forked execution saves context, but the user must see the expert's response.
