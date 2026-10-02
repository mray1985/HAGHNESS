"""Deny-by-default permissions, evaluated anew for every service action."""
from datetime import datetime, timezone
from .domain import Principal, Scope


def authorize(principal: Principal | None, scope: Scope, action: str, repository) -> None:
    denied = PermissionError('Resource unavailable')
    if principal is None or not principal.subject or principal.mfa_verified is not True:
        raise denied
    if principal.expires_at.tzinfo is None or principal.expires_at <= datetime.now(timezone.utc):
        raise denied
    if (not scope.profile_id or not scope.business_id
            or type(scope.tax_year) is not int or not 2023 <= scope.tax_year <= 2026):
        raise denied
    if repository.profile_for_business(scope.business_id) != scope.profile_id:
        raise denied
    if not any(g.subject == principal.subject and g.scope == scope and action in g.actions
               for g in repository.grants_for(principal.subject)):
        raise denied
