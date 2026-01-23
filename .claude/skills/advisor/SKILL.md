---
name: advisor
description: Get second opinion from alternative LLMs (Gemini, GPT, DeepSeek, etc.). Use for code review, architecture decisions, debugging help, or comparing approaches. Run `advisor models` to see configured providers.
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

## When to Use

✅ **Use advisor:**
- Important architectural decisions
- Security-sensitive code review
- When stuck on a hard problem
- Validating approach before major changes
- Trade-off decisions needing diverse opinions

❌ **Don't use:**
- Simple questions (answer yourself)
- Code generation (you have full context)
- Project-specific questions (read the code)

## consult vs compare

| Situation | Tool |
|-----------|------|
| Quick validation | `consult_expert` — one model, fast |
| Important decision | `compare_experts` — multiple viewpoints |
| Trade-offs, controversy | `compare_experts` — reveals disagreements |

## Workflow

1. **Find context first** (if about code):
   - `mgrep "query"` — semantic search
   - `Grep` / `Glob` / `Read` — exact match, files

2. **Call tool** with `query`, `context`, `role`

3. **Summarize** — highlight insights, don't dump raw output

## Writing Good Queries

❌ Vague: "Review this", "Is this good?"

✅ Specific:
- "Найди уязвимости: инъекции, auth bypass, утечка данных"
- "O(n²) приемлемо для N=10k или оптимизировать?"
- "Redis vs Memcached для 100 req/hour, 1MB values?"
- "Какие edge cases я пропустил в error handling?"

## Task Templates

| Domain | Query Template |
|--------|----------------|
| Security | "Найди уязвимости: инъекции, обход авторизации, утечка данных" |
| Code review | "Оцени: читаемость, edge cases, баги, тестируемость" |
| Architecture | "Оцени масштабируемость для X users / Y RPS" |
| Performance | "Найди узкие места. N=..., частота: ..." |
| API design | "Оцени консистентность и удобство API" |
| Data modeling | "Оцени схему: нормализация, индексы, связи" |
| Tech decision | "Сравни A vs B для MVP с учётом time-to-market" |

## Expert Roles

Set `role` for specialized answers:

| Domain | Role |
|--------|------|
| Security | "Ты Senior Security Engineer. Думай как атакующий." |
| Architecture | "Ты Solution Architect. Фокус на масштабируемости." |
| Performance | "Ты Performance Engineer. Ищи bottlenecks." |
| Code quality | "Ты Staff Engineer. Оцени maintainability." |

## Models

Uses models from config. Run `advisor models` to see current setup.

Override: `model="deepseek/deepseek-reasoner"` for complex reasoning.

---

## For parent agent

**Always show the full result to the user.** Forked execution saves context, but user must see the response.
