# ThinkKoma

ThinkKoma patrols a workspace with no human prompt. `thinkkoma drive` senses failing tests, syntax errors, and logs, turns them into missions, and stops when the workspace is quiet. `--watch` keeps rescanning. Verification and halt stay local; optional Ollama only enriches interpretation.

Scoring uses plus (unit 6) and minus (unit 7) across ten viewpoints. Residuals backpropagate onto interpret / plan / act / verify / submit. Spec-ok requires oracle, safety, and integrity after independent reenact by both models.

See README.md for the Japanese operator guide.
