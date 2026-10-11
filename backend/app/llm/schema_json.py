"""JSON Schemas for the two LLM steps, derived from the Pydantic models and made strict.

Both providers' structured-output modes reject many JSON Schema keywords, so the schema is
inlined (no $ref), stripped of titles and defaults, and every object forbids extra properties.
Length and value limits (a 90-word answer, quote length) are checked afterwards in Pydantic or in
verify.py, never in the schema.
"""

import json
from typing import Any

from pydantic import BaseModel

from app.schemas import ComposeOutput, UnderstandOutput

CEREBRAS_SCHEMA_MAX_CHARS = 5000
CEREBRAS_BANNED = frozenset(
    {
        "pattern", "format", "minItems", "maxItems", "oneOf", "allOf", "anyOf", "not", "nullable",
        "minLength", "maxLength", "minimum", "maximum", "multipleOf", "if", "then", "else",
        "patternProperties", "unevaluatedProperties", "dependentRequired", "dependentSchemas",
        "$anchor", "$ref", "$defs", "default", "title",
    }
)  # fmt: skip


def _inline(node: Any, defs: dict) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline(defs[node["$ref"].split("/")[-1]], defs)
        out = {}
        for key, value in node.items():
            if key in ("title", "default", "$defs", "description"):
                continue
            out[key] = _inline(value, defs)
        if out.get("type") == "object" or "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def strict_schema(model: type[BaseModel]) -> dict:
    raw = model.model_json_schema()
    return _inline(raw, raw.get("$defs", {}))


def assert_cerebras_strict(schema: dict) -> None:
    """Raise ValueError if the schema would be rejected by Cerebras strict mode."""
    text = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
    if len(text) > CEREBRAS_SCHEMA_MAX_CHARS:
        raise ValueError(f"schema is {len(text)} chars, over {CEREBRAS_SCHEMA_MAX_CHARS}")

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            bad = CEREBRAS_BANNED & node.keys() - {"properties"}
            # a property *named* like a banned keyword is fine; only schema keywords matter
            if path.endswith("/properties"):
                bad = set()
            if bad:
                raise ValueError(f"banned keyword(s) {sorted(bad)} at {path or '/'}")
            if "properties" in node:
                if node.get("additionalProperties") is not False:
                    raise ValueError(f"object at {path or '/'} must set additionalProperties false")
                if set(node.get("required", [])) != set(node["properties"]):
                    raise ValueError(f"object at {path or '/'} must require every property")
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(schema, "")


UNDERSTAND_SCHEMA = strict_schema(UnderstandOutput)
COMPOSE_SCHEMA = strict_schema(ComposeOutput)
