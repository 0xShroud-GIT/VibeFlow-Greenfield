#!/usr/bin/env python3
"""M-010 tenant/resource authorization boundary contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHZ_PACKAGE = REPO_ROOT / "packages" / "authorization" / "package.json"
AUTHZ_SERVICE = REPO_ROOT / "packages" / "authorization" / "src" / "service.ts"
AUTHZ_TYPES = REPO_ROOT / "packages" / "authorization" / "src" / "types.ts"
AUTHZ_DECISION = REPO_ROOT / "packages" / "authorization" / "src" / "decision.ts"
AUTHZ_LIVE_TEST = REPO_ROOT / "packages" / "authorization" / "src" / "tenant.live.test.ts"
AUTHZ_README = REPO_ROOT / "packages" / "authorization" / "README.md"
ROOT_PACKAGE = REPO_ROOT / "package.json"


class M010TenantAuthorizationContractTests(unittest.TestCase):
    def test_authorization_package_uses_only_ratified_workspace_dependencies(self) -> None:
        manifest = json.loads(AUTHZ_PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "@vibeflow/authorization")
        self.assertEqual(manifest["dependencies"], {"@vibeflow/persistence": "workspace:*"})
        # No external authorization engine is pulled for this slice.
        for forbidden in ("openfga", "casbin", "cerbos", "oso", "zanzibar"):
            self.assertNotIn(forbidden, json.dumps(manifest).lower())

    def test_decision_boundary_is_typed_and_resource_type_agnostic(self) -> None:
        source = AUTHZ_TYPES.read_text(encoding="utf-8")
        for required in (
            "RESOURCE_TYPES",
            "ACTIONS",
            "ResourceRef",
            "AuthorizationRequest",
            "AuthorizationDecision",
            "DenyReason",
            "no_membership",
            "unknown_resource_type",
            "unknown_action",
            "malformed_request",
            "invalid_identifier",
            "unknown_resource",
            "ALLOW",
        ):
            self.assertIn(required, source)

    def test_service_is_deny_by_default_and_resolves_membership_from_persistence(self) -> None:
        source = AUTHZ_SERVICE.read_text(encoding="utf-8")
        for required in (
            "deny-by-default",
            "getOrganizationById",
            "getMembership",
            "organization_memberships",
            "no_membership",
            "unknown_resource",
            "ALLOW",
            "request.accountId",
        ):
            self.assertIn(required, source)
        # The boundary never accepts a client-claimed organization id or role:
        # no property is named for roles, permissions, or ownership.
        self.assertNotIn('"role"', source)
        self.assertNotIn("role:", source)
        self.assertNotIn('"permissions"', source)
        self.assertNotIn("permissions:", source)
        self.assertNotIn("ownerId", source)
        self.assertNotIn("openfga", source.lower())

    def test_request_boundary_never_accepts_a_client_claimed_organization_id(self) -> None:
        # The request is { accountId, action, resource{type,id} }. There is no
        # separate client/provider-supplied organization id, role, permission,
        # or ownership claim to trust; the tenant is resolved from persistence.
        source = AUTHZ_TYPES.read_text(encoding="utf-8")
        self.assertNotIn("organizationId", source)
        self.assertNotIn("ownerId", source)
        self.assertNotIn('"role"', source)
        self.assertNotIn("role:", source)
        self.assertNotIn('"permissions"', source)
        self.assertNotIn("permissions:", source)
        self.assertNotIn("ownership:", source)

    def test_validation_rejects_non_canonical_ids_and_unknown_resource_action(self) -> None:
        source = AUTHZ_DECISION.read_text(encoding="utf-8")
        for required in (
            "isUuid",
            "deny(\"invalid_identifier\")",
            "deny(\"unknown_resource_type\")",
            "deny(\"unknown_action\")",
            "deny(\"malformed_request\")",
        ):
            self.assertIn(required, source)
        self.assertIn("RESOURCE_TYPES", source)

    def test_live_suite_requires_database_in_ci_and_covers_p0_negatives(self) -> None:
        source = AUTHZ_LIVE_TEST.read_text(encoding="utf-8")
        self.assertIn('process.env["CI"] === "true"', source)
        self.assertIn("M-010 PostgreSQL authorization requires DATABASE_URL in CI", source)
        for required in (
            "P0 negative",
            "cross-tenant access",
            "IDOR",
            "deleted/stale membership",
            "forged",
            "swapped",
            "no_membership",
            "unknown_resource",
            "malformed and unknown resource/action",
            "cannot create/update/delete",
        ):
            self.assertIn(required, source)

    def test_readme_does_not_overclaim_later_missions(self) -> None:
        readme = AUTHZ_README.read_text(encoding="utf-8")
        collapsed = " ".join(readme.lower().split())
        self.assertIn("deny-by-default", collapsed)
        self.assertIn("does not implement project persistence/lifecycle (m-012)", collapsed)
        self.assertIn("no external authorization engine is used", collapsed)

    def test_root_check_retains_m010_contract_and_explicit_live_runner(self) -> None:
        manifest = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        self.assertIn("test_m010_authz.py", manifest["scripts"]["check"])
        self.assertIn("run-m010-authz-integration.py", manifest["scripts"]["check"])
        runner = (REPO_ROOT / "scripts" / "run-m010-authz-integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("required in CI", runner)
        self.assertIn("not verification evidence", runner)


if __name__ == "__main__":
    unittest.main()
