"""Pytest configuration and global environment fixtures."""

import os

# Ensure HuggingFace Hub doesn't attempt network calls in test runs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

