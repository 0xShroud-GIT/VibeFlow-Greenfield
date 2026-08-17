# Workspace Isolation

VibeFlow initially uses certified workspace providers instead of building a proprietary sandbox fabric. Certification tests filesystem/project scoping, process isolation, network controls, preview auth, secrets exposure, snapshot/persistence behavior, resource limits, cleanup and cross-tenant separation.

Provider documentation is not sufficient evidence; VibeFlow adapter tests record observed behavior.
