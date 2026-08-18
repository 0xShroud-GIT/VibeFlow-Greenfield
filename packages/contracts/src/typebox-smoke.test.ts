import { describe, it, expect } from "vitest";
import { Check } from "typebox/schema";
import type { Static } from "typebox";

import {
  CANONICAL_RESOURCES,
  CanonicalResourceNameSchema,
  type CanonicalResourceName,
  STATE_MACHINE_NAMES,
  StateMachineNameSchema,
  type StateMachineName,
  TaskStateSchema,
  type TaskState,
  TaskTerminalStateSchema,
  type TaskTerminalState,
  ExecutionStateSchema,
  RecoveryRecordStateSchema,
  EVENT_IDS,
  EVENT_NAMES,
  EventIdSchema,
  type EventId,
  EventNameSchema,
  type EventName,
  EVENT_CATALOG,
  CONTRACT_CATALOG_ID
} from "./index.js";

describe("M-005 generated contract catalog — TypeBox 1.3.6 raw JSON Schema", () => {
  it("exposes raw JSON Schema literals that TypeBox accepts directly", () => {
    expect(CanonicalResourceNameSchema.type).toBe("string");
    expect(Array.isArray(CanonicalResourceNameSchema.enum)).toBe(true);
    expect(StateMachineNameSchema.type).toBe("string");
    expect(TaskStateSchema.type).toBe("string");
    expect(EventIdSchema.type).toBe("string");
    expect(CONTRACT_CATALOG_ID).toBe("urn:vibeflow:contracts:catalog:v1");
  });

  it("validates a canonical resource value and rejects an invalid one", () => {
    expect(Check(CanonicalResourceNameSchema, "Project")).toBe(true);
    expect(Check(CanonicalResourceNameSchema, "Execution")).toBe(true);
    expect(Check(CanonicalResourceNameSchema, "NotAResource")).toBe(false);
    expect(Check(CanonicalResourceNameSchema, "project")).toBe(false);
    expect(Check(CanonicalResourceNameSchema, 42)).toBe(false);
  });

  it("validates a canonical state and rejects an invalid state", () => {
    expect(Check(TaskStateSchema, "CANDIDATE_COMPLETE")).toBe(true);
    expect(Check(TaskStateSchema, "VERIFIED")).toBe(true);
    expect(Check(TaskStateSchema, "DONE")).toBe(false);
    expect(Check(ExecutionStateSchema, "LOST")).toBe(true);
    expect(Check(ExecutionStateSchema, "COMPLETED")).toBe(false);
    expect(Check(RecoveryRecordStateSchema, "EXECUTION_LOST")).toBe(true);
    expect(Check(RecoveryRecordStateSchema, "RECOVERED_MAYBE")).toBe(false);
  });

  it("keeps terminal states a subset of the machine's states (INV-016)", () => {
    for (const terminal of TaskTerminalStateSchema.enum) {
      expect(Check(TaskStateSchema, terminal)).toBe(true);
    }
    // INV-001: agent completion is candidate completion, never terminal VERIFIED
    // by assertion alone. CANDIDATE_COMPLETE is a state but not a terminal one.
    expect(Check(TaskStateSchema, "CANDIDATE_COMPLETE")).toBe(true);
    expect(Check(TaskTerminalStateSchema, "CANDIDATE_COMPLETE")).toBe(false);
  });

  it("validates canonical state-machine names", () => {
    expect(Check(StateMachineNameSchema, "Execution")).toBe(true);
    expect(Check(StateMachineNameSchema, "Workspace")).toBe(false);
    expect(STATE_MACHINE_NAMES.length).toBe(7);
  });

  it("validates EventId and EventName values", () => {
    expect(Check(EventIdSchema, "EVT-001")).toBe(true);
    expect(Check(EventIdSchema, "EVT-037")).toBe(true);
    expect(Check(EventIdSchema, "EVT-999")).toBe(false);
    expect(Check(EventNameSchema, "execution.candidate_complete")).toBe(true);
    expect(Check(EventNameSchema, "execution.totally_made_up")).toBe(false);
  });

  it("keeps generated catalog data aligned with the generated enums", () => {
    expect(CANONICAL_RESOURCES.length).toBe(35);
    expect(EVENT_IDS.length).toBe(37);
    expect(EVENT_NAMES.length).toBe(37);
    expect(EVENT_CATALOG.length).toBe(37);
    expect([...CANONICAL_RESOURCES]).toEqual([...CanonicalResourceNameSchema.enum]);
    expect([...EVENT_IDS]).toEqual([...EventIdSchema.enum]);
    expect([...EVENT_NAMES]).toEqual([...EventNameSchema.enum]);
    expect(EVENT_CATALOG.map((event) => event.id)).toEqual([...EVENT_IDS]);
    expect(EVENT_CATALOG.map((event) => event.name)).toEqual([...EVENT_NAMES]);
  });

  it("derives TypeScript types from the schemas via Static<> (compile-time proof)", () => {
    // These annotations only compile because the types are derived from the
    // JSON Schema literals rather than being handwritten unions.
    const resource: CanonicalResourceName = "Project";
    const machine: StateMachineName = "Execution";
    const state: TaskState = "CANDIDATE_COMPLETE";
    const terminal: TaskTerminalState = "VERIFIED";
    const eventId: EventId = "EVT-011";
    const eventName: EventName = "execution.candidate_complete";

    // A terminal state must be assignable to the wider state type.
    const widened: TaskState = terminal;

    // Derivation is exact: an invalid member is a compile-time error.
    // @ts-expect-error "NotAResource" is not a canonical resource name
    const invalidResource: CanonicalResourceName = "NotAResource";
    // @ts-expect-error "DONE" is not a canonical Task state
    const invalidState: TaskState = "DONE";

    // The catalog row type is derived from the generated data, not handwritten.
    type Row = Static<typeof EventIdSchema>;
    const row: Row = eventId;

    expect([resource, machine, state, widened, row, eventName]).toHaveLength(6);
    expect([invalidResource, invalidState]).toHaveLength(2);
  });
});
