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


def permitted_cases(principal,repository):
    """Current read-granted scopes only; each data action still authorizes again."""
    if (principal is None or not principal.subject or principal.mfa_verified is not True
            or principal.expires_at.tzinfo is None or principal.expires_at<=datetime.now(timezone.utc)):
        raise PermissionError('Resource unavailable')
    read_cases = getattr(repository, 'read_cases_for', None)
    if callable(read_cases):
        return read_cases(principal.subject)
    scopes=set();profiles={}
    for grant in repository.grants_for(principal.subject):
        scope=grant.scope
        if (grant.subject!=principal.subject or 'read' not in grant.actions
                or not scope.profile_id or not scope.business_id
                or type(scope.tax_year) is not int or not 2023<=scope.tax_year<=2026):continue
        if scope.business_id not in profiles:
            profiles[scope.business_id]=repository.profile_for_business(scope.business_id)
        if profiles[scope.business_id]==scope.profile_id:
            scopes.add((scope.profile_id,scope.business_id,scope.tax_year))
    return [{'profile':profile,'business':business,'year':year} for profile,business,year in sorted(scopes)]
