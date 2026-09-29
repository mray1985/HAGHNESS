"""HA Tax Software — offline federal/state individual income tax calculator.

Not a filing service. Not return preparation. Not tax advice. See
ha/compliance/__init__.py for the full limited-status statement.
"""

from .compliance import VERSION, DISCLAIMER_SHORT, attestation_payload

__all__ = ["VERSION", "DISCLAIMER_SHORT", "attestation_payload"]
__version__ = VERSION
