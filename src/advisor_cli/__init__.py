"""Advisor CLI - получение второго мнения от альтернативных LLM."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("advisor-cli")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
