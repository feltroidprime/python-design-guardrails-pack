"""End-to-end value benchmark: one LLM builds the same app with and without the template.

The package is standard-library-only except for `agents.py`, which imports
`headless_llm` lazily so the pack's deterministic tests never need it.
"""
