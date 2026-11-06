"""Application layer: use-case orchestration.

Services coordinate domain objects and infrastructure adapters (retrievers,
stores, agents) to fulfill a single use-case each. They raise
``src.domain.exceptions`` errors and never import FastAPI.
"""
