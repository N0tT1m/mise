"""Mise offline pipeline.

Four stages, run in order. The pipeline writes to the database; the API only
ever reads. Nothing here belongs in a request path.
"""

__version__ = "0.1.0"

STAGES = ("ingest", "extract", "resolve", "publish")
