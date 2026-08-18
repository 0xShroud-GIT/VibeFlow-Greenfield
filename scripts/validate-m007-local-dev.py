#!/usr/bin/env python3
"""M-007 local development environment static validator (retained after M-007).

Network-free, stdlib-only static gate for the repository development
environment. It distinguishes two modes:

Active M-007 snapshot (M-007 is READY/IN_PROGRESS/REVIEW)
    Requires the exact accepted initial environment shape: digest-pinned
    `node:24.19.0` base image, the single registered digest-pinned python
    feature, non-root dev user, no forwarded ports / privileged / host
    network / docker socket / Docker-in-Docker / raw secrets, exact
    repository toolchain agreement, frozen-lockfile bootstrap, mission and
    ledger synchronization, and an exact capability-status snapshot.

Durable later-mission mode (M-007 is DONE)
    Permits a later owning mission to extend the environment (forwarded
    ports, additional digest-pinned registered features, benign environment
    metadata, mounts, service containers) only when explicitly declared and
    locked under `durable_extension_policy.extensions` in
    infrastructure/dev/dev-environment-policy.json, while permanently
    retaining: immutable image/tool provenance, no raw secrets in
    committed/client-readable configuration, no privileged / docker-socket /
    host-network expansion, exact repository toolchain agreement, frozen-
    lockfile dependency installation, mission/ledger synchronization, and
    Dev Containers as the adopted portable descriptor.

This validator intentionally does not freeze the whole future workflow or
environment shape (the earlier M-006 mistake); later missions declare growth
through the extension lock instead.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
M007 = "M-007"

# --- Immutable M-007 provenance (authority: infrastructure/dev/dev-environment-policy.json) ---
BASE_IMAGE = {
    "semantic_reference": "docker.io/library/node:24.19.0",
    "digest": "sha256:934240a162082fd8b8a2f90cd5114446443f1eba1c5378f6687167ca405e6584",
    "architectures": {
        "amd64": "sha256:f6d02cf1353049cf3658e6ce9ec03c6877a6479495f122062d195e2279d01055",
        "arm64": "sha256:7e4b2953088599075c288871d109e23bc7a33384b96ca443a7cfb7b5c318b099",
        "ppc64le": "sha256:56c4cadee33f1eff8ace75854383652bcf9584319747bb2373e010ce86e00989",
    },
    "upstream_source": "https://github.com/nodejs/docker-node",
    "node_version": "24.19.0",
}

PYTHON_FEATURE = {
    "id": "python",
    "version": "1.8.0",
    "semantic_tag": "ghcr.io/devcontainers/features/python:1",
    "digest_reference": (
        "ghcr.io/devcontainers/features/python@sha256:"
        "fbcad6955caeecc5ad3f7886baf652e25cba5225a6c4c2287c536de2e5607511"
    ),
    "upstream_source": "https://github.com/devcontainers/features/tree/main/src/python",
}

TOOLCHAIN = {
    "node": "24.19.0",
    "pnpm": "11.4.0",
    "typescript": "6.0.3",
    "turborepo": "2.10.6",
    "vitest": "4.1.7",
    "typebox": "1.3.6",
}

REL_M006_BASELINE = {
    "VF-REL-002": "IMPLEMENTED",
    "VF-REL-003": "IMPLEMENTED",
    "VF-REL-004": "IMPLEMENTED",
    "VF-REL-005": "IN_PROGRESS",
}

STATUS_RANK = {
    "NOT_STARTED": 0,
    "IN_PROGRESS": 1,
    "IMPLEMENTED": 2,
    "VERIFIED": 3,
    "COMPLETE": 4,
}

# Exact accepted M-007 capability snapshot (active mode). Generated from the
# accepted ledger; only VF-ENV-005 advances in M-007 (NOT_STARTED ->
# IN_PROGRESS). Durable mode intentionally does not freeze unrelated rows.
CAPABILITY_SNAPSHOT = {
    "VF-EXP-001": "NOT_STARTED",
    "VF-EXP-002": "NOT_STARTED",
    "VF-EXP-003": "NOT_STARTED",
    "VF-EXP-004": "NOT_STARTED",
    "VF-EXP-005": "NOT_STARTED",
    "VF-EXP-006": "NOT_STARTED",
    "VF-EXP-007": "NOT_STARTED",
    "VF-EXP-008": "NOT_STARTED",
    "VF-EXP-009": "NOT_STARTED",
    "VF-EXP-010": "NOT_STARTED",
    "VF-EXP-011": "NOT_STARTED",
    "VF-EXP-012": "NOT_STARTED",
    "VF-EXP-013": "NOT_STARTED",
    "VF-EXP-014": "NOT_STARTED",
    "VF-EXP-015": "NOT_STARTED",
    "VF-EXP-016": "NOT_STARTED",
    "VF-MOB-001": "NOT_STARTED",
    "VF-MOB-002": "NOT_STARTED",
    "VF-MOB-003": "NOT_STARTED",
    "VF-MOB-004": "NOT_STARTED",
    "VF-MOB-005": "NOT_STARTED",
    "VF-MOB-006": "NOT_STARTED",
    "VF-MOB-007": "NOT_STARTED",
    "VF-MOB-008": "NOT_STARTED",
    "VF-MOB-009": "NOT_STARTED",
    "VF-MOB-010": "NOT_STARTED",
    "VF-MOB-011": "NOT_STARTED",
    "VF-MOB-012": "NOT_STARTED",
    "VF-MOB-013": "NOT_STARTED",
    "VF-MOB-014": "NOT_STARTED",
    "VF-MOB-015": "NOT_STARTED",
    "VF-MOB-016": "NOT_STARTED",
    "VF-MOB-017": "NOT_STARTED",
    "VF-MOB-018": "NOT_STARTED",
    "VF-MOB-019": "NOT_STARTED",
    "VF-MOB-020": "NOT_STARTED",
    "VF-MOB-021": "NOT_STARTED",
    "VF-MOB-022": "NOT_STARTED",
    "VF-MOB-023": "NOT_STARTED",
    "VF-BRG-001": "NOT_STARTED",
    "VF-BRG-002": "NOT_STARTED",
    "VF-BRG-003": "NOT_STARTED",
    "VF-BRG-004": "NOT_STARTED",
    "VF-BRG-005": "NOT_STARTED",
    "VF-BRG-006": "NOT_STARTED",
    "VF-BRG-007": "NOT_STARTED",
    "VF-BRG-008": "NOT_STARTED",
    "VF-BRG-009": "NOT_STARTED",
    "VF-BRG-010": "NOT_STARTED",
    "VF-BRG-011": "NOT_STARTED",
    "VF-BRG-012": "NOT_STARTED",
    "VF-BRG-013": "NOT_STARTED",
    "VF-BRG-014": "NOT_STARTED",
    "VF-BRG-015": "NOT_STARTED",
    "VF-BRG-016": "NOT_STARTED",
    "VF-BRG-017": "NOT_STARTED",
    "VF-BRG-018": "NOT_STARTED",
    "VF-BRG-019": "NOT_STARTED",
    "VF-BRG-020": "NOT_STARTED",
    "VF-BRG-021": "NOT_STARTED",
    "VF-BRG-022": "NOT_STARTED",
    "VF-BRG-023": "NOT_STARTED",
    "VF-BRG-024": "NOT_STARTED",
    "VF-IAM-001": "NOT_STARTED",
    "VF-IAM-002": "NOT_STARTED",
    "VF-IAM-003": "NOT_STARTED",
    "VF-IAM-004": "NOT_STARTED",
    "VF-IAM-005": "NOT_STARTED",
    "VF-IAM-006": "NOT_STARTED",
    "VF-IAM-007": "NOT_STARTED",
    "VF-IAM-008": "NOT_STARTED",
    "VF-IAM-009": "NOT_STARTED",
    "VF-IAM-010": "NOT_STARTED",
    "VF-IAM-011": "NOT_STARTED",
    "VF-IAM-012": "NOT_STARTED",
    "VF-IAM-013": "NOT_STARTED",
    "VF-IAM-014": "NOT_STARTED",
    "VF-IAM-015": "NOT_STARTED",
    "VF-IAM-016": "NOT_STARTED",
    "VF-PRJ-001": "NOT_STARTED",
    "VF-PRJ-002": "NOT_STARTED",
    "VF-PRJ-003": "NOT_STARTED",
    "VF-PRJ-004": "NOT_STARTED",
    "VF-PRJ-005": "NOT_STARTED",
    "VF-PRJ-006": "NOT_STARTED",
    "VF-PRJ-007": "NOT_STARTED",
    "VF-PRJ-008": "NOT_STARTED",
    "VF-PRJ-009": "NOT_STARTED",
    "VF-PRJ-010": "NOT_STARTED",
    "VF-PRJ-011": "NOT_STARTED",
    "VF-PRJ-012": "NOT_STARTED",
    "VF-PRJ-013": "NOT_STARTED",
    "VF-PRJ-014": "NOT_STARTED",
    "VF-PRJ-015": "NOT_STARTED",
    "VF-PRJ-016": "NOT_STARTED",
    "VF-PRJ-017": "NOT_STARTED",
    "VF-AGT-001": "NOT_STARTED",
    "VF-AGT-002": "NOT_STARTED",
    "VF-AGT-003": "NOT_STARTED",
    "VF-AGT-004": "NOT_STARTED",
    "VF-AGT-005": "NOT_STARTED",
    "VF-AGT-006": "NOT_STARTED",
    "VF-AGT-007": "NOT_STARTED",
    "VF-AGT-008": "NOT_STARTED",
    "VF-AGT-009": "NOT_STARTED",
    "VF-AGT-010": "NOT_STARTED",
    "VF-AGT-011": "NOT_STARTED",
    "VF-AGT-012": "NOT_STARTED",
    "VF-AGT-013": "NOT_STARTED",
    "VF-AGT-014": "NOT_STARTED",
    "VF-AGT-015": "NOT_STARTED",
    "VF-AGT-016": "NOT_STARTED",
    "VF-AGT-017": "NOT_STARTED",
    "VF-AGT-018": "NOT_STARTED",
    "VF-AGT-019": "NOT_STARTED",
    "VF-AGT-020": "NOT_STARTED",
    "VF-AGT-021": "NOT_STARTED",
    "VF-AGT-022": "NOT_STARTED",
    "VF-AGT-023": "NOT_STARTED",
    "VF-AGT-024": "NOT_STARTED",
    "VF-AGT-025": "NOT_STARTED",
    "VF-AGT-026": "NOT_STARTED",
    "VF-AGT-027": "NOT_STARTED",
    "VF-AGT-028": "NOT_STARTED",
    "VF-AGT-029": "NOT_STARTED",
    "VF-AGT-030": "NOT_STARTED",
    "VF-AGT-031": "NOT_STARTED",
    "VF-AGT-032": "NOT_STARTED",
    "VF-WKS-001": "NOT_STARTED",
    "VF-WKS-002": "NOT_STARTED",
    "VF-WKS-003": "NOT_STARTED",
    "VF-WKS-004": "NOT_STARTED",
    "VF-WKS-005": "NOT_STARTED",
    "VF-WKS-006": "NOT_STARTED",
    "VF-WKS-007": "NOT_STARTED",
    "VF-WKS-008": "NOT_STARTED",
    "VF-WKS-009": "NOT_STARTED",
    "VF-WKS-010": "NOT_STARTED",
    "VF-WKS-011": "NOT_STARTED",
    "VF-WKS-012": "NOT_STARTED",
    "VF-WKS-013": "NOT_STARTED",
    "VF-WKS-014": "NOT_STARTED",
    "VF-WKS-015": "NOT_STARTED",
    "VF-WKS-016": "NOT_STARTED",
    "VF-WKS-017": "NOT_STARTED",
    "VF-WKS-018": "NOT_STARTED",
    "VF-WKS-019": "NOT_STARTED",
    "VF-WKS-020": "NOT_STARTED",
    "VF-WKS-021": "NOT_STARTED",
    "VF-WKS-022": "NOT_STARTED",
    "VF-WKS-023": "NOT_STARTED",
    "VF-WKS-024": "NOT_STARTED",
    "VF-GIT-001": "NOT_STARTED",
    "VF-GIT-002": "NOT_STARTED",
    "VF-GIT-003": "NOT_STARTED",
    "VF-GIT-004": "NOT_STARTED",
    "VF-GIT-005": "NOT_STARTED",
    "VF-GIT-006": "NOT_STARTED",
    "VF-GIT-007": "NOT_STARTED",
    "VF-GIT-008": "NOT_STARTED",
    "VF-GIT-009": "NOT_STARTED",
    "VF-GIT-010": "NOT_STARTED",
    "VF-GIT-011": "NOT_STARTED",
    "VF-GIT-012": "NOT_STARTED",
    "VF-GIT-013": "NOT_STARTED",
    "VF-GIT-014": "NOT_STARTED",
    "VF-GIT-015": "NOT_STARTED",
    "VF-GIT-016": "NOT_STARTED",
    "VF-GIT-017": "NOT_STARTED",
    "VF-CON-001": "NOT_STARTED",
    "VF-CON-002": "NOT_STARTED",
    "VF-CON-003": "NOT_STARTED",
    "VF-CON-004": "NOT_STARTED",
    "VF-CON-005": "NOT_STARTED",
    "VF-CON-006": "NOT_STARTED",
    "VF-CON-007": "NOT_STARTED",
    "VF-CON-008": "NOT_STARTED",
    "VF-CON-009": "NOT_STARTED",
    "VF-CON-010": "NOT_STARTED",
    "VF-CON-011": "NOT_STARTED",
    "VF-CON-012": "NOT_STARTED",
    "VF-CON-013": "NOT_STARTED",
    "VF-CON-014": "NOT_STARTED",
    "VF-CON-015": "NOT_STARTED",
    "VF-CON-016": "NOT_STARTED",
    "VF-CON-017": "NOT_STARTED",
    "VF-CON-018": "NOT_STARTED",
    "VF-CON-019": "NOT_STARTED",
    "VF-CON-020": "NOT_STARTED",
    "VF-DAT-001": "NOT_STARTED",
    "VF-DAT-002": "NOT_STARTED",
    "VF-DAT-003": "NOT_STARTED",
    "VF-DAT-004": "NOT_STARTED",
    "VF-DAT-005": "NOT_STARTED",
    "VF-DAT-006": "NOT_STARTED",
    "VF-DAT-007": "NOT_STARTED",
    "VF-DAT-008": "NOT_STARTED",
    "VF-DAT-009": "NOT_STARTED",
    "VF-DAT-010": "NOT_STARTED",
    "VF-DAT-011": "NOT_STARTED",
    "VF-DAT-012": "NOT_STARTED",
    "VF-DAT-013": "NOT_STARTED",
    "VF-DAT-014": "NOT_STARTED",
    "VF-DEP-001": "NOT_STARTED",
    "VF-DEP-002": "NOT_STARTED",
    "VF-DEP-003": "NOT_STARTED",
    "VF-DEP-004": "NOT_STARTED",
    "VF-DEP-005": "NOT_STARTED",
    "VF-DEP-006": "NOT_STARTED",
    "VF-DEP-007": "NOT_STARTED",
    "VF-DEP-008": "NOT_STARTED",
    "VF-DEP-009": "NOT_STARTED",
    "VF-DEP-010": "NOT_STARTED",
    "VF-DEP-011": "NOT_STARTED",
    "VF-DEP-012": "NOT_STARTED",
    "VF-DEP-013": "NOT_STARTED",
    "VF-DEP-014": "NOT_STARTED",
    "VF-DEP-015": "NOT_STARTED",
    "VF-DEP-016": "NOT_STARTED",
    "VF-DEP-017": "NOT_STARTED",
    "VF-DEP-018": "NOT_STARTED",
    "VF-DEP-019": "NOT_STARTED",
    "VF-DEP-020": "NOT_STARTED",
    "VF-VER-001": "NOT_STARTED",
    "VF-VER-002": "NOT_STARTED",
    "VF-VER-003": "NOT_STARTED",
    "VF-VER-004": "NOT_STARTED",
    "VF-VER-005": "NOT_STARTED",
    "VF-VER-006": "NOT_STARTED",
    "VF-VER-007": "NOT_STARTED",
    "VF-VER-008": "NOT_STARTED",
    "VF-VER-009": "NOT_STARTED",
    "VF-VER-010": "NOT_STARTED",
    "VF-VER-011": "NOT_STARTED",
    "VF-VER-012": "NOT_STARTED",
    "VF-VER-013": "NOT_STARTED",
    "VF-VER-014": "NOT_STARTED",
    "VF-VER-015": "NOT_STARTED",
    "VF-VER-016": "NOT_STARTED",
    "VF-VER-017": "NOT_STARTED",
    "VF-VER-018": "NOT_STARTED",
    "VF-VER-019": "NOT_STARTED",
    "VF-OBS-001": "NOT_STARTED",
    "VF-OBS-002": "NOT_STARTED",
    "VF-OBS-003": "NOT_STARTED",
    "VF-OBS-004": "NOT_STARTED",
    "VF-OBS-005": "NOT_STARTED",
    "VF-OBS-006": "NOT_STARTED",
    "VF-OBS-007": "NOT_STARTED",
    "VF-OBS-008": "NOT_STARTED",
    "VF-OBS-009": "NOT_STARTED",
    "VF-OBS-010": "NOT_STARTED",
    "VF-OBS-011": "NOT_STARTED",
    "VF-OBS-012": "NOT_STARTED",
    "VF-OBS-013": "NOT_STARTED",
    "VF-OBS-014": "NOT_STARTED",
    "VF-DSN-001": "NOT_STARTED",
    "VF-DSN-002": "NOT_STARTED",
    "VF-DSN-003": "NOT_STARTED",
    "VF-DSN-004": "NOT_STARTED",
    "VF-DSN-005": "NOT_STARTED",
    "VF-DSN-006": "NOT_STARTED",
    "VF-DSN-007": "NOT_STARTED",
    "VF-DSN-008": "NOT_STARTED",
    "VF-DSN-009": "NOT_STARTED",
    "VF-DSN-010": "NOT_STARTED",
    "VF-DSN-011": "NOT_STARTED",
    "VF-DSN-012": "NOT_STARTED",
    "VF-DSN-013": "NOT_STARTED",
    "VF-DSN-014": "NOT_STARTED",
    "VF-DSN-015": "NOT_STARTED",
    "VF-DSN-016": "NOT_STARTED",
    "VF-DSN-017": "NOT_STARTED",
    "VF-DSN-018": "NOT_STARTED",
    "VF-DSN-019": "NOT_STARTED",
    "VF-NAT-001": "NOT_STARTED",
    "VF-NAT-002": "NOT_STARTED",
    "VF-NAT-003": "NOT_STARTED",
    "VF-NAT-004": "NOT_STARTED",
    "VF-NAT-005": "NOT_STARTED",
    "VF-NAT-006": "NOT_STARTED",
    "VF-NAT-007": "NOT_STARTED",
    "VF-NAT-008": "NOT_STARTED",
    "VF-NAT-009": "NOT_STARTED",
    "VF-NAT-010": "NOT_STARTED",
    "VF-NAT-011": "NOT_STARTED",
    "VF-NAT-012": "NOT_STARTED",
    "VF-NAT-013": "NOT_STARTED",
    "VF-AUT-001": "NOT_STARTED",
    "VF-AUT-002": "NOT_STARTED",
    "VF-AUT-003": "NOT_STARTED",
    "VF-AUT-004": "NOT_STARTED",
    "VF-AUT-005": "NOT_STARTED",
    "VF-COL-001": "NOT_STARTED",
    "VF-COL-002": "NOT_STARTED",
    "VF-COL-003": "NOT_STARTED",
    "VF-COL-004": "NOT_STARTED",
    "VF-COL-005": "NOT_STARTED",
    "VF-COL-006": "NOT_STARTED",
    "VF-COL-007": "NOT_STARTED",
    "VF-COL-008": "NOT_STARTED",
    "VF-COL-009": "NOT_STARTED",
    "VF-COL-010": "NOT_STARTED",
    "VF-COL-011": "NOT_STARTED",
    "VF-COL-012": "NOT_STARTED",
    "VF-COL-013": "NOT_STARTED",
    "VF-COL-014": "NOT_STARTED",
    "VF-BIL-001": "NOT_STARTED",
    "VF-BIL-002": "NOT_STARTED",
    "VF-BIL-003": "NOT_STARTED",
    "VF-BIL-004": "NOT_STARTED",
    "VF-BIL-005": "NOT_STARTED",
    "VF-BIL-006": "NOT_STARTED",
    "VF-BIL-007": "NOT_STARTED",
    "VF-BIL-008": "NOT_STARTED",
    "VF-BIL-009": "NOT_STARTED",
    "VF-BIL-010": "NOT_STARTED",
    "VF-BIL-011": "NOT_STARTED",
    "VF-BIL-012": "NOT_STARTED",
    "VF-BIL-013": "NOT_STARTED",
    "VF-BIL-014": "NOT_STARTED",
    "VF-BIL-015": "NOT_STARTED",
    "VF-BIL-016": "NOT_STARTED",
    "VF-BIL-017": "NOT_STARTED",
    "VF-ECO-001": "NOT_STARTED",
    "VF-ECO-002": "NOT_STARTED",
    "VF-ECO-003": "NOT_STARTED",
    "VF-ECO-004": "NOT_STARTED",
    "VF-ECO-005": "NOT_STARTED",
    "VF-ECO-006": "NOT_STARTED",
    "VF-SAA-001": "NOT_STARTED",
    "VF-SAA-002": "NOT_STARTED",
    "VF-SAA-003": "NOT_STARTED",
    "VF-SAA-004": "NOT_STARTED",
    "VF-SAA-005": "NOT_STARTED",
    "VF-SAA-006": "NOT_STARTED",
    "VF-SAA-007": "NOT_STARTED",
    "VF-SAA-008": "NOT_STARTED",
    "VF-SAA-009": "NOT_STARTED",
    "VF-SAA-010": "NOT_STARTED",
    "VF-SAA-011": "NOT_STARTED",
    "VF-REL-001": "NOT_STARTED",
    "VF-REL-002": "IMPLEMENTED",
    "VF-REL-003": "IMPLEMENTED",
    "VF-REL-004": "IMPLEMENTED",
    "VF-REL-005": "IN_PROGRESS",
    "VF-REL-006": "NOT_STARTED",
    "VF-REL-007": "NOT_STARTED",
    "VF-REL-008": "NOT_STARTED",
    "VF-REL-009": "NOT_STARTED",
    "VF-REL-010": "NOT_STARTED",
    "VF-REL-011": "NOT_STARTED",
    "VF-ENV-001": "NOT_STARTED",
    "VF-ENV-002": "NOT_STARTED",
    "VF-ENV-003": "NOT_STARTED",
    "VF-ENV-004": "NOT_STARTED",
    "VF-ENV-005": "IN_PROGRESS",
    "VF-GRO-001": "NOT_STARTED",
    "VF-GRO-002": "NOT_STARTED",
    "VF-GRO-003": "NOT_STARTED",
    "VF-GRO-004": "NOT_STARTED",
    "VF-UNK-001": "NOT_STARTED",
    "VF-UNK-002": "NOT_STARTED",
    "VF-UNK-003": "NOT_STARTED",
    "VF-UNK-004": "NOT_STARTED",
    "VF-UNK-005": "NOT_STARTED",
    "VF-UNK-006": "NOT_STARTED",
    "VF-UNK-007": "NOT_STARTED",
    "VF-UNK-008": "NOT_STARTED",
    "VF-UNK-009": "NOT_STARTED",
    "VF-UNK-010": "NOT_STARTED",
    "VF-UNK-011": "NOT_STARTED",
    "VF-UNK-012": "NOT_STARTED",
    "VF-UNK-013": "NOT_STARTED",
    "VF-UNK-014": "NOT_STARTED",
    "VF-UNK-015": "NOT_STARTED",
    "VF-UNK-016": "NOT_STARTED",
    "VF-UNK-017": "NOT_STARTED",
    "VF-UNK-018": "NOT_STARTED",
    "VF-UNK-019": "NOT_STARTED",
    "VF-UNK-020": "NOT_STARTED",
    "VF-UNK-021": "NOT_STARTED",
    "VF-UNK-022": "NOT_STARTED",
    "VF-UNK-023": "NOT_STARTED",
    "VF-UNK-024": "NOT_STARTED",
    "VF-PORT-001": "NOT_STARTED",
    "VF-PORT-002": "NOT_STARTED",
    "VF-PORT-003": "NOT_STARTED",
    "VF-PORT-004": "NOT_STARTED",
    "VF-PORT-005": "NOT_STARTED",
    "VF-TRU-001": "NOT_STARTED",
    "VF-TRU-002": "NOT_STARTED",
    "VF-TRU-003": "NOT_STARTED",
    "VF-TRU-004": "NOT_STARTED",
    "VF-TRU-005": "NOT_STARTED",
    "VF-POL-001": "NOT_STARTED",
    "VF-POL-002": "NOT_STARTED",
    "VF-POL-003": "NOT_STARTED",
    "VF-AI-001": "NOT_STARTED",
    "VF-AI-002": "NOT_STARTED",
    "VF-AI-003": "NOT_STARTED",
    "VF-UX-001": "NOT_STARTED",
    "VF-UX-002": "NOT_STARTED",
    "VF-ECO-007": "NOT_STARTED",
    "VF-ECO-008": "NOT_STARTED",
}

DEV_SCRIPTS = (
    "scripts/dev-doctor.py",
    "scripts/dev-bootstrap.py",
    "scripts/dev-runtime-smoke.py",
)

# Raw-looking credential/token material that must never appear in devcontainer
# environment fields, mounts, image arguments, or committed env examples.
SECRET_PATTERNS = (
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
    r"ghp_[A-Za-z0-9]{36}",
    r"github_pat_[A-Za-z0-9_]{40,}",
    r"AKIA[0-9A-Z]{16}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"sk-[A-Za-z0-9]{20,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
)

HOST_CREDENTIAL_REF = re.compile(
    r"(?:/root/|~/|/\$HOME/|\$HOME/|/home/[^/]+/)?"
    r"\.?(?:ssh|aws|azure|config/gcloud|\.docker|git-credentials|kube|netrc)"
)

DOCKER_SOCKET_REF = re.compile(r"docker\.sock")

# The canonical M-007 node_modules volume: shadows the host checkout's
# node_modules inside the container so `pnpm install --frozen-lockfile` runs
# non-interactively against a fresh container-local modules dir (fixes
# ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY) without mutating host files.
NODE_MODULES_VOLUME = (
    "source=vibeflow-node-modules,target=${containerWorkspaceFolder}/node_modules,type=volume"
)

DEVCONTAINER_REL = ".devcontainer/devcontainer.json"
POLICY_REL = "infrastructure/dev/dev-environment-policy.json"
INTENDED_WORKFLOWS_REL = "evidence/missions/M-007/INTENDED_WORKFLOWS.patch"
EVIDENCE_MD_REL = "evidence/missions/M-007/LOCAL_DEV_ENVIRONMENT.md"
EVIDENCE_JSON_REL = "evidence/missions/M-007/LOCAL_DEV_ENVIRONMENT.json"

DEVCONTAINERS_CI_ACTION = "devcontainers/ci"
DEVCONTAINERS_CI_PIN = "513af61f4de4f75d37e4438f184ba4358f0fc1ca"
DEVCONTAINERS_CI_VERSION = "0.3.1900000450"


def parse_statuses(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    dag_text = (root / "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml").read_text(encoding="utf-8")
    dag: dict[str, str] = {}
    current: str | None = None
    for line in dag_text.splitlines():
        match = re.match(r"^- mission_id: (M-\d{3})$", line)
        if match:
            current = match.group(1)
        elif current and (match := re.match(r"^  status: ([A-Z_]+)$", line)):
            dag[current] = match.group(1)
            current = None
    register: dict[str, str] = {}
    with (root / "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        register = {row["mission_id"]: row["status"] for row in csv.DictReader(handle)}
    return dag, register


class Validator:
    def __init__(self, root: Path, mode: str) -> None:
        self.root = root
        self.errors: list[str] = []
        self.counts: dict[str, int] = {}
        self.mode = mode
        self.m007_status = ""
        self.active_later_mission: str | None = None
        self.completed_later_missions: set[str] = set()

    # ---------- helpers ----------
    def err(self, area: str, message: str) -> None:
        self.errors.append(f"{area}: {message}")

    def read_text(self, rel: str) -> str | None:
        path = self.root / rel
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def read_json(self, rel: str) -> dict | None:
        text = self.read_text(rel)
        if text is None:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            self.err("json", f"{rel} is not valid JSON: {exc}")
            return None
        return value if isinstance(value, dict) else None

    # ---------- mission / ledger synchronization ----------
    def check_mission_progression(self) -> None:
        dag, register = parse_statuses(self.root)
        for mid in sorted(set(dag) | set(register)):
            if dag.get(mid) != register.get(mid):
                self.err("mission", f"{mid} status disagrees between DAG and register")
        for index in range(1, 7):
            mid = f"M-{index:03d}"
            if dag.get(mid) != "DONE" or register.get(mid) != "DONE":
                self.err("mission", f"{mid} must be DONE before M-007 is active (successor consumption)")
        self.m007_status = str(dag.get(M007) or "")
        active_later: list[str] = []
        if self.mode == "active":
            if self.m007_status not in {"READY", "IN_PROGRESS", "REVIEW"}:
                self.err("mission", f"M-007 must be READY/IN_PROGRESS/REVIEW in active mode, got {self.m007_status!r}")
            for index in range(8, 152):
                mid = f"M-{index:03d}"
                if dag.get(mid) != "LOCKED" or register.get(mid) != "LOCKED":
                    self.err("mission", f"{mid} must remain LOCKED while M-007 is {self.m007_status}")
        else:
            if self.m007_status != "DONE":
                self.err("mission", f"M-007 must be DONE in durable mode, got {self.m007_status!r}")
            active_later = [
                mid for mid, value in dag.items()
                if int(mid.split("-")[1]) >= 8 and value in {"READY", "IN_PROGRESS", "REVIEW", "BLOCKED"}
            ]
            if len(active_later) != 1:
                self.err("mission", f"accepted M-007 requires one active later mission, got {active_later}")
            elif len(active_later) == 1:
                self.active_later_mission = active_later[0]
                self.completed_later_missions = {
                    mid for mid, value in dag.items()
                    if int(mid.split("-")[1]) >= 8
                    and mid != self.active_later_mission
                    and value == "DONE"
                }

        expected_active = M007 if self.mode == "active" else (
            active_later[0] if self.mode == "durable" and len(active_later) == 1 else None
        )
        for rel in (".ai/ACTIVE_MISSION.md", "README.md", "docs/WORKSPACE_BOOTSTRAP_STATUS.md"):
            text = self.read_text(rel)
            if text is None:
                self.err("mission", f"mission pointer file missing: {rel}")
            elif expected_active and expected_active not in text:
                self.err("mission", f"{rel} does not name active mission {expected_active}")
        self.counts["missions_synced"] = len(dag)

    # ---------- dev container shape ----------
    def check_devcontainer(self) -> None:
        text = self.read_text(DEVCONTAINER_REL)
        if text is None:
            self.err("devcontainer", f"missing {DEVCONTAINER_REL}")
            return
        try:
            config = json.loads(text)
        except json.JSONDecodeError as exc:
            self.err("devcontainer", f"{DEVCONTAINER_REL} is not valid JSON: {exc}")
            return
        if not isinstance(config, dict):
            self.err("devcontainer", "devcontainer.json must be a JSON object")
            return

        policy = self.read_json(POLICY_REL) or {}
        locked_digest = str((policy.get("base_image") or {}).get("digest") or BASE_IMAGE["digest"])

        # --- image: immutable digest pin and locked semantic coordinate ---
        image = str(config.get("image") or "")
        image_match = re.fullmatch(r"(?P<ref>[^@]+)@(?P<digest>sha256:[0-9a-f]{64})", image)
        if not image_match:
            self.err("devcontainer", "image must be a digest-pinned reference name:tag@sha256:<64hex>")
        else:
            ref, digest = image_match.group("ref"), image_match.group("digest")
            if not ref.endswith(f":{BASE_IMAGE['node_version']}"):
                self.err("devcontainer", f"image semantic coordinate must end with :{BASE_IMAGE['node_version']}, got {ref!r}")
            if digest != locked_digest:
                self.err("devcontainer", f"image digest {digest} != locked provenance digest {locked_digest}")
            if digest != BASE_IMAGE["digest"]:
                self.err("devcontainer", f"image digest disagrees with the accepted M-007 snapshot {BASE_IMAGE['digest']}")

        # --- users: non-root, exact in the active M-007 snapshot ---
        if self.mode == "active":
            for field in ("remoteUser", "containerUser"):
                if config.get(field) != "node":
                    self.err(
                        "devcontainer",
                        f"active M-007 requires {field} == 'node', got {config.get(field)!r}",
                    )
        else:
            # Durable: BOTH user fields must remain explicitly present and
            # non-root; removal/absence/empty would let execution fall back to
            # the base image's default root user and is permanently banned.
            # Changing either away from `node` requires a declaration owned by
            # the actually active later mission (exact values + rationale).
            declared_users = {
                "remoteUser": config.get("remoteUser"),
                "containerUser": config.get("containerUser"),
            }
            for field in ("remoteUser", "containerUser"):
                user = config.get(field)
                if (
                    user is None
                    or (isinstance(user, str) and not user.strip())
                    or str(user).strip() in {"root", "0"}
                ):
                    self.err(
                        "devcontainer",
                        f"durable {field} must be explicitly present and non-root, got {user!r}",
                    )
                elif user != "node" and not self._declared("users", declared_users):
                    self.err(
                        "devcontainer",
                        f"durable {field} change from 'node' requires a declaration "
                        f"owned by the active later mission",
                    )

        # --- permanent bans (both modes) ---
        if config.get("privileged") is True:
            self.err("devcontainer", "privileged: true is permanently forbidden")
        run_args = config.get("runArgs")
        if run_args is not None:
            if not isinstance(run_args, list):
                self.err("devcontainer", "runArgs must be an array")
            else:
                joined = " ".join(str(item) for item in run_args)
                if "--privileged" in joined:
                    self.err("devcontainer", "runArgs --privileged is permanently forbidden")
                if re.search(r"--network(?:=| )", joined):
                    self.err("devcontainer", "runArgs host/network override is permanently forbidden")
                if re.search(r"--cap-add|--security-opt", joined):
                    self.err("devcontainer", "runArgs capability/securityOpt weakening is permanently forbidden")
                if DOCKER_SOCKET_REF.search(joined) or HOST_CREDENTIAL_REF.search(joined) or "ssh-agent" in joined:
                    self.err("devcontainer", "runArgs must not mount docker socket, host credentials, or ssh-agent")
                if self.mode == "active":
                    if joined:
                        self.err("devcontainer", "active M-007 forbids any runArgs")
                elif run_args and not self._declared("run_args", run_args):
                    self.err(
                        "devcontainer",
                        "durable runArgs require a declaration owned by the active later mission",
                    )
        mounts = config.get("mounts")
        if mounts is not None:
            if not isinstance(mounts, list):
                self.err("devcontainer", "mounts must be an array")
            else:
                joined = " ".join(str(item) for item in mounts)
                if DOCKER_SOCKET_REF.search(joined):
                    self.err("devcontainer", "docker socket mount is permanently forbidden")
                if HOST_CREDENTIAL_REF.search(joined):
                    self.err("devcontainer", "host credential mounts are permanently forbidden")
                if "ssh-agent" in joined or "SSH_AUTH_SOCK" in joined:
                    self.err("devcontainer", "ssh-agent forwarding is permanently forbidden")
                if self.mode == "active":
                    # The active M-007 snapshot allows exactly the canonical
                    # node_modules volume; anything else (or its removal)
                    # fails so the CI bootstrap regression cannot return.
                    if mounts != [NODE_MODULES_VOLUME]:
                        self.err(
                            "devcontainer",
                            f"active M-007 requires exactly the node_modules volume, got {mounts}",
                        )
                else:
                    extras = [m for m in mounts if m != NODE_MODULES_VOLUME]
                    if extras and not self._declared("mounts", mounts):
                        self.err(
                            "devcontainer",
                            "durable mounts require a declaration owned by the active later mission",
                        )

        # --- environment fields: no raw secrets; active forbids entirely ---
        for field in ("containerEnv", "remoteEnv"):
            value = config.get(field)
            if value is None:
                continue
            if not isinstance(value, dict):
                self.err("devcontainer", f"{field} must be an object")
                continue
            if value and self.mode == "active":
                self.err("devcontainer", f"active M-007 forbids {field}")
            elif value and self.mode == "durable" and not self._declared(field, value):
                self.err("devcontainer", f"durable {field} requires a declaration owned by the active later mission")
            joined = json.dumps(value)
            for pattern in SECRET_PATTERNS:
                if re.search(pattern, joined):
                    self.err("devcontainer", f"{field} contains raw secret material")
                    break

        # --- forwarded ports ---
        ports = config.get("forwardPorts")
        if ports is not None and ports:
            if self.mode == "active":
                self.err("devcontainer", "active M-007 forbids forwarded ports")
            elif not self._declared("forwarded_ports", ports):
                self.err("devcontainer", "durable forwarded ports require a declaration owned by the active later mission")

        # --- product services / second descriptor ---
        if config.get("dockerComposeFile") is not None:
            if self.mode == "active":
                self.err("devcontainer", "active M-007 forbids dockerComposeFile (product services)")
            elif not self._declared("docker_compose", True):
                self.err("devcontainer", "durable dockerComposeFile requires a declaration owned by the active later mission")
        if (self.root / ".devcontainer/Dockerfile").is_file():
            if self.mode == "active":
                self.err("devcontainer", "active M-007 forbids a .devcontainer/Dockerfile")
            elif not self._declared("dockerfile", True):
                self.err("devcontainer", "durable Dockerfile requires a declaration owned by the active later mission")
        if (self.root / ".devcontainer/docker-compose.yml").is_file() and self.mode == "active":
            self.err("devcontainer", "active M-007 forbids a .devcontainer/docker-compose.yml")

        # --- features: digest-pinned and registered ---
        features = config.get("features")
        if features is None:
            features = {}
        if not isinstance(features, dict):
            self.err("devcontainer", "features must be an object")
            features = {}
        feature_refs = [str(key) for key in features]
        locked_feature_refs = {
            self._feature_ref(entry) for entry in (policy.get("features") or []) if isinstance(entry, dict)
        }
        for ref in feature_refs:
            match = re.fullmatch(r"([^@]+)@sha256:[0-9a-f]{64}", ref)
            if not match:
                self.err("devcontainer", f"feature {ref!r} must be digest-pinned (ref@sha256:<64hex>)")
                continue
            if ref not in locked_feature_refs:
                self.err("devcontainer", f"feature {ref!r} is not registered in the dev-environment policy lock")
        if self.mode == "active":
            if set(feature_refs) != locked_feature_refs:
                self.err(
                    "devcontainer",
                    f"active feature set must equal the lock registration {sorted(locked_feature_refs)}, got {sorted(feature_refs)}",
                )
        else:
            # Durable: the M-007 python feature is retained; additional
            # features must be registered in the policy/provenance structure
            # AND owned by the active later mission or an already-completed
            # later mission (historical extensions remain). An unrelated or
            # future mission authorizes nothing.
            python_ref = PYTHON_FEATURE["digest_reference"]
            if python_ref not in feature_refs:
                self.err("devcontainer", "durable mode must retain the M-007 python feature")
            for ref in feature_refs:
                if ref == python_ref:
                    continue
                if not self._feature_owned(ref):
                    self.err(
                        "devcontainer",
                        f"durable feature {ref!r} requires an owning extension from the "
                        f"active or a completed later mission",
                    )

        # --- committed env examples: no raw secrets ---
        for path in sorted(self.root.rglob(".env*")):
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="replace")
                for pattern in SECRET_PATTERNS:
                    if re.search(pattern, content):
                        self.err("devcontainer", f"committed env example {path.relative_to(self.root)} contains raw secret material")
                        break

        self.counts["devcontainer_features"] = len(feature_refs)

    def _feature_ref(self, entry: dict) -> str:
        return str(entry.get("digest_reference") or "")

    def _declared(self, kind: str, value: object) -> bool:
        """True only if a durable extension entry declares `kind == value` AND
        is owned by the actually active later mission (explicit mission_id)."""
        if self.mode != "durable" or not self.active_later_mission:
            return False
        policy = self.read_json(POLICY_REL) or {}
        for entry in policy.get("durable_extension_policy", {}).get("extensions") or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("mission_id") or "") != self.active_later_mission:
                continue
            if not str(entry.get("rationale") or "").strip():
                continue
            declared = entry.get("declared", {})
            if not isinstance(declared, dict):
                continue
            for key, expected in declared.items():
                if key != kind:
                    continue
                if isinstance(value, (dict, list)) and isinstance(expected, (dict, list)):
                    if json.dumps(expected, sort_keys=True) == json.dumps(value, sort_keys=True):
                        return True
                elif expected == value:
                    return True
        return False

    def _feature_owned(self, ref: str) -> bool:
        """Durable: True if a durable extension entry (owned by the active
        later mission or by an already-completed later mission, with rationale)
        declares this digest-pinned feature ref."""
        if self.mode != "durable" or not self.active_later_mission:
            return False
        owners = {self.active_later_mission} | self.completed_later_missions
        policy = self.read_json(POLICY_REL) or {}
        for entry in policy.get("durable_extension_policy", {}).get("extensions") or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("mission_id") or "") not in owners:
                continue
            if not str(entry.get("rationale") or "").strip():
                continue
            declared = entry.get("declared", {})
            if not isinstance(declared, dict):
                continue
            declared_refs = declared.get("features")
            if isinstance(declared_refs, list) and ref in [str(item) for item in declared_refs]:
                return True
        return False

    # ---------- provenance / policy lock ----------
    def check_policy_lock(self) -> None:
        policy = self.read_json(POLICY_REL)
        if policy is None:
            self.err("policy", f"missing {POLICY_REL}")
            return
        if policy.get("schema_version") != 1:
            self.err("policy", "policy lock schema_version must be 1")
        if policy.get("adopted_environment_descriptor") != "devcontainers":
            self.err("policy", "Dev Containers must remain the adopted descriptor")
        base = policy.get("base_image") or {}
        if base.get("semantic_reference") != BASE_IMAGE["semantic_reference"]:
            self.err("policy", "policy base image coordinate disagrees with M-007 snapshot")
        if base.get("digest") != BASE_IMAGE["digest"]:
            self.err("policy", "policy base image digest disagrees with M-007 snapshot")
        arches = base.get("architectures") or {}
        for arch in ("amd64", "arm64"):
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(arches.get(arch) or "")):
                self.err("policy", f"policy base image missing valid {arch} digest")
        if not str(base.get("upstream_source") or "").startswith("https://"):
            self.err("policy", "policy base image source must be recorded")
        if not str(base.get("project_license") or "").strip():
            self.err("policy", "policy base image license must be recorded")

        features = policy.get("features") or []
        if not isinstance(features, list) or not features:
            self.err("policy", "policy lock must register the M-007 python feature")
        else:
            python_entries = [
                entry for entry in features
                if isinstance(entry, dict)
                and entry.get("digest_reference") == PYTHON_FEATURE["digest_reference"]
            ]
            if not python_entries:
                self.err("policy", "policy lock must retain the M-007 python feature")
            for entry in features:
                if not isinstance(entry, dict):
                    self.err("policy", "feature registration must be an object")
                    continue
                if entry.get("digest_reference") == PYTHON_FEATURE["digest_reference"]:
                    if entry.get("id") != PYTHON_FEATURE["id"] or entry.get("version") != PYTHON_FEATURE["version"]:
                        self.err("policy", "python feature registration disagrees with M-007 snapshot")
                    if entry.get("digest_reference") != PYTHON_FEATURE["digest_reference"]:
                        self.err("policy", "python feature digest disagrees with M-007 snapshot")
                    if not str(entry.get("upstream_source") or "").startswith("https://"):
                        self.err("policy", "python feature source must be recorded")
                    if not str(entry.get("project_license") or "").strip():
                        self.err("policy", "python feature license must be recorded")
                else:
                    ref = str(entry.get("digest_reference") or "")
                    if not re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", ref):
                        self.err("policy", f"additional feature {ref!r} must be digest-pinned")
                    if not str(entry.get("upstream_source") or "").startswith("https://"):
                        self.err("policy", f"additional feature {ref!r} source must be recorded")
                    if not str(entry.get("project_license") or "").strip():
                        self.err("policy", f"additional feature {ref!r} license must be recorded")
            if self.mode == "active" and len(features) != 1:
                self.err(
                    "policy",
                    f"active M-007 policy registry must register exactly the python feature, got {len(features)}",
                )
            if self.mode == "durable":
                for entry in features:
                    if not isinstance(entry, dict):
                        continue
                    ref = str(entry.get("digest_reference") or "")
                    if ref == PYTHON_FEATURE["digest_reference"]:
                        continue
                    if not self._feature_owned(ref):
                        self.err(
                            "policy",
                            f"policy feature {ref!r} requires an owning extension from the "
                            f"active or a completed later mission",
                        )

        toolchain = policy.get("toolchain") or {}
        for name, expected in TOOLCHAIN.items():
            if str(toolchain.get(name) or "") != expected:
                self.err("policy", f"policy toolchain {name} must be {expected}, got {toolchain.get(name)!r}")
        for required in ("corepack", "python3", "git"):
            if str(toolchain.get(required) or "").strip() in {"", "false"}:
                self.err("policy", f"policy toolchain must require {required}")

        bootstrap = policy.get("bootstrap") or {}
        if bootstrap.get("frozen_lockfile") is not True:
            self.err("policy", "policy bootstrap must require frozen-lockfile installation")
        for command in ("command", "doctor", "runtime_smoke", "static_validator"):
            if not str(bootstrap.get(command) or "").strip():
                self.err("policy", f"policy bootstrap missing {command}")

        posture = policy.get("security_posture") or {}
        for key, expected in (
            ("non_root_user", "node"),
            ("privileged", False),
            ("host_network", False),
            ("docker_socket_mount", False),
            ("docker_in_docker", False),
            ("host_credential_mounts", False),
            ("raw_secrets_in_env_or_committed_examples", False),
            ("ssh_agent_or_cloud_credential_forwarding", False),
        ):
            if posture.get(key) != expected:
                self.err("policy", f"policy security_posture {key} must be {expected!r}")
        for key in ("extra_capabilities", "security_opt", "forwarded_ports", "product_services"):
            if posture.get(key) not in (None, []):
                self.err("policy", f"policy security_posture {key} must be empty in the M-007 baseline")
        posture_mounts = posture.get("mounts")
        if not isinstance(posture_mounts, list) or not any(
            isinstance(item, dict) and item.get("entry") == NODE_MODULES_VOLUME
            for item in posture_mounts
        ):
            self.err("policy", "policy security_posture must document the canonical node_modules volume")

        extensions = (policy.get("durable_extension_policy") or {}).get("extensions") or []
        if not isinstance(extensions, list):
            self.err("policy", "durable_extension_policy.extensions must be a list")
        else:
            if self.mode == "active" and extensions:
                self.err("policy", "active M-007 snapshot requires zero durable extensions")
            for entry in extensions:
                if not isinstance(entry, dict):
                    self.err("policy", "extension entries must be objects")
                    continue
                if not re.fullmatch(r"M-\d{3}", str(entry.get("mission_id") or "")):
                    self.err("policy", f"extension entry needs owning mission_id: {entry}")
                if not str(entry.get("rationale") or "").strip():
                    self.err("policy", f"extension entry {entry.get('mission_id')} needs a rationale")
        self.counts["policy_extensions"] = len(extensions)

    # ---------- repository scripts ----------
    def check_scripts(self) -> None:
        for rel in DEV_SCRIPTS:
            text = self.read_text(rel)
            if text is None:
                self.err("scripts", f"missing {rel}")
                continue
            first = text.splitlines()[0] if text.splitlines() else ""
            if "python3" not in first and "python" not in first:
                self.err("scripts", f"{rel} must be a python3 script (shebang)")
            self._check_python_subprocess(rel, text)
        bootstrap = self.read_text("scripts/dev-bootstrap.py") or ""
        if "--frozen-lockfile" not in bootstrap:
            self.err("scripts", "dev-bootstrap.py must run pnpm install --frozen-lockfile")
        for bypass in ("--no-frozen-lockfile", "pnpm install -f", "pnpm install --force", "pnpm install --lockfile-only"):
            if bypass in bootstrap:
                self.err("scripts", f"dev-bootstrap.py must not bypass the lockfile via {bypass!r}")
        smoke = self.read_text("scripts/dev-runtime-smoke.py") or ""
        for expected in ("v24.19.0", "11.4.0", "python3", "git"):
            if expected not in smoke:
                self.err("scripts", f"dev-runtime-smoke.py must verify {expected}")
        self.counts["dev_scripts"] = len(DEV_SCRIPTS)

    def _check_python_subprocess(self, rel: str, text: str) -> None:
        """AST-level check: subprocess calls must use explicit argv, never
        shell=True / string-shell execution; os.system/os.popen are forbidden."""
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            self.err("scripts", f"{rel} is not valid python3: {exc}")
            return
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "os" and func.attr in {"system", "popen"}:
                    self.err("scripts", f"{rel} must not use os.{func.attr} (explicit argv subprocess only)")
                if func.value.id == "subprocess" and func.attr in {"run", "Popen", "call", "check_call", "check_output"}:
                    for keyword in node.keywords:
                        if keyword.arg == "shell":
                            value = keyword.value
                            if isinstance(value, ast.Constant) and value.value is False:
                                continue
                            self.err("scripts", f"{rel} must not use subprocess shell=True")
                    if node.args:
                        first = node.args[0]
                        if isinstance(first, ast.Constant) and isinstance(first.value, str):
                            self.err(
                                "scripts",
                                f"{rel} must pass explicit argv lists to subprocess, not a command string",
                            )

    # ---------- root package / toolchain agreement ----------
    def check_root_package(self) -> None:
        package = self.read_json("package.json")
        if package is None:
            self.err("root", "missing package.json")
            return
        scripts = package.get("scripts") or {}
        expected_scripts = {
            "dev:doctor": "python3 scripts/dev-doctor.py",
            "dev:bootstrap": "python3 scripts/dev-bootstrap.py",
            "dev:validate": "python3 scripts/validate-m007-local-dev.py",
        }
        for name, command in expected_scripts.items():
            if scripts.get(name) != command:
                self.err("root", f"root script {name!r} must be {command!r}")
        check = str(scripts.get("check") or "")
        stages = [stage.strip() for stage in check.split("&&") if stage.strip()]
        if "pnpm run dev:validate" not in stages:
            self.err("root", "root check must include the pnpm run dev:validate stage")
        if not stages or stages[0] != "python3 scripts/validate-m004-foundation.py":
            self.err("root", "M-004 foundation validator must remain the first check stage")
        nvmrc = self.root / ".nvmrc"
        if not nvmrc.is_file() or nvmrc.read_text(encoding="utf-8").strip() != "24.19.0":
            self.err("root", ".nvmrc must pin 24.19.0")
        engines = package.get("engines") or {}
        if engines.get("node") != "24.x" or engines.get("pnpm") != "11.4.0":
            self.err("root", "engines must remain node 24.x / pnpm 11.4.0")
        if package.get("packageManager") != "pnpm@11.4.0":
            self.err("root", "packageManager must remain pnpm@11.4.0")

    # ---------- capability ledger ----------
    def check_capabilities(self) -> None:
        csv_path = self.root / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv"
        yaml_path = self.root / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml"
        if not csv_path.is_file() or not yaml_path.is_file():
            self.err("capability", "capability ledger CSV/YAML must exist")
            return
        with csv_path.open(newline="", encoding="utf-8") as handle:
            csv_rows = list(csv.DictReader(handle))
        csv_statuses = {row["vf_id"]: row["status"] for row in csv_rows}
        yaml_text = yaml_path.read_text(encoding="utf-8")
        yaml_statuses: dict[str, str] = {}
        current: str | None = None
        for line in yaml_text.splitlines():
            match = re.match(r"^- vf_id: (\S+)$", line)
            if match:
                current = match.group(1)
            elif current and (match := re.match(r"^  status: ([A-Z_]+)$", line)):
                yaml_statuses[current] = match.group(1)
                current = None
        for vf_id in sorted(set(csv_statuses) | set(yaml_statuses)):
            if csv_statuses.get(vf_id) != yaml_statuses.get(vf_id):
                self.err("capability", f"{vf_id} status disagrees between CSV and YAML")
        if len(csv_statuses) != len(CAPABILITY_SNAPSHOT):
            self.err("capability", f"capability count {len(csv_statuses)} != M-007 snapshot {len(CAPABILITY_SNAPSHOT)}")

        if self.mode == "active":
            for vf_id, expected in CAPABILITY_SNAPSHOT.items():
                actual = csv_statuses.get(vf_id)
                if actual != expected:
                    self.err("capability", f"active M-007 requires {vf_id}={expected}, got {actual!r}")
        else:
            for vf_id, expected in REL_M006_BASELINE.items():
                actual = csv_statuses.get(vf_id)
                if actual in STATUS_RANK and STATUS_RANK[actual] < STATUS_RANK[expected]:
                    self.err("capability", f"durable {vf_id} regressed below M-006 baseline {expected} to {actual}")
            actual_env = csv_statuses.get("VF-ENV-005")
            if actual_env in STATUS_RANK and STATUS_RANK[actual_env] < STATUS_RANK["IN_PROGRESS"]:
                self.err("capability", f"durable VF-ENV-005 regressed below IN_PROGRESS to {actual_env}")
        self.counts["capabilities"] = len(csv_statuses)

    # ---------- CI wrappers ----------
    def check_ci_wrappers(self) -> None:
        wrapper_scripts = (
            "scripts/security/scan-dev-image.sh",
            "scripts/security/generate-dev-image-sbom.sh",
        )
        for rel in wrapper_scripts:
            path = self.root / rel
            if not path.is_file():
                self.err("ci", f"missing {rel}")
                continue
            if not os.access(path, os.X_OK):
                self.err("ci", f"{rel} must be executable (fresh checkout invokes it directly)")
        scan = self.read_text("scripts/security/scan-dev-image.sh") or ""
        for snippet in ("--scanners vuln,misconfig", "--severity HIGH,CRITICAL", "--ignore-unfixed", "--exit-code 1"):
            if snippet not in scan:
                self.err("ci", f"scan-dev-image.sh missing required policy argument {snippet!r}")
        sbom = self.read_text("scripts/security/generate-dev-image-sbom.sh") or ""
        for snippet in ("--format cyclonedx", "sha256sum"):
            if snippet not in sbom:
                self.err("ci", f"generate-dev-image-sbom.sh missing required policy argument {snippet!r}")
        if "install-ci-tool.py" not in (scan + sbom):
            self.err("ci", "dev-image wrappers must use the locked Trivy toolchain path")
        self.counts["ci_wrappers"] = len(wrapper_scripts)

    # ---------- evidence and CI readiness ----------
    def check_evidence(self) -> None:
        if not (self.root / EVIDENCE_MD_REL).is_file():
            self.err("evidence", f"missing {EVIDENCE_MD_REL}")
        evidence = self.read_json(EVIDENCE_JSON_REL)
        if evidence is None:
            self.err("evidence", f"missing or invalid {EVIDENCE_JSON_REL}")
        else:
            for key in ("mission", "mission_status", "starting_main_sha", "branch", "base_image", "features", "toolchain", "capability_status", "adr_required"):
                if key not in evidence:
                    self.err("evidence", f"{EVIDENCE_JSON_REL} missing key {key!r}")
        if self.mode == "active":
            patch = self.read_text(INTENDED_WORKFLOWS_REL)
            if patch is None:
                self.err("evidence", f"active M-007 requires {INTENDED_WORKFLOWS_REL}")
            else:
                # The patch is the exact correction delta from the current
                # workflow state: it must remove the defective imageName and
                # pin the fixed coordinate plus the resulting local tag.
                required_patch_content = (
                    "devcontainers/ci@513af61f4de4f75d37e4438f184ba4358f0fc1ca",
                    "imageName: vibeflow-dev:smoke",
                    "imageName: vibeflow-dev",
                    "vibeflow-dev:latest",
                    "scripts/dev-runtime-smoke.py",
                    "scripts/security/scan-dev-image.sh",
                    "scripts/security/generate-dev-image-sbom.sh",
                )
                for snippet in required_patch_content:
                    if snippet not in patch:
                        self.err("evidence", f"INTENDED_WORKFLOWS.patch missing {snippet!r}")
            # Actual workflow files (applied by GPT through the
            # workflow-authorized connector) must carry the stable M-007 CI
            # evidence that is not part of the pending imageName correction.
            # Arena cannot write workflows, so the corrected imageName itself
            # is required only inside INTENDED_WORKFLOWS.patch until applied.
            workflow_evidence = {
                ".github/workflows/master-build-system-integrity.yml": (
                    "scripts/validate-m007-local-dev.py",
                    "tests/contract/test_m007_local_dev.py",
                ),
                ".github/workflows/repository-foundation.yml": (
                    "docker pull docker.io/library/node@sha256:934240a162082fd8b8a2f90cd5114446443f1eba1c5378f6687167ca405e6584",
                    "scripts/dev-runtime-smoke.py",
                    "imageName: vibeflow-dev",
                ),
                ".github/workflows/security-and-dependency-gates.yml": (
                    "docker pull docker.io/library/node@sha256:934240a162082fd8b8a2f90cd5114446443f1eba1c5378f6687167ca405e6584",
                    "scripts/security/scan-dev-image.sh",
                    "scripts/security/generate-dev-image-sbom.sh",
                    "vibeflow-dev-image-cyclonedx",
                    "imageName: vibeflow-dev",
                    "vibeflow-dev:latest",
                ),
            }
            for rel, snippets in workflow_evidence.items():
                text = self.read_text(rel)
                if text is None:
                    self.err("evidence", f"missing workflow {rel}")
                    continue
                for snippet in snippets:
                    if snippet not in text:
                        self.err("evidence", f"workflow {rel} missing {snippet!r}")
        lock = self.read_json("security/ci-toolchain.lock.json") or {}
        actions = lock.get("github_actions") or {}
        entry = actions.get(DEVCONTAINERS_CI_ACTION)
        if self.mode == "active":
            if not isinstance(entry, dict):
                self.err("evidence", "M-007 active requires devcontainers/ci registered in the CI action lock")
            else:
                if entry.get("commit_sha") != DEVCONTAINERS_CI_PIN or entry.get("version") != DEVCONTAINERS_CI_VERSION:
                    self.err("evidence", "devcontainers/ci action lock disagrees with the intended M-007 pin")
        self.counts["evidence_files"] = 3

    # ---------- master pack hash integrity ----------
    def check_master_hashes(self) -> None:
        mbs = self.root / "master-build-system"
        sums = mbs / "SHA256SUMS.txt"
        if not sums.is_file():
            self.err("hash", "missing master-build-system/SHA256SUMS.txt")
            return
        completed = subprocess.run(
            ["sha256sum", "-c", "SHA256SUMS.txt"],
            cwd=str(mbs),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            self.err("hash", f"master pack hash drift: sha256sum -c failed ({len(detail)} mismatch lines)")
        self.counts["master_hashes"] = len(sums.read_text(encoding="utf-8").splitlines())

    def run(self) -> dict:
        self.check_mission_progression()
        self.check_devcontainer()
        self.check_policy_lock()
        self.check_scripts()
        self.check_root_package()
        self.check_capabilities()
        self.check_ci_wrappers()
        self.check_evidence()
        self.check_master_hashes()
        return {
            "result": "FAIL" if self.errors else "PASS",
            "errors": self.errors,
            "counts": self.counts,
            "mode": self.mode,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--mode", choices=("auto", "active", "durable"), default="auto")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        dag, register = parse_statuses(root)
        m007 = str(dag.get(M007) or "")
        if args.mode != "auto":
            mode = args.mode
        elif m007 in {"READY", "IN_PROGRESS", "REVIEW"}:
            mode = "active"
        elif m007 == "DONE":
            mode = "durable"
        else:
            raise ValueError(f"cannot auto-select mode for M-007 status {m007!r}")
        result = Validator(root, mode).run()
    except Exception as exc:  # noqa: BLE001 — fail closed on malformed policy
        result = {"result": "FAIL", "errors": [f"validator exception: {type(exc).__name__}: {exc}"], "counts": {}, "mode": "unknown"}
    print("M-007 local development environment validator")
    print(f"  mode: {result['mode']}")
    for key, value in sorted(result["counts"].items()):
        print(f"  {key}: {value}")
    if result["errors"]:
        print("Errors:")
        for error in result["errors"]:
            print(f"  - {error}")
    print(f"RESULT: {result['result']}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
