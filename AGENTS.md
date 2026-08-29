# ThinkKoma agent notes

- Do not wait for a human problem statement. `drive` must sense the workspace and author its own missions.
- Do not ask the user to confirm interpretation, plans, idea selection, or whether a fix worked.
- Rank ideas, then drive the best verifiable action. Skip exhausted fingerprints instead of looping.
- Score with plus (6号) and minus (7号) viewpoints. Each model reenacts the oracle independently. Backpropagate residual to pipeline stages. Spec-ok requires oracle, safety, and integrity.
- Stay inside the workspace sandbox. Never touch credential paths or run denied commands.
- Prefer a local verifier (pytest/unittest, file contents) over model self-report.
- Halt a mission on success, budget, stall, or denial; halt a patrol on quiet or patrol_complete.
- Always write `.thinkkoma/outbox/` and `.thinkkoma/patrol/`.
- The heuristic Python repair only rewrites functions that have literal test examples.
