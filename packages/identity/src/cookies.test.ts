import { describe, expect, it } from "vitest";

import type { ControlPlanePool } from "@vibeflow/persistence";

import { cookieRequestHeader, setCookieHeaders } from "./cookies.js";
import { IdentityInputError } from "./errors.js";
import { IdentityService } from "./service.js";

describe("M-009 cookie transport boundary", () => {
  it("forwards only cookie name/value pairs on a subsequent request", () => {
    expect(
      cookieRequestHeader([
        "__Secure-vibeflow.session_token=opaque; Path=/; HttpOnly; Secure",
        "vibeflow.dont_remember=0; Path=/; HttpOnly; Secure",
      ]),
    ).toBe("__Secure-vibeflow.session_token=opaque; vibeflow.dont_remember=0");
  });

  it("reads a regular set-cookie response header when multi-value headers are unavailable", () => {
    const headers = new Headers({
      "set-cookie": "__Secure-vibeflow.session_token=opaque; Path=/; HttpOnly; Secure",
    });
    expect(setCookieHeaders(headers)).toEqual([
      "__Secure-vibeflow.session_token=opaque; Path=/; HttpOnly; Secure",
    ]);
  });

  it("rejects insecure base URLs and undersized server secrets", () => {
    const controlPlane = {} as ControlPlanePool;
    expect(
      () =>
        new IdentityService({
          controlPlane,
          baseURL: "http://identity.vibeflow.test",
          secret: "this-secret-is-long-enough-to-reach-the-next-check",
        }),
    ).toThrow(IdentityInputError);
    expect(
      () =>
        new IdentityService({
          controlPlane,
          baseURL: "https://identity.vibeflow.test",
          secret: "too-short",
        }),
    ).toThrow(IdentityInputError);
  });
});
