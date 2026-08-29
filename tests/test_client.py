from __future__ import annotations

from thinkkoma.backends.client import parse_llm_json


def test_parse_llm_json_strips_fences() -> None:
    payload = parse_llm_json("```json\n{\"ideas\": [{\"title\": \"x\"}]}\n```")
    assert payload["ideas"][0]["title"] == "x"
