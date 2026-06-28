## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Coding-agent behavior rules

These rules adapt the Karpathy-inspired coding guidelines for this project.

- Think before coding: state assumptions, surface tradeoffs, and ask before architecture, privacy, data-source, or integration changes.
- Keep it simple: solve the requested workflow with the minimum useful local-first code.
- Make surgical changes: touch only files needed for the task and avoid unrelated refactors.
- Verify the goal: run the relevant script or tests before saying the work is done.

## Personal finance safety rules

- Use fictional/sample data only unless Paul explicitly approves a real personal-data workflow.
- Do not add bank-login integrations, credential storage, cloud hosting, hosted databases, or external AI APIs.
- Keep personal workflow outputs in Git-ignored local folders such as `data/personal/`, `data/processed/`, and `outputs/personal/`.
- Do not run Graphify on real personal financial data, credentials, private exports, or generated private reports.
