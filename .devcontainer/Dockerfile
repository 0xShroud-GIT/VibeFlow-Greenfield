# VibeFlow M-007 repository development environment — owner-authorized remediation layer.
# Deterministic filesystem-only removal of unused bundled npm/yarn.
# No apt/apk install or upgrade, no download, no floating reference, no new tool.
FROM docker.io/library/node:24.19.0-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d

RUN rm -rf /usr/local/lib/node_modules/npm \
           /opt/yarn-v1.22.22 \
  && rm -f /usr/local/bin/npm \
           /usr/local/bin/npx \
           /usr/local/bin/yarn \
           /usr/local/bin/yarnpkg

USER node
