/**
 * Browser transport owns these strings. The Identity boundary never persists or
 * exposes a session token as ordinary product state.
 */
export function setCookieHeaders(headers: Headers): readonly string[] {
  const candidate = headers as Headers & {
    getSetCookie?: () => string[];
  };

  if (typeof candidate.getSetCookie === "function") {
    return candidate.getSetCookie();
  }

  const singleHeader = headers.get("set-cookie");
  return singleHeader === null ? [] : [singleHeader];
}

/** Test/server-adapter helper for forwarding cookies on a subsequent request. */
export function cookieRequestHeader(setCookies: readonly string[]): string {
  return setCookies
    .map((value) => value.split(";", 1)[0]?.trim() ?? "")
    .filter((value) => value.length > 0)
    .join("; ");
}
