import { betterAuth } from "better-auth";
import { Kysely, PostgresDialect } from "kysely";
import {
  type AccountRow,
  type ControlPlanePool,
  TenantRepository,
} from "@vibeflow/persistence";

import { setCookieHeaders } from "./cookies.js";
import {
  AuthenticationRejectedError,
  CanonicalAccountLinkError,
  IdentityInputError,
  UntrustedIdentityOriginError,
} from "./errors.js";

const SESSION_EXPIRES_IN_SECONDS = 60 * 60 * 24;
const SESSION_UPDATE_AGE_SECONDS = 60 * 60;
const SESSION_FRESH_AGE_SECONDS = 60 * 5;

type BetterAuthUser = Readonly<{
  id: string;
}>;

type BetterAuthSession = Readonly<{
  id: string;
  expiresAt: Date;
  createdAt: Date;
}>;

type BetterAuthSessionResult = Readonly<{
  user: BetterAuthUser;
  session: BetterAuthSession;
}>;

type AuthResultWithHeaders<Response> = Readonly<{
  response: Response;
  headers: Headers;
}>;

export type IdentityServiceOptions = Readonly<{
  controlPlane: ControlPlanePool;
  /** HTTPS application origin used for trusted-origin and cookie enforcement. */
  baseURL: string;
  /** At least 32 characters; supplied only through server configuration. */
  secret: string;
}>;

export type EmailPasswordRegistration = Readonly<{
  displayName: string;
  email: string;
  password: string;
  origin: string;
}>;

export type EmailPasswordSignIn = Readonly<{
  email: string;
  password: string;
  origin: string;
}>;

export type SessionStart = Readonly<{
  accountId: string;
  setCookie: readonly string[];
}>;

/** Identity proof only. It intentionally contains no Organization/Project/role state. */
export type SessionValidation =
  | Readonly<{
      authenticated: false;
    }>
  | Readonly<{
      authenticated: true;
      accountId: string;
      sessionId: string;
      expiresAt: Date;
      isFresh: boolean;
    }>;

function requiredText(name: string, value: string): string {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    throw new IdentityInputError(`${name} is required`);
  }
  return trimmed;
}

function requireSecureOrigin(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new IdentityInputError("baseURL must be an absolute HTTPS URL");
  }
  if (parsed.protocol !== "https:") {
    throw new IdentityInputError("baseURL must use HTTPS");
  }
  return parsed.origin;
}

function requireSecret(value: string): string {
  if (value.length < 32) {
    throw new IdentityInputError("Better Auth secret must be at least 32 characters");
  }
  return value;
}

function asHeaders(origin: string, cookieHeader?: string): Headers {
  const headers = new Headers({ origin });
  if (cookieHeader !== undefined && cookieHeader.length > 0) {
    headers.set("cookie", cookieHeader);
  }
  return headers;
}

function isSessionResult(value: unknown): value is BetterAuthSessionResult {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as {
    user?: { id?: unknown };
    session?: { id?: unknown; expiresAt?: unknown; createdAt?: unknown };
  };
  return (
    typeof candidate.user?.id === "string" &&
    typeof candidate.session?.id === "string" &&
    candidate.session.expiresAt instanceof Date &&
    candidate.session.createdAt instanceof Date
  );
}

/**
 * M-009 boundary around Better Auth. Better Auth performs credential and
 * session mechanics; VibeFlow resolves the resulting user through the
 * canonical Account link and never treats a session as tenant authorization.
 */
export class IdentityService {
  private readonly tenantRepository: TenantRepository;
  private readonly baseOrigin: string;
  private readonly secret: string;
  /**
   * Better Auth's Kysely adapter runs its signup sequence in this PostgreSQL
   * transaction context. The control-plane pool retains lifecycle ownership.
   */
  private readonly authDatabase: Kysely<{}>;

  public constructor(private readonly options: IdentityServiceOptions) {
    this.tenantRepository = new TenantRepository(options.controlPlane.db);
    this.baseOrigin = requireSecureOrigin(options.baseURL);
    this.secret = requireSecret(options.secret);
    this.authDatabase = new Kysely<{}>({
      dialect: new PostgresDialect({ pool: options.controlPlane.pool }),
    });
  }

  public async registerEmailPassword(input: EmailPasswordRegistration): Promise<SessionStart> {
    const displayName = requiredText("displayName", input.displayName);
    const origin = this.requireTrustedOrigin(input.origin);
    const auth = this.createAuth();

    try {
      const result = (await auth.api.signUpEmail({
        body: {
          name: displayName,
          email: requiredText("email", input.email),
          password: input.password,
        },
        headers: asHeaders(origin),
        returnHeaders: true,
      })) as AuthResultWithHeaders<{ user: BetterAuthUser }>;
      const account = await this.requireCanonicalAccount(result.response.user.id);
      return {
        accountId: account.id,
        setCookie: setCookieHeaders(result.headers),
      };
    } catch (error) {
      if (error instanceof IdentityInputError || error instanceof UntrustedIdentityOriginError) {
        throw error;
      }
      throw new AuthenticationRejectedError("Registration was rejected", { cause: error });
    }
  }

  public async signInEmailPassword(input: EmailPasswordSignIn): Promise<SessionStart> {
    const origin = this.requireTrustedOrigin(input.origin);
    const auth = this.createAuth();

    try {
      const result = (await auth.api.signInEmail({
        body: {
          email: requiredText("email", input.email),
          password: input.password,
          rememberMe: true,
        },
        headers: asHeaders(origin),
        returnHeaders: true,
      })) as AuthResultWithHeaders<{ user: BetterAuthUser }>;
      const account = await this.requireCanonicalAccount(result.response.user.id);
      return {
        accountId: account.id,
        setCookie: setCookieHeaders(result.headers),
      };
    } catch (error) {
      if (error instanceof IdentityInputError || error instanceof UntrustedIdentityOriginError) {
        throw error;
      }
      throw new AuthenticationRejectedError("Invalid email or password");
    }
  }

  public async validateSession(input: Readonly<{ origin: string; cookieHeader: string }>): Promise<SessionValidation> {
    const origin = this.requireTrustedOrigin(input.origin);
    const auth = this.createAuth();

    try {
      const result = await auth.api.getSession({
        headers: asHeaders(origin, input.cookieHeader),
      });
      if (!isSessionResult(result)) {
        return { authenticated: false };
      }

      const account = await this.tenantRepository.findAccountByIdentityUserId(result.user.id);
      if (account === undefined) {
        return { authenticated: false };
      }

      return {
        authenticated: true,
        accountId: account.id,
        sessionId: result.session.id,
        expiresAt: result.session.expiresAt,
        isFresh:
          Date.now() - result.session.createdAt.getTime() <=
          SESSION_FRESH_AGE_SECONDS * 1000,
      };
    } catch {
      // Invalid, expired, malformed, replayed, or unlinked sessions all fail closed.
      return { authenticated: false };
    }
  }

  public async logout(input: Readonly<{ origin: string; cookieHeader: string }>): Promise<readonly string[]> {
    const origin = this.requireTrustedOrigin(input.origin);
    const auth = this.createAuth();

    try {
      const result = (await auth.api.signOut({
        headers: asHeaders(origin, input.cookieHeader),
        returnHeaders: true,
      })) as AuthResultWithHeaders<{ success: boolean }>;
      if (!result.response.success) {
        throw new AuthenticationRejectedError("Logout was rejected");
      }
      return setCookieHeaders(result.headers);
    } catch (error) {
      if (error instanceof UntrustedIdentityOriginError) {
        throw error;
      }
      throw new AuthenticationRejectedError("Logout was rejected");
    }
  }

  private requireTrustedOrigin(origin: string): string {
    let parsed: URL;
    try {
      parsed = new URL(origin);
    } catch {
      throw new UntrustedIdentityOriginError("Authentication origin is invalid");
    }
    if (parsed.origin !== this.baseOrigin) {
      throw new UntrustedIdentityOriginError("Authentication origin is not trusted");
    }
    return parsed.origin;
  }

  private async requireCanonicalAccount(identityUserId: string): Promise<AccountRow> {
    const account = await this.tenantRepository.findAccountByIdentityUserId(identityUserId);
    if (account === undefined) {
      throw new CanonicalAccountLinkError(
        "Authenticated user is not linked to a canonical VibeFlow Account",
      );
    }
    return account;
  }

  private createAuth() {
    return betterAuth({
      appName: "VibeFlow",
      baseURL: this.baseOrigin,
      secret: this.secret,
      database: {
        db: this.authDatabase,
        type: "postgres",
        // Better Auth's sign-up path wraps user, credential, and session writes
        // in its adapter transaction when this is enabled.
        transaction: true,
      },
      trustedOrigins: [this.baseOrigin],
      advanced: {
        useSecureCookies: true,
        cookiePrefix: "vibeflow",
        defaultCookieAttributes: {
          httpOnly: true,
          secure: true,
          sameSite: "lax",
          path: "/",
        },
        database: {
          // Better Auth 1.6.x generates PostgreSQL UUIDs server-side.
          generateId: "uuid",
        },
      },
      emailAndPassword: {
        enabled: true,
        autoSignIn: true,
        minPasswordLength: 12,
        maxPasswordLength: 128,
        requireEmailVerification: false,
      },
      user: {
        modelName: "identity_users",
        fields: {
          emailVerified: "email_verified",
          createdAt: "created_at",
          updatedAt: "updated_at",
        },
        additionalFields: {
          vibeflowAccountId: {
            type: "string",
            // The hook supplies this server-side before persistence. Keep it
            // optional to Better Auth input parsing so a client can never send it.
            required: false,
            input: false,
            returned: true,
            fieldName: "vibeflow_account_id",
          },
        },
      },
      session: {
        modelName: "identity_sessions",
        fields: {
          expiresAt: "expires_at",
          createdAt: "created_at",
          updatedAt: "updated_at",
          ipAddress: "ip_address",
          userAgent: "user_agent",
          userId: "user_id",
        },
        expiresIn: SESSION_EXPIRES_IN_SECONDS,
        updateAge: SESSION_UPDATE_AGE_SECONDS,
        freshAge: SESSION_FRESH_AGE_SECONDS,
        cookieCache: {
          enabled: false,
        },
      },
      account: {
        modelName: "identity_accounts",
        fields: {
          accountId: "account_id",
          providerId: "provider_id",
          userId: "user_id",
          accessToken: "access_token",
          refreshToken: "refresh_token",
          idToken: "id_token",
          accessTokenExpiresAt: "access_token_expires_at",
          refreshTokenExpiresAt: "refresh_token_expires_at",
          createdAt: "created_at",
          updatedAt: "updated_at",
        },
        accountLinking: {
          enabled: false,
        },
        storeAccountCookie: false,
      },
      verification: {
        modelName: "identity_verifications",
        fields: {
          expiresAt: "expires_at",
          createdAt: "created_at",
          updatedAt: "updated_at",
        },
      },
      databaseHooks: {
        user: {
          create: {
            before: async (user) => ({
              data: {
                ...user,
                // The VibeFlow server generates this opaque Account ID before
                // inserting the Better Auth user. PostgreSQL's BEFORE INSERT
                // trigger creates the canonical Account with the same ID in the
                // surrounding signup transaction.
                vibeflowAccountId: crypto.randomUUID(),
              },
            }),
          },
        },
      },
    });
  }
}
