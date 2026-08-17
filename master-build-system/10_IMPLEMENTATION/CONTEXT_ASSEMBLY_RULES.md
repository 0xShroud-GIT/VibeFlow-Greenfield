# Mission Context Assembly

A mission packet is generated from the master pack; it is not hand-written free-form context.

Include:
- mission row and explicit non-goals,
- relevant invariants only,
- relevant capability ledger rows,
- relevant resource/state/event/API/frontend-backend contracts,
- approved harvest entries,
- files/modules expected to change,
- acceptance tests/evidence.

Exclude by default:
- unrelated masters,
- full Replit research/evidence pack,
- future mission details,
- giant dependency docs,
- decompiled/disassembled material.

Target <= 12k tokens for ordinary implementation missions. Increase only when the mission intrinsically spans contracts.
