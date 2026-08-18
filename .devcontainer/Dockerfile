# VibeFlow M-007 repository development environment — remediation layer.
#
# Derives FROM the official Node.js 24.19.0 trixie image pinned by immutable
# OCI digest (index sha256:66bb8d36ae1ddd72199ed235a089904874ca4079ee517936ca3adb80506a75c1,
# amd64 sha256:05c60dce78787e477fd7c0d61d9efcd5b7ae3f21a8b18787c7ef3daf9c9a2ad3,
# arm64 sha256:3f734716ad93ed2aa8a6eec03f2404de09b8505f3f9ce06c15933ffaf49ec65c).
#
# Deterministic remediation (M-007 packet §4.3 / §8): the official image
# bundles npm and yarn package-manager material that VibeFlow does not use
# (VibeFlow uses Corepack + pnpm). This layer removes that unused bundled
# surface filesystem-only:
#   - no apt/apk upgrade/install (nothing is installed or upgraded)
#   - no curl-pipe installers
#   - no floating package/image references
#   - Node.js 24.19.0, Corepack and git are retained unchanged.
# Corepack provides pnpm/yarn shims independently of npm; the M-007
# bootstrap, runtime smoke, check chain and retained contracts never invoke
# the npm or yarn executables.

FROM docker.io/library/node:24.19.0-trixie@sha256:66bb8d36ae1ddd72199ed235a089904874ca4079ee517936ca3adb80506a75c1

# Remove unused bundled npm and yarn (deterministic filesystem-only removal).
# - npm:   /usr/local/lib/node_modules/npm + /usr/local/bin/npm, /usr/local/bin/npx
# - yarn:  /opt/yarn-v1.22.22 + /usr/local/bin/yarn, /usr/local/bin/yarnpkg
# Corepack (/usr/local/lib/node_modules/corepack) is retained.
RUN rm -rf /usr/local/lib/node_modules/npm \
           /opt/yarn-v1.22.22 \
  && rm -f  /usr/local/bin/npm \
            /usr/local/bin/npx \
            /usr/local/bin/yarn \
            /usr/local/bin/yarnpkg
