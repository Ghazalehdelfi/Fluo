# Language Learning Agents
# Lazy imports to avoid circular dependency with cost_tracker ↔ agents.logging_utils


def __getattr__(name: str):
    """Lazy-load agent classes on first access to prevent circular imports."""
    _map = {
        "NoteExtractorAgent": "agents.note_extractor",
        "DialogueAgent": "agents.dialogue_agent",
        "AnalysisAgent": "agents.analysis_agent",
        "PlacementTestAgent": "agents.placement_agent",
    }
    if name in _map:
        import importlib

        module = importlib.import_module(_map[name])
        return getattr(module, name)
    raise AttributeError(f"module 'agents' has no attribute {name!r}")


__all__ = [
    "NoteExtractorAgent",
    "DialogueAgent",
    "AnalysisAgent",
]
