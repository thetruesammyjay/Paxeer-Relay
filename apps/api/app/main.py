"""Expose the control-plane app at ``app.main:app`` for local development."""

from paxrelay_api.main import app

__all__ = ["app"]
