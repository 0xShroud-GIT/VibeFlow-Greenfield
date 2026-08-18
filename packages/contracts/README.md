# packages/contracts

The shared VibeFlow contract package: canonical resource names, state machines
and event catalog metadata, exposed as JSON Schema plus derived TypeScript types.

## Authority

The **Master Build System owns authority**. This package owns nothing.

Everything published here is *derived* from the authoritative master files that
`master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml` routes to:

| Route       | Authoritative file                                    |
| ----------- | ----------------------------------------------------- |
| `resources` | `02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml`       |
| `states`    | `03_BACKEND/STATE_MACHINES.yaml`                      |
| `events`    | `03_BACKEND/EVENT_CATALOG.yaml`                       |

There is no second, hand-maintained copy of these vocabularies. To change a
resource, state or event, change the master file and regenerate.

## Generated files — DO NOT EDIT

```
packages/contracts/src/generated/catalog.ts        # TS constants, schemas, derived types
packages/contracts/generated/catalog.schema.json   # JSON Schema 2020-12 bundle
packages/contracts/generated/catalog.manifest.json # inputs, input hashes, counts, inventory
```

Manual edits to these files are a drift error and are rejected by CI. Fix drift
by regenerating, never by hand-patching.

## How to generate

```bash
pnpm run contracts:generate     # python3 scripts/generate-contracts.py
```

## How to check for drift

```bash
pnpm run contracts:check        # python3 scripts/generate-contracts.py --check
```

`--check` performs **no writes**. It regenerates the expected bytes in memory and
fails on missing, stale or unexpected generated output. It also runs as a stage
of the root `pnpm run check`.

The generator is stdlib-only Python and deterministic: identical authoritative
inputs always produce byte-identical artifacts. It emits no timestamps, machine
paths, hostnames or random identifiers.

## JSON Schema first; TypeScript types derived

Each vocabulary is emitted as a raw JSON-Schema-compatible literal, and the
matching TypeScript type is derived from that literal using TypeBox `Static<>`:

```ts
export const CanonicalResourceNameSchema = {
  type: "string",
  enum: ["Account", "Organization", "Project" /* … */]
} as const;

export type CanonicalResourceName = Static<typeof CanonicalResourceNameSchema>;
```

TypeBox is pinned at `typebox@1.3.6` (TypeBox 1.x, ESM) per harvest entry H-025.
Runtime validation uses TypeBox's own raw JSON Schema API (`Check` from
`typebox/schema`); no separate validator (Ajv or otherwise) is a dependency.

## Exports

| Specifier                       | Contents                            |
| ------------------------------- | ----------------------------------- |
| `@vibeflow/contracts`           | compiled TypeScript entry (`dist/`) |
| `@vibeflow/contracts/schema`    | generated `catalog.schema.json`     |
| `@vibeflow/contracts/manifest`  | generated `catalog.manifest.json`   |

## Scope limit

The catalog currently carries the canonical **vocabularies and event metadata**
that the master pack actually defines: resource names, state-machine names,
state and terminal-state enums, event IDs/names, and each event's `resource`,
`producer`, `envelope` and `durable` fields.

Command payload schemas, event payload schemas, REST request/response shapes,
persistence schemas and an error-code catalog are **deliberately absent**. The
master pack does not yet define them, and this pipeline does not manufacture
missing domain authority. The generator is capable of emitting those contracts
as soon as an authoritative domain mission defines them.
