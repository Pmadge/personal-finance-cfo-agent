## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Coding-agent behavior rules

These rules adapt the Karpathy-inspired coding guidelines for this project.

### Think before coding
- State assumptions when a task could be interpreted multiple ways.
- Ask before changing architecture, privacy posture, data sources, or external integrations.
- Push back if a simpler local-first approach solves the task.

### Simplicity first
- Write the minimum code that solves the requested workflow.
- Do not add speculative features, frameworks, cloud services, bank integrations, or broad configurability.
- If a change starts to sprawl, stop and narrow it.

### Surgical changes
- Touch only files needed for the current task.
- Match the existing project style.
- Do not refactor unrelated code or delete old artifacts unless explicitly asked.
- Clean up only unused code created by your own change.

### Goal-driven execution
- Turn each task into a verifiable goal.
- For behavior changes, write or update tests first when practical.
- Run the relevant command, script, or tests before saying the work is done.

## Personal finance safety rules

- Use fictional/sample data only unless Paul explicitly approves a real personal-data workflow.
- Do not add bank-login integrations, credential storage, cloud hosting, hosted databases, or external AI APIs.
- Keep personal workflow outputs in Git-ignored local folders such as `data/personal/`, `data/processed/`, and `outputs/personal/`.
- Do not run Graphify on real personal financial data, credentials, private exports, or generated private reports.
- Treat deterministic Python code as the source of truth for numbers. AI can explain checked numbers but must not invent financial outputs.
