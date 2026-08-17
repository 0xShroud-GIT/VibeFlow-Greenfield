# Canonical User Journeys

## J1 — Zero to running project
Create Project → choose/connect Agent/Model/Workspace → create Task → Agent works → open files/terminal/preview → candidate completion → verification → VERIFIED.

## J2 — Phone disconnect
Execution runs remotely → phone loses connection → durable execution continues → phone reconnects → replay missed events → reconcile authoritative state → continue without duplicate work.

## J3 — Privileged tool action
Agent requests tool → grant/policy evaluation → durable approval if required → approved scoped execution → immutable evidence/audit.

## J4 — Recovery
Execution/provider/workspace interruption → classify failure → replay events only for UI continuity → reconcile workspace revision → reattach/retry as policy permits → reverify → recovered or honest EXECUTION_LOST/BLOCKED.

## J5 — Release
Verified candidate → Release created with exact revision/evidence → deployment adapter → production health evidence → deploy success/rollback while dev workspace remains independent.

## J6 — Provider replacement
Replace Agent/Model/Workspace/Deployment binding → Project/Task/Evidence identity remains stable → adapter certification and reconciliation preserve user continuity.
