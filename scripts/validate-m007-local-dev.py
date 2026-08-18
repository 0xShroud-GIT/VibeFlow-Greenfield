#!/usr/bin/env python3
"""M-007 validator entrypoint with the owner-authorized Round-6 image remediation.

The retained Arena validator remains byte-for-byte in _validate_m007_core.py.
This entrypoint preserves that full durable/mutation policy and narrows one
Round-5 stop-report decision: the accepted trixie-slim base may be wrapped by
one exact, deterministic Dockerfile that removes unused bundled npm/yarn so
the unchanged Trivy HIGH/CRITICAL gate can pass.
"""

from __future__ import annotations

import json

import _validate_m007_core as core

BASE_IMAGE = (
    "docker.io/library/node:24.19.0-trixie-slim@"
    "sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d"
)

EXPECTED_DOCKERFILE = """# VibeFlow M-007 repository development environment — owner-authorized remediation layer.
# Deterministic filesystem-only removal of unused bundled npm/yarn.
# No apt/apk install or upgrade, no download, no floating reference, no new tool.
FROM docker.io/library/node:24.19.0-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d

RUN rm -rf /usr/local/lib/node_modules/npm \\
           /opt/yarn-v1.22.22 \\
  && rm -f /usr/local/bin/npm \\
           /usr/local/bin/npx \\
           /usr/local/bin/yarn \\
           /usr/local/bin/yarnpkg

USER node
"""

LEGACY_IMAGE_ERRORS = {
    "devcontainer: active M-007 forbids a .devcontainer/Dockerfile (packet trigger not met)",
    "devcontainer: image must be a digest-pinned reference name:tag@sha256:<64hex>",
}


class OwnerRemediatedValidator(core.Validator):
    """Preserve the Round-5 validator and admit only the exact owner decision."""

    def check_devcontainer(self) -> None:
        text = self.read_text(core.DEVCONTAINER_REL)
        config: dict[str, object] | None = None
        if text is not None:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    config = parsed
            except json.JSONDecodeError:
                pass

        owner_shape = bool(
            config is not None
            and config.get("build") == {"dockerfile": "Dockerfile"}
            and "image" not in config
            and config.get("dockerFile") is None
            and config.get("dockerComposeFile") is None
        )

        start = len(self.errors)
        super().check_devcontainer()

        if not owner_shape:
            return

        dockerfile = self.read_text(core.DOCKERFILE_REL)
        if dockerfile != EXPECTED_DOCKERFILE:
            self.err(
                "devcontainer",
                "owner-authorized remediation Dockerfile must exactly match the locked M-007 content",
            )
            return

        policy = self.read_json(core.POLICY_REL) or {}
        base = policy.get("base_image") or {}
        if not isinstance(base, dict):
            self.err("devcontainer", "policy base_image must be an object")
            return
        if base.get("dockerfile") is not True:
            self.err("devcontainer", "policy must record the owner-authorized Dockerfile remediation")
            return
        if base.get("remediation_dockerfile") != core.DOCKERFILE_REL:
            self.err("devcontainer", "policy remediation_dockerfile must be .devcontainer/Dockerfile")
            return
        if base.get("semantic_reference") != core.BASE_IMAGE["semantic_reference"]:
            self.err("devcontainer", "remediation must retain the locked trixie-slim semantic base")
            return
        if base.get("digest") != core.BASE_IMAGE["digest"]:
            self.err("devcontainer", "remediation must retain the locked trixie-slim digest")
            return

        # The core validator predates the explicit owner decision and therefore
        # reports exactly two legacy errors for an otherwise-valid build-based
        # configuration. Remove only those exact legacy diagnostics; every
        # other invariant and mutation remains enforced by the retained core.
        self.errors[start:] = [
            error for error in self.errors[start:] if error not in LEGACY_IMAGE_ERRORS
        ]


core.Validator = OwnerRemediatedValidator

if __name__ == "__main__":
    raise SystemExit(core.main())
