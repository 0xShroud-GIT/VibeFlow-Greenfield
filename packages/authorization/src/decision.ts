/**
 * Pure request validation for the authorization boundary.
 *
 * Every malformed, unknown, or unparseable input is reduced to a deny decision
 * here so the service can fail closed without ever throwing an authorization
 * exception that could be mistaken for an allow. The boundary accepts only
 * canonical VibeFlow UUIDs and registered resource-type/action tokens.
 */

import { isUuid } from "@vibeflow/persistence";

import { ACTIONS, RESOURCE_TYPES, deny } from "./types.js";
import type { AuthorizationDecision, AuthorizationRequest } from "./types.js";

/**
 * Returns a deny decision when the request is malformed or references an
 * unknown resource type/action, or `null` when the request is structurally
 * valid and ready for canonical persistence resolution.
 */
export function validateRequest(
  request: AuthorizationRequest,
): AuthorizationDecision | null {
  if (!isPresent(request)) {
    return deny("malformed_request");
  }
  if (
    typeof request.accountId !== "string" ||
    request.accountId.trim().length === 0
  ) {
    return deny("malformed_request");
  }
  if (
    typeof request.action !== "string" ||
    request.action.trim().length === 0
  ) {
    return deny("malformed_request");
  }
  const resource = request.resource;
  if (
    resource === null ||
    typeof resource !== "object" ||
    typeof resource.type !== "string" ||
    resource.type.trim().length === 0 ||
    typeof resource.id !== "string" ||
    resource.id.trim().length === 0
  ) {
    return deny("malformed_request");
  }
  // Canonical VibeFlow identifiers are server-owned UUIDs. Anything else
  // (client ids, provider ids, slugs) is not authoritative and is denied.
  if (!isUuid(request.accountId) || !isUuid(resource.id)) {
    return deny("invalid_identifier");
  }
  if (!(RESOURCE_TYPES as readonly string[]).includes(resource.type)) {
    return deny("unknown_resource_type");
  }
  if (!(ACTIONS as readonly string[]).includes(request.action)) {
    return deny("unknown_action");
  }
  return null;
}

function isPresent(value: unknown): value is AuthorizationRequest {
  return (
    value !== null &&
    typeof value === "object" &&
    Object.prototype.hasOwnProperty.call(value, "accountId") &&
    Object.prototype.hasOwnProperty.call(value, "action") &&
    Object.prototype.hasOwnProperty.call(value, "resource")
  );
}
