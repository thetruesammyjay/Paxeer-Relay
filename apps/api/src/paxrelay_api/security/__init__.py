"""Authentication layer for the PaxRelay control-plane API.

Public surface
--------------
``verify_api_key`` — FastAPI dependency that validates a ``Bearer`` token,
  fetches the matching :class:`~paxrelay_db.ApiKey` row, and returns a
  :class:`~paxrelay_api.tenant.TenantContext` for the request.
"""

from paxrelay_api.security.api_key import verify_api_key

__all__ = ["verify_api_key"]
