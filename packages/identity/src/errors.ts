export class IdentityError extends Error {
  override readonly name: string = "IdentityError";
}

/** Input was malformed before it reached Better Auth or PostgreSQL. */
export class IdentityInputError extends IdentityError {
  override readonly name = "IdentityInputError";
}

/** The request origin is not a configured VibeFlow authentication origin. */
export class UntrustedIdentityOriginError extends IdentityError {
  override readonly name = "UntrustedIdentityOriginError";
}

/** Deliberately generic: callers must not learn whether a credential exists. */
export class AuthenticationRejectedError extends IdentityError {
  override readonly name = "AuthenticationRejectedError";
}

/** A library-authenticated user without a canonical VibeFlow Account is denied. */
export class CanonicalAccountLinkError extends IdentityError {
  override readonly name = "CanonicalAccountLinkError";
}
