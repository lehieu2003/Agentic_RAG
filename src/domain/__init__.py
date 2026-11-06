"""Domain layer: framework-free business rules and errors.

This package must not import FastAPI (or any other presentation concern);
the API edge maps its exceptions onto HTTP responses in one place.
"""
