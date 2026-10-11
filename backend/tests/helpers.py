"""Builders for scripted model replies."""


def understand_json(intent="plot_norms", in_scope=True, query="open space", **params):
    """A valid Step A reply. Unstated numbers are -1, as the schema says."""
    base = {
        "plot_area": -1, "plot_area_unit": "none", "road_width_m": -1, "height_m": -1,
        "built_up_area_sqm": -1, "frontage_m": -1, "use": "unknown", "building_type": "unknown",
        "voltage": "unknown",
    }  # fmt: skip
    base.update(params)
    return {"in_scope": in_scope, "intent": intent, "search_query_en": query, "params": base}


def compose_json(answer="", citations=(), status="answered", missing=()):
    return {
        "status": status,
        "answer": answer,
        "citations": [{"chunk_id": c, "quote": q} for c, q in citations],
        "missing_info": list(missing),
    }
