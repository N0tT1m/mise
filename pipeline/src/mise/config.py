"""Configuration, from the environment only.

Never read secrets from a file in the repo. A .gitignore rule does nothing to
a file that is already tracked.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    database_url: str
    parser_version: int
    inference_url: str | None

    @classmethod
    def from_env(cls) -> "Config":
        url = os.environ.get("MISE_DATABASE_URL")
        if not url:
            raise RuntimeError(
                "MISE_DATABASE_URL is not set. Refusing to start rather than "
                "guessing a connection string."
            )
        return cls(
            database_url=url,
            parser_version=int(os.environ.get("MISE_PARSER_VERSION", "1")),
            inference_url=os.environ.get("MISE_INFERENCE_URL"),
        )
