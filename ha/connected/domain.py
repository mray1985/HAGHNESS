"""Immutable service identities and permission boundaries."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Principal:
    subject: str
    expires_at: datetime
    mfa_verified: bool


@dataclass(frozen=True)
class Scope:
    profile_id: str
    business_id: str
    tax_year: int


@dataclass(frozen=True)
class Grant:
    subject: str
    scope: Scope
    actions: frozenset[str]
