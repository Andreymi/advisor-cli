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
- "Find vulnerabilities: injection, auth bypass, data exposure"
- "Is O(n²) acceptable for N=10k or should I optimize?"
- "Redis vs Memcached for 100 req/hour, 1MB values?"
- "What edge cases am I missing in this error handling?"

## Task Templates

| Domain | Query Template |
|--------|----------------|
| Security | "Find vulnerabilities: injection, auth bypass, data exposure" |
| Code review | "Evaluate: readability, edge cases, bugs, testability" |
| Architecture | "Evaluate scalability for X users / Y RPS" |
| Performance | "Find bottlenecks. N=..., frequency: ..." |
| API design | "Evaluate API consistency and usability" |
| Data modeling | "Evaluate schema: normalization, indexes, relations" |
| Tech decision | "Compare A vs B for MVP considering time-to-market" |

## Expert Roles

Set `role` for specialized answers:

| Domain | Role |
|--------|------|
| Security | "You are a Senior Security Engineer. Think like an attacker." |
| Architecture | "You are a Solution Architect. Focus on scalability." |
| Performance | "You are a Performance Engineer. Find bottlenecks." |
| Code quality | "You are a Staff Engineer. Evaluate maintainability." |

## Models

Uses models from config. Run `advisor models` to see current setup.

Override: `model="deepseek/deepseek-reasoner"` for complex reasoning.

---

## For parent agent

**Always show the full result to the user.** Forked execution saves context, but user must see the response.
