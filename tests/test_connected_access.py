import unittest
from datetime import datetime, timedelta, timezone

from ha.connected.access import authorize
from ha.connected.domain import Principal, Scope, Grant


class Repository:
    def __init__(self):
        self.grants = [Grant('orchard-owner', Scope('orchard', 'business', 2026), frozenset({'read', 'upload', 'correct', 'restore'}))]
        self.businesses = {'business': 'orchard', 'cedar-business': 'cedar'}

    def grants_for(self, subject):
        return [g for g in self.grants if g.subject == subject]

    def profile_for_business(self, business):
        return self.businesses.get(business)


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.owner = Principal('orchard-owner', datetime.now(timezone.utc) + timedelta(minutes=5), True)
        self.scope = Scope('orchard', 'business', 2026)

    def test_explicit_grant_permits_actions(self):
        for action in ('read', 'upload', 'correct', 'restore'):
            authorize(self.owner, self.scope, action, self.repo)

    def test_wrong_profile_business_year_subject_and_action_denied(self):
        for scope in (Scope('cedar', 'cedar-business', 2026), Scope('orchard', 'cedar-business', 2026), Scope('orchard', 'business', 2025)):
            with self.assertRaises(PermissionError):
                authorize(self.owner, scope, 'read', self.repo)
        with self.assertRaises(PermissionError):
            authorize(Principal('cedar-owner', self.owner.expires_at, True), self.scope, 'read', self.repo)
        with self.assertRaises(PermissionError):
            authorize(self.owner, self.scope, 'delete_original', self.repo)

    def test_revoked_grant_denies_same_active_principal(self):
        authorize(self.owner, self.scope, 'read', self.repo)
        self.repo.grants.clear()
        with self.assertRaises(PermissionError):
            authorize(self.owner, self.scope, 'read', self.repo)

    def test_missing_expired_and_non_mfa_identity_denied(self):
        for principal in (None, Principal('orchard-owner', datetime.now(timezone.utc) - timedelta(seconds=1), True), Principal('orchard-owner', self.owner.expires_at, False)):
            with self.assertRaises(PermissionError):
                authorize(principal, self.scope, 'read', self.repo)

    def test_invalid_scope_denied(self):
        for scope in (Scope('', 'business', 2026), Scope('orchard', '', 2026), Scope('orchard', 'business', True)):
            with self.assertRaises(PermissionError):
                authorize(self.owner, scope, 'read', self.repo)
