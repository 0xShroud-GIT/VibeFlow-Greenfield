#!/usr/bin/env python3
"""M-004 Foundation validator — stdlib only.

Deterministically inspects the repository and fails for foundation contract violations.

Checks A-W as defined in M-004 mission packet:
A. exact Node pin / supported 24.x engine
B. exact packageManager pnpm@11.4.0
C. exact approved external dependency pins
D. no dependency ranges (^, ~, latest)
E. no arbitrary git/http/file external dependency sources
F. only approved M-004 dependencies
G. exactly one pnpm lockfile
H. no npm/yarn/bun lockfiles
I. required workspace globs exist
J. no package.json files under apps/services/workers/adapters
K. exactly seven M-004 shared package manifests
L. expected @vibeflow/* names
M. all shared packages are private, 0.0.0 and ESM
N. TypeBox uses `typebox` 1.x, never @sinclair/typebox
O. mandatory TypeScript strict flags
P. no VibeFlow package lifecycle scripts
Q. no dangerouslyAllowAllBuilds
R. release-age policy remains enabled
S. trustLockfile is not true
T. no obvious workspace dependency cycles
U. M-004 mission progression remains coherent
V. M-005 remains LOCKED
W. foundation CI workflow exists
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def get_repo_root() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", type=str, default=None)
    args, _ = parser.parse_known_args()
    if args.root:
        return Path(args.root).resolve()
    return REPO_ROOT

# Approved exact pins for M-004
APPROVED_DEPS = {
    "typescript": "6.0.3",
    "turbo": "2.10.6",
    "vitest": "4.1.7",
    "typebox": "1.3.6",
}

# Only these external dependencies are allowed as direct dependencies at M-004
ALLOWED_EXTERNAL_DEPS = set(APPROVED_DEPS.keys())

EXPECTED_WORKSPACE_GLOBS = [
    "apps/*",
    "services/*",
    "workers/*",
    "packages/*",
    "adapters/*",
]

EXPECTED_PACKAGES = {
    "core": "@vibeflow/core",
    "contracts": "@vibeflow/contracts",
    "remote": "@vibeflow/remote",
    "bridge": "@vibeflow/bridge",
    "provider-sdk": "@vibeflow/provider-sdk",
    "verification": "@vibeflow/verification",
    "ui": "@vibeflow/ui",
}

STRICT_FLAGS = {
    "strict": True,
    "noUncheckedIndexedAccess": True,
    "exactOptionalPropertyTypes": True,
    "noImplicitOverride": True,
    "noFallthroughCasesInSwitch": True,
    "useUnknownInCatchVariables": True,
    "forceConsistentCasingInFileNames": True,
}

FORBIDDEN_LIFECYCLE_SCRIPTS = {"preinstall", "install", "postinstall", "prepare"}

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, str(e)

def parse_npmrc(path: Path):
    data = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            k,v = line.split("=",1)
            data[k.strip()] = v.strip()
        elif ":" in line:
            k,v = line.split(":",1)
            data[k.strip()] = v.strip()
    return data

def check_file_exists(path: Path, errors: list[str]):
    if not path.is_file():
        errors.append(f"Missing required file: {path.relative_to(REPO_ROOT)}")
        return False
    return True

def main() -> int:
    global REPO_ROOT
    REPO_ROOT = get_repo_root()
    errors: list[str] = []
    warnings: list[str] = []

    # ---- Load root package.json ----
    root_pkg_path = REPO_ROOT / "package.json"
    if check_file_exists(root_pkg_path, errors):
        root_pkg = json.loads(root_pkg_path.read_text(encoding="utf-8"))
    else:
        root_pkg = {}

    # A. exact Node pin / supported 24.x engine
    nvmrc_path = REPO_ROOT / ".nvmrc"
    if not nvmrc_path.is_file():
        errors.append("A: Missing .nvmrc (expected 24.19.0)")
    else:
        nvmrc = nvmrc_path.read_text(encoding="utf-8").strip()
        if nvmrc != "24.19.0":
            errors.append(f"A: Wrong Node pin in .nvmrc: expected '24.19.0', got '{nvmrc}'")

    # Check engines.node
    engines = root_pkg.get("engines", {}) if isinstance(root_pkg, dict) else {}
    node_engine = engines.get("node", "")
    if node_engine != "24.x":
        errors.append(f"A: Wrong engines.node: expected '24.x', got '{node_engine}'")
    pnpm_engine = engines.get("pnpm", "")
    if pnpm_engine != "11.4.0":
        errors.append(f"A: Wrong engines.pnpm: expected '11.4.0', got '{pnpm_engine}'")

    # B. exact packageManager pnpm@11.4.0
    pkg_manager = root_pkg.get("packageManager", "")
    if pkg_manager != "pnpm@11.4.0":
        errors.append(f"B: Wrong packageManager: expected 'pnpm@11.4.0', got '{pkg_manager}'")

    # Check root private, type module
    if root_pkg.get("private") is not True:
        errors.append("Root package.json must have \"private\": true")
    if root_pkg.get("type") != "module":
        errors.append("Root package.json must have \"type\": \"module\" for ESM")

    # Collect all dependencies for checks C/D/E/F/N/P
    # Root devDependencies
    root_dev_deps = root_pkg.get("devDependencies", {}) or {}
    root_deps = root_pkg.get("dependencies", {}) or {}
    all_root_deps = {**root_deps, **root_dev_deps}

    # Check C: exact approved external dependency pins
    # Approved pins must match exactly
    for dep, expected in [("typescript","6.0.3"), ("turbo","2.10.6"), ("vitest","4.1.7")]:
        actual = root_dev_deps.get(dep)
        if actual is None:
            errors.append(f"C: Missing required devDependency '{dep}' with pin '{expected}'")
        elif actual != expected:
            errors.append(f"C: Wrong pin for '{dep}': expected '{expected}', got '{actual}'")

    # Check contracts typebox
    contracts_pkg_path = REPO_ROOT / "packages" / "contracts" / "package.json"
    if contracts_pkg_path.is_file():
        contracts_pkg = json.loads(contracts_pkg_path.read_text(encoding="utf-8"))
        c_deps = contracts_pkg.get("dependencies", {}) or {}
        c_dev_deps = contracts_pkg.get("devDependencies", {}) or {}
        c_all = {**c_deps, **c_dev_deps}
        actual = c_all.get("typebox")
        if actual != "1.3.6":
            errors.append(f"C: Wrong pin for 'typebox' in packages/contracts: expected '1.3.6', got '{actual}'")
    else:
        errors.append("C: Missing packages/contracts/package.json for typebox check")
        c_all = {}

    # D. no dependency ranges (^, ~, latest)
    # Check all package.json files
    def check_no_ranges(deps: dict, location: str):
        for name, ver in deps.items():
            if not isinstance(ver, str):
                continue
            if ver.strip() == "":
                continue
            if ver.startswith("^") or ver.startswith("~"):
                errors.append(f"D: Dependency range forbidden for '{name}' in {location}: '{ver}' (no ^ or ~)")
            if ver == "latest" or ver.startswith("latest"):
                errors.append(f"D: Dependency 'latest' forbidden for '{name}' in {location}: '{ver}'")
            if "*" in ver:
                # allow workspace:*? but we forbid general *
                if ver != "*" and "workspace:" not in ver:
                    # Check if version contains * not as workspace
                    # For M-004 we forbid ranges like "1.x" is allowed? But spec says no ^,~ latest. We treat * as range too
                    if "*" in ver:
                        # But workspace:* is not considered range failure for D, but should be checked elsewhere
                        # We'll only flag if not workspace
                        if "workspace" not in ver:
                            errors.append(f"D: Dependency range forbidden for '{name}' in {location}: '{ver}' (no *)")
            # Also check npm dist-tag like "next" or "beta" without pin - treat as range? We'll consider if version contains non-exact semver like "x"
            # But we only enforce ^ ~ latest * for now per spec

    check_no_ranges(all_root_deps, "root package.json")
    # Check all packages
    for pkg_dir in EXPECTED_PACKAGES.keys():
        ppath = REPO_ROOT / "packages" / pkg_dir / "package.json"
        if ppath.is_file():
            data = json.loads(ppath.read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            check_no_ranges(deps, f"packages/{pkg_dir}/package.json")

    # E. no arbitrary git/http/file external dependency sources
    def check_no_exotic(deps: dict, location: str):
        for name, ver in deps.items():
            if not isinstance(ver, str):
                continue
            lower = ver.lower()
            if lower.startswith("git+") or "github:" in lower or lower.startswith("git://"):
                errors.append(f"E: Git URL dependency forbidden for '{name}' in {location}: '{ver}'")
            if lower.startswith("http://") or lower.startswith("https://"):
                errors.append(f"E: HTTP URL dependency forbidden for '{name}' in {location}: '{ver}'")
            if lower.startswith("file:") or lower.startswith("link:"):
                errors.append(f"E: File/link dependency forbidden for '{name}' in {location}: '{ver}'")
            # workspace: is allowed only for internal but M-004 should avoid
            # We don't fail on workspace: here, but will be handled in T

    check_no_exotic(all_root_deps, "root package.json")
    for pkg_dir in EXPECTED_PACKAGES.keys():
        ppath = REPO_ROOT / "packages" / pkg_dir / "package.json"
        if ppath.is_file():
            data = json.loads(ppath.read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            check_no_exotic(deps, f"packages/{pkg_dir}/package.json")

    # F. only approved M-004 dependencies
    # Root should only have typescript, turbo, vitest as direct deps (allow also maybe other internal? but spec says only approved)
    allowed_root = {"typescript", "turbo", "vitest"}
    for dep in all_root_deps.keys():
        # Check if dep is internal @vibeflow/* with workspace: — currently none, but if present would be considered internal and we should allow? But spec says avoid unnecessary internal deps
        if dep.startswith("@vibeflow/"):
            # workspace internal - flag as unnecessary at M-004? For F we consider it not allowed unless needed
            errors.append(f"F: Unapproved external dependency '{dep}' in root package.json (only {sorted(allowed_root)} and typebox in contracts are allowed)")
        elif dep not in allowed_root:
            # Allow typebox only in contracts, not root
            if dep == "typebox":
                errors.append(f"F: Unapproved external dependency 'typebox' in root package.json (only packages/contracts should need TypeBox)")
            else:
                errors.append(f"F: Unapproved external dependency '{dep}' in root package.json: '{dep}' not in approved M-004 set {sorted(allowed_root)}")

    # Check contracts allowed deps: only typebox
    if contracts_pkg_path.is_file():
        contracts_pkg = json.loads(contracts_pkg_path.read_text(encoding="utf-8"))
        c_deps = {**(contracts_pkg.get("dependencies") or {}), **(contracts_pkg.get("devDependencies") or {})}
        for dep in c_deps.keys():
            if dep != "typebox":
                errors.append(f"F: Unapproved external dependency '{dep}' in packages/contracts (only typebox@1.3.6 is allowed)")

    # Check other packages should have no dependencies (since M-004 shells have no product behavior)
    for pkg_dir in EXPECTED_PACKAGES.keys():
        if pkg_dir == "contracts":
            continue
        ppath = REPO_ROOT / "packages" / pkg_dir / "package.json"
        if ppath.is_file():
            data = json.loads(ppath.read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            # Filter peerDependencies? not expected
            if deps:
                for dep in deps.keys():
                    errors.append(f"F: Unapproved external dependency '{dep}' in packages/{pkg_dir}/package.json (M-004 shells must have no external dependencies except contracts->typebox)")

    # G. exactly one pnpm lockfile
    pnpm_lock_root = REPO_ROOT / "pnpm-lock.yaml"
    if not pnpm_lock_root.is_file():
        errors.append("G: Missing required pnpm-lock.yaml at repository root")
    # Check nested pnpm-lock.yaml
    nested = list(REPO_ROOT.rglob("pnpm-lock.yaml"))
    # Filter out root
    nested_filtered = [p for p in nested if p.resolve() != pnpm_lock_root.resolve()]
    if nested_filtered:
        for p in nested_filtered:
            rel = p.relative_to(REPO_ROOT)
            errors.append(f"G: Nested pnpm-lock.yaml forbidden: {rel}")
    # Also check exactly one - if multiple, already flagged; if zero flagged above

    # H. no npm/yarn/bun lockfiles
    forbidden_lockfiles = ["package-lock.json", "yarn.lock", "bun.lock", "bun.lockb"]
    for name in forbidden_lockfiles:
        for found in REPO_ROOT.rglob(name):
            # Ignore .git and node_modules? But spec says reject any such lockfiles at repo level? We'll check anywhere not in .git/node_modules? For simplicity, check root and any not in node_modules/.git
            # Skip node_modules/.git paths
            parts = found.relative_to(REPO_ROOT).parts
            if "node_modules" in parts or ".git" in parts:
                continue
            errors.append(f"H: Forbidden lockfile present: {found.relative_to(REPO_ROOT)}")

    # I. required workspace globs exist
    ws_path = REPO_ROOT / "pnpm-workspace.yaml"
    if not ws_path.is_file():
        errors.append("I: Missing pnpm-workspace.yaml")
    else:
        text = ws_path.read_text(encoding="utf-8")
        for glob in EXPECTED_WORKSPACE_GLOBS:
            # Simple check: glob string appears
            if glob not in text:
                errors.append(f"I: Missing required workspace glob '{glob}' in pnpm-workspace.yaml")
        # Check that only those globs? We require exactly reservation but not necessarily exclusive; but we check that expected ones exist
        # Also validate packages key exists
        if "packages:" not in text:
            errors.append("I: pnpm-workspace.yaml missing 'packages:' key")

    # J. no package.json files under apps/services/workers/adapters
    for prefix in ["apps", "services", "workers", "adapters"]:
        base = REPO_ROOT / prefix
        if base.is_dir():
            for found in base.rglob("package.json"):
                parts = found.relative_to(REPO_ROOT).parts
                if "node_modules" in parts:
                    continue
                errors.append(f"J: Forbidden package.json under {prefix}: {found.relative_to(REPO_ROOT)}")

    # K. exactly seven M-004 shared package manifests
    found_packages = []
    for pkg_dir in EXPECTED_PACKAGES.keys():
        ppath = REPO_ROOT / "packages" / pkg_dir / "package.json"
        if ppath.is_file():
            found_packages.append(pkg_dir)
        else:
            errors.append(f"K: Missing shared package manifest: packages/{pkg_dir}/package.json")
    # Also check that there are not extra package manifests under packages/* that are not expected?
    # Let's detect extra
    packages_root = REPO_ROOT / "packages"
    if packages_root.is_dir():
        for child in packages_root.iterdir():
            if child.is_dir():
                if child.name not in EXPECTED_PACKAGES:
                    # If it has package.json, it's extra
                    if (child / "package.json").is_file():
                        errors.append(f"K: Unexpected package manifest: packages/{child.name}/package.json (expected only seven)")
        # Count
        if len(found_packages) != 7:
            errors.append(f"K: Expected exactly seven M-004 shared package manifests, found {len(found_packages)}")

    # L. expected @vibeflow/* names
    for dir_name, expected_name in EXPECTED_PACKAGES.items():
        ppath = REPO_ROOT / "packages" / dir_name / "package.json"
        if ppath.is_file():
            data = json.loads(ppath.read_text(encoding="utf-8"))
            actual = data.get("name", "")
            if actual != expected_name:
                errors.append(f"L: Wrong package name in packages/{dir_name}/package.json: expected '{expected_name}', got '{actual}'")

    # M. all shared packages are private, 0.0.0 and ESM
    for dir_name in EXPECTED_PACKAGES.keys():
        ppath = REPO_ROOT / "packages" / dir_name / "package.json"
        if ppath.is_file():
            data = json.loads(ppath.read_text(encoding="utf-8"))
            if data.get("private") is not True:
                errors.append(f"M: Package packages/{dir_name}/package.json must have \"private\": true")
            if data.get("version") != "0.0.0":
                errors.append(f"M: Package packages/{dir_name}/package.json must have version \"0.0.0\", got '{data.get('version')}'")
            if data.get("type") != "module":
                errors.append(f"M: Package packages/{dir_name}/package.json must have \"type\": \"module\"")

    # N. TypeBox uses `typebox` 1.x, never @sinclair/typebox
    # Check all package.json for @sinclair/typebox
    for pkg_json_path in REPO_ROOT.rglob("package.json"):
        parts = pkg_json_path.relative_to(REPO_ROOT).parts
        if "node_modules" in parts or ".git" in parts:
            continue
        data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
        for field in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
            deps = data.get(field) or {}
            if "@sinclair/typebox" in deps:
                errors.append(f"N: Forbidden TypeBox 0.x package '@sinclair/typebox' found in {pkg_json_path.relative_to(REPO_ROOT)}")
            if "typebox" in deps:
                ver = deps["typebox"]
                # Must be 1.x - check not 0.x, and specifically our pin
                if ver.startswith("0.") or ver.startswith("0.x") or ver.startswith("@"):
                    errors.append(f"N: TypeBox must be 1.x line, got '{ver}' in {pkg_json_path.relative_to(REPO_ROOT)}")
                # Also ensure it's not referencing outdated registry - we already check pin
    # Also ensure contracts uses typebox 1.3.6
    # Already checked in C

    # O. mandatory TypeScript strict flags
    ts_base_path = REPO_ROOT / "tsconfig.base.json"
    if not ts_base_path.is_file():
        errors.append("O: Missing tsconfig.base.json")
    else:
        try:
            ts_data = json.loads(ts_base_path.read_text(encoding="utf-8"))
            opts = ts_data.get("compilerOptions", {})
            for flag, expected in STRICT_FLAGS.items():
                actual = opts.get(flag)
                if actual != expected:
                    errors.append(f"O: Missing or wrong TypeScript strict flag '{flag}': expected {expected}, got {actual}")
            # Also check modern ESM settings: module should be NodeNext or ESNext etc.
            mod = opts.get("module", "")
            if mod not in ("NodeNext", "Node16", "ESNext", "ES2022"):
                # Not a hard failure but warn? Spec says must use modern ESM/Node-compatible - we enforce NodeNext
                if mod != "NodeNext":
                    errors.append(f"O: tsconfig.base.json module should be 'NodeNext' for ESM, got '{mod}'")
            # Check strict at top
            if opts.get("strict") is not True:
                errors.append("O: tsconfig.base.json must have \"strict\": true")
        except Exception as e:
            errors.append(f"O: Failed to parse tsconfig.base.json: {e}")

    # Also check each package tsconfig extends base
    for dir_name in EXPECTED_PACKAGES.keys():
        tsc_path = REPO_ROOT / "packages" / dir_name / "tsconfig.json"
        if not tsc_path.is_file():
            errors.append(f"O: Missing tsconfig for package {dir_name}: packages/{dir_name}/tsconfig.json")
        else:
            try:
                data = json.loads(tsc_path.read_text(encoding="utf-8"))
                extends = data.get("extends", "")
                if "tsconfig.base.json" not in extends:
                    errors.append(f"O: packages/{dir_name}/tsconfig.json must extend tsconfig.base.json")
            except Exception as e:
                errors.append(f"O: Failed to parse packages/{dir_name}/tsconfig.json: {e}")

    # P. no VibeFlow package lifecycle scripts
    def check_lifecycle(pkg_path: Path):
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        scripts = data.get("scripts") or {}
        for script in FORBIDDEN_LIFECYCLE_SCRIPTS:
            if script in scripts:
                errors.append(f"P: Forbidden lifecycle script '{script}' in {pkg_path.relative_to(REPO_ROOT)}")

    if root_pkg_path.is_file():
        check_lifecycle(root_pkg_path)
    for dir_name in EXPECTED_PACKAGES.keys():
        ppath = REPO_ROOT / "packages" / dir_name / "package.json"
        if ppath.is_file():
            check_lifecycle(ppath)

    # Q, R, S: check .npmrc / pnpm-workspace.yaml supply chain settings
    npmrc_path = REPO_ROOT / ".npmrc"
    npmrc = parse_npmrc(npmrc_path) if npmrc_path.is_file() else {}
    # Also check pnpm-workspace.yaml may contain settings? But we focus on .npmrc

    # Q. no dangerouslyAllowAllBuilds
    if npmrc.get("dangerouslyAllowAllBuilds", "").lower() == "true":
        errors.append("Q: 'dangerouslyAllowAllBuilds' must not be enabled")

    # Also check if any other config file has it
    for cfg in [REPO_ROOT / "pnpm-workspace.yaml", REPO_ROOT / ".npmrc"]:
        if cfg.is_file():
            text = cfg.read_text(encoding="utf-8")
            if "dangerouslyAllowAllBuilds" in text and "true" in text.lower():
                # already flagged, but ensure detection if not via parse
                if "Q: 'dangerouslyAllowAllBuilds'" not in str(errors):
                    # check more strictly
                    if re.search(r"dangerouslyAllowAllBuilds\s*=\s*true", text, re.IGNORECASE):
                        errors.append("Q: 'dangerouslyAllowAllBuilds' must not be enabled")

    # R. release-age policy remains enabled
    # minimumReleaseAge=1440
    mra = npmrc.get("minimumReleaseAge", "")
    if mra != "1440":
        errors.append(f"R: 'minimumReleaseAge' must be 1440, got '{mra}'")
    mras = npmrc.get("minimumReleaseAgeStrict", "")
    if mras.lower() != "true":
        errors.append(f"R: 'minimumReleaseAgeStrict' must be true, got '{mras}'")
    mra_ignore = npmrc.get("minimumReleaseAgeIgnoreMissingTime", "")
    if mra_ignore.lower() != "false":
        errors.append(f"R: 'minimumReleaseAgeIgnoreMissingTime' must be false, got '{mra_ignore}'")
    block_exotic = npmrc.get("blockExoticSubdeps", "")
    if block_exotic.lower() != "true":
        errors.append(f"R: 'blockExoticSubdeps' must be true, got '{block_exotic}'")
    strict_builds = npmrc.get("strictDepBuilds", "")
    if strict_builds.lower() != "true":
        errors.append(f"R: 'strictDepBuilds' must be true, got '{strict_builds}'")

    # S. trustLockfile is not true
    trust = npmrc.get("trustLockfile", "")
    if trust.lower() == "true":
        errors.append("S: 'trustLockfile' must not be true")
    # Also check if trustLockfile missing? spec says trustLockfile is not true, but should be false
    if trust.lower() != "false":
        # If missing or not false, error: spec says trustLockfile is not true and should be false
        # We require false explicitly
        if trust == "":
            errors.append("S: 'trustLockfile' must be false (missing)")
        elif trust.lower() != "false":
            errors.append(f"S: 'trustLockfile' must be false, got '{trust}'")

    # T. no obvious workspace dependency cycles
    # Build graph of workspace deps
    workspace_deps = {}  # pkg name -> list of dep names that are workspace: protocol
    for dir_name, pkg_name in EXPECTED_PACKAGES.items():
        ppath = REPO_ROOT / "packages" / dir_name / "package.json"
        if not ppath.is_file():
            continue
        data = json.loads(ppath.read_text(encoding="utf-8"))
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        for dep, ver in deps.items():
            if isinstance(ver, str) and ver.startswith("workspace:"):
                workspace_deps.setdefault(pkg_name, []).append(dep)
    # Detect cycles via DFS
    def has_cycle():
        visited = set()
        rec_stack = set()
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neigh in workspace_deps.get(node, []):
                if neigh not in visited:
                    if dfs(neigh):
                        return True
                elif neigh in rec_stack:
                    return True
            rec_stack.remove(node)
            return False
        for n in workspace_deps:
            if n not in visited:
                if dfs(n):
                    return True
        return False

    if workspace_deps and has_cycle():
        errors.append(f"T: Workspace dependency cycle detected: {workspace_deps}")
    # Also if M-004 has any workspace deps at all, we consider? Spec says M-004 should avoid unnecessary internal package dependencies
    # But not strictly forbidden, we already have check F that would flag workspace deps? Let's warn if any workspace deps present
    if workspace_deps:
        # For M-004 we expect no workspace deps; if any, it's at least warning but we treat as error per spec "should avoid"
        # Not a hard error unless cycle, but we can warn
        # To keep deterministic, we will error if any workspace deps found
        errors.append(f"T: Unexpected workspace dependencies at M-004 (should avoid): {workspace_deps}")

    # U. M-004 mission progression remains coherent
    # V. M-005 remains LOCKED
    dag_path = REPO_ROOT / "master-build-system" / "10_IMPLEMENTATION" / "MISSION_DAG.yaml"
    reg_path = REPO_ROOT / "master-build-system" / "10_IMPLEMENTATION" / "MISSION_REGISTER.csv"
    # Simple parsing for statuses
    def parse_dag_statuses(p: Path):
        text = p.read_text(encoding="utf-8") if p.is_file() else ""
        # naive regex for mission_id and status
        pattern = re.compile(r"mission_id:\s*(M-\d{3})\s*\n.*?status:\s*(\w+)", re.DOTALL)
        # Better line-based
        statuses = {}
        current_id = None
        for line in text.splitlines():
            m = re.match(r"\s*-?\s*mission_id:\s*(M-\d{3})", line)
            if m:
                current_id = m.group(1)
            m2 = re.match(r"\s*status:\s*(\w+)", line)
            if m2 and current_id:
                statuses[current_id] = m2.group(1)
                current_id = None  # reset after pairing? but status line follows after id, so we keep?
                # Actually status follows after mission_id block, so current_id is still valid prior
                # We'll keep current_id for next? Let's store and continue
                # To handle multiple fields, we need to capture status associated with last mission_id seen
                # The above simplistic will treat status as belonging to last seen mission_id
                # So we should not reset current_id immediately before reading status? We already did.
                # Instead we need to track latest mission_id until status found
                pass
        # Alternative: iterate lines and track
        statuses2 = {}
        last_id = None
        for line in text.splitlines():
            id_match = re.search(r"mission_id:\s*(M-\d{3})", line)
            if id_match:
                last_id = id_match.group(1)
            status_match = re.search(r"status:\s*(\w+)", line)
            if status_match and last_id:
                # This will capture every status line after an id, but there are many statuses; we need to ensure we capture the last status before next mission_id?
                # Better to capture when we see status and associate with most recent id not yet assigned
                # We'll assume each mission block has exactly one status line after id
                # So we can assign and clear last_id after assignment to avoid reassigning same id to next status
                # But if we clear, then next status without new id would be missed (but there is always id before status)
                # We'll assign and keep last_id until next id overrides
                statuses2[last_id] = status_match.group(1)
        return statuses2

    dag_statuses = parse_dag_statuses(dag_path) if dag_path.is_file() else {}

    # Parse register
    reg_statuses = {}
    if reg_path.is_file():
        lines = reg_path.read_text(encoding="utf-8").splitlines()
        if lines:
            header = lines[0].split(",")
            try:
                idx_id = header.index("mission_id")
                idx_status = header.index("status")
            except ValueError:
                errors.append("U: MISSION_REGISTER.csv missing mission_id/status columns")
                idx_id = idx_status = None
            if idx_id is not None:
                for line in lines[1:]:
                    # naive csv split respecting quotes? Use simple but handle quoted commas
                    # Use csv module would be safer, but we implement simple
                    # For robustness, use csv
                    import csv
                    reader = csv.reader([line])
                    row = next(reader)
                    if len(row) > max(idx_id, idx_status):
                        reg_statuses[row[idx_id].strip()] = row[idx_status].strip()
    else:
        errors.append("U: Missing MISSION_REGISTER.csv")

    # Validate progression
    expected_progression = {
        "M-001": "DONE",
        "M-002": "DONE",
        "M-003": "DONE",
        "M-004": "REVIEW",
    }
    for mid, exp_status in expected_progression.items():
        dag_actual = dag_statuses.get(mid)
        reg_actual = reg_statuses.get(mid)
        if dag_actual != exp_status:
            errors.append(f"U: MISSION_DAG.yaml status for {mid} expected '{exp_status}', got '{dag_actual}'")
        if reg_actual != exp_status:
            errors.append(f"U: MISSION_REGISTER.csv status for {mid} expected '{exp_status}', got '{reg_actual}'")

    # Check M-005..M-151 are LOCKED in both
    for i in range(5, 152):
        mid = f"M-{i:03d}"
        dag_s = dag_statuses.get(mid)
        reg_s = reg_statuses.get(mid)
        if dag_s is not None and dag_s != "LOCKED":
            errors.append(f"V: {mid} must remain LOCKED in MISSION_DAG.yaml, got '{dag_s}'")
        if reg_s is not None and reg_s != "LOCKED":
            errors.append(f"V: {mid} must remain LOCKED in MISSION_REGISTER.csv, got '{reg_s}'")

    # W. foundation CI workflow exists
    wf_path = REPO_ROOT / ".github" / "workflows" / "repository-foundation.yml"
    if not wf_path.is_file():
        errors.append("W: Missing foundation CI workflow .github/workflows/repository-foundation.yml")
    else:
        text = wf_path.read_text(encoding="utf-8")
        # Check it contains required steps
        required_snippets = [
            "node --version",
            "pnpm --version",
            "pnpm install --frozen-lockfile",
            "pnpm run check",
            "24.19.0",
            "11.4.0",
        ]
        for snippet in required_snippets:
            if snippet not in text:
                errors.append(f"W: Foundation workflow missing required snippet '{snippet}'")
        # Also check it triggers on pull_request and push
        if "pull_request" not in text:
            errors.append("W: Foundation workflow should run on pull_request")
        if "push" not in text:
            errors.append("W: Foundation workflow should run on push")

    # Also check turbo.json exists
    turbo_path = REPO_ROOT / "turbo.json"
    if not turbo_path.is_file():
        errors.append("Missing turbo.json")
    else:
        try:
            turbo_data = json.loads(turbo_path.read_text(encoding="utf-8"))
            tasks = turbo_data.get("tasks", {})
            for t in ["build", "typecheck", "test"]:
                if t not in tasks:
                    errors.append(f"turbo.json missing required task '{t}'")
        except Exception as e:
            errors.append(f"Failed to parse turbo.json: {e}")

    # Print results
    if errors:
        print("M-004 foundation validation FAILED")
        for e in errors:
            print(f"  ERROR: {e}")
        if warnings:
            for w in warnings:
                print(f"  WARN: {w}")
        print(f"Total errors: {len(errors)}")
        return 1
    else:
        print("M-004 foundation validation PASSED")
        if warnings:
            for w in warnings:
                print(f"  WARN: {w}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
