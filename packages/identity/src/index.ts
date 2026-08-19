export { cookieRequestHeader, setCookieHeaders } from "./cookies.js";
export {
  AuthenticationRejectedError,
  CanonicalAccountLinkError,
  IdentityError,
  IdentityInputError,
  UntrustedIdentityOriginError,
} from "./errors.js";
export {
  IdentityService,
  type AuthenticationAuditRecorder,
  type EmailPasswordRegistration,
  type EmailPasswordSignIn,
  type IdentityServiceOptions,
  type SessionStart,
  type SessionValidation,
} from "./service.js";
