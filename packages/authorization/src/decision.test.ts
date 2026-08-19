import { describe, expect, it } from "vitest";

import type { OrganizationMembershipRow, OrganizationRow } from "@vibeflow/persistence";

import { validateRequest } from "./decision.js";
import { TenantAuthorizationService } from "./service.js";
import type { MembershipAuthority } from "./service.js";
import { ALLOW, ACTIONS, RESOURCE_TYPES, deny } from "./types.js";
import type { AuthorizationRequest } from "./types.js";

const ACCOUNT_A = "11111111-1111-4111-8111-111111111111";
const ORG_A = "22222222-2222-4222-8222-222222222222";
const ORG_B = "33333333-3333-4333-8333-333333333333";

function orgRow(id: string): OrganizationRow {
  return {
    id,
    name: "Org",
    kind: "standard",
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

function membershipRow(organizationId: string, accountId: string): OrganizationMembershipRow {
  return { id: "44444444-4444-4444-8444-444444444444", organizationId, accountId, createdAt: new Date() };
}

/** Fake canonical-persistence authority: a member of ORG_A only. */
function fakeAuthority(): MembershipAuthority {
  return {
    async getOrganizationById(id) {
      if (id === ORG_A || id === ORG_B) return orgRow(id);
      throw Object.assign(new Error("not found"), { name: "NotFoundError" });
    },
    async getMembership({ organizationId, accountId }) {
      if (organizationId === ORG_A && accountId === ACCOUNT_A) {
        return membershipRow(ORG_A, ACCOUNT_A);
      }
      throw Object.assign(new Error("not found"), { name: "NotFoundError" });
    },
  };
}

function request(overrides: Partial<AuthorizationRequest> = {}): AuthorizationRequest {
  return {
    accountId: ACCOUNT_A,
    action: "read",
    resource: { type: "organization", id: ORG_A },
    ...overrides,
  };
}

describe("M-010 authorization decision boundary", () => {
  it("registers the organization resource type and canonical actions", () => {
    expect(RESOURCE_TYPES).toEqual(["organization"]);
    expect(ACTIONS).toEqual(["read", "create", "update", "delete", "list"]);
  });

  it("rejects malformed and non-canonical requests as deny", () => {
    expect(validateRequest(undefined as never)).toEqual(deny("malformed_request"));
    expect(validateRequest(null as never)).toEqual(deny("malformed_request"));
    expect(validateRequest({} as never)).toEqual(deny("malformed_request"));
    expect(validateRequest(request({ accountId: "" }))).toEqual(deny("malformed_request"));
    expect(validateRequest(request({ action: "  " }))).toEqual(deny("malformed_request"));
    expect(validateRequest(request({ resource: { type: "", id: ORG_A } }))).toEqual(
      deny("malformed_request"),
    );
    expect(validateRequest(request({ resource: { type: "organization", id: "" } }))).toEqual(
      deny("malformed_request"),
    );
  });

  it("rejects non-canonical identifiers as invalid_identifier", () => {
    expect(validateRequest(request({ accountId: "not-a-uuid" }))).toEqual(
      deny("invalid_identifier"),
    );
    expect(validateRequest(request({ resource: { type: "organization", id: "org-from-client" } }))).toEqual(
      deny("invalid_identifier"),
    );
    expect(validateRequest(request({ resource: { type: "organization", id: "22222222" } }))).toEqual(
      deny("invalid_identifier"),
    );
  });

  it("rejects unknown resource types and unknown actions", () => {
    expect(validateRequest(request({ resource: { type: "project", id: ORG_A } }))).toEqual(
      deny("unknown_resource_type"),
    );
    expect(validateRequest(request({ action: "deploy" }))).toEqual(deny("unknown_action"));
    expect(validateRequest(request({ action: "transferOwnership" }))).toEqual(
      deny("unknown_action"),
    );
  });

  it("accepts a structurally valid request for canonical resolution", () => {
    expect(validateRequest(request())).toBeNull();
  });

  it("allows a member of the organization", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    await expect(service.authorize(request())).resolves.toEqual(ALLOW);
  });

  it("allows every known mutation action for a proven member", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    for (const action of ACTIONS) {
      await expect(service.authorize(request({ action }))).resolves.toEqual(ALLOW);
    }
  });

  it("denies an account with no membership", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    const outsider = "55555555-5555-4555-8555-555555555555";
    await expect(service.authorize(request({ accountId: outsider }))).resolves.toEqual(
      deny("no_membership"),
    );
  });

  it("denies cross-tenant access to an organization the account does not belong to", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    await expect(
      service.authorize(request({ resource: { type: "organization", id: ORG_B } })),
    ).resolves.toEqual(deny("no_membership"));
  });

  it("denies a forged id that is not a real organization", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    const forged = "66666666-6666-4666-8666-666666666666";
    await expect(
      service.authorize(request({ resource: { type: "organization", id: forged } })),
    ).resolves.toEqual(deny("unknown_resource"));
  });

  it("denies an unknown resource type at the service boundary", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    await expect(
      service.authorize(request({ resource: { type: "workspace", id: ORG_A } })),
    ).resolves.toEqual(deny("unknown_resource_type"));
  });

  it("denies an unknown action at the service boundary", async () => {
    const service = new TenantAuthorizationService(fakeAuthority());
    await expect(service.authorize(request({ action: "admin" }))).resolves.toEqual(
      deny("unknown_action"),
    );
  });
});
