import { Type, type Static } from "typebox";

export const HealthSchema = Type.Object({
  status: Type.Literal("ok"),
  version: Type.String()
});

export type Health = Static<typeof HealthSchema>;

export const CONTRACTS_PACKAGE = "@vibeflow/contracts" as const;
