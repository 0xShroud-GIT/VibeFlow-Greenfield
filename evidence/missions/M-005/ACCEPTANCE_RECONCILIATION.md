# M-005 Acceptance Reconciliation (Append-Only)

This record is appended to M-005 evidence. It does not edit, replace, or delete
any prior M-005 evidence statement.

## Independent acceptance identity

- Reviewed head: `7530df9bf18ddaa81d782ef8a0cbeb9ee817aedb`
- Merge SHA: `76f2f2ae908cd728e337b64fe538cbd07a158945`
- Outcome: M-005 accepted and merged; M-005 is now `DONE`.
- Final retained M-004 mutation suite at acceptance: **82 tests**.
- Final M-005 mutation suite at acceptance: **87 tests**.

The historical earlier **47/61** counts and snapshot-permanence statements in
prior evidence are superseded by the later review-response and generalized
validator evidence. They remain preserved as historical records; they are not
rewritten to make the earlier statements disappear.

## Post-merge finding reconciled by M-006

One remaining progression defect was discovered after merge:
`scripts/validate-m005-contract-codegen.py` rejected every `allowBuilds` key even
when M-005 was already `DONE`. That froze an M-005 absence as a permanent rule
and would have blocked a later explicitly reviewed package build-script
approval.

M-006 corrects the retained gate without weakening M-004:

- while M-005 is active, `allowBuilds` remains forbidden;
- after M-005 acceptance, each entry must be an explicit boolean `true` and
  reconcile to an npm coordinate plus a matching harvest-side approval and
  non-empty rationale;
- unregistered, malformed, or unapproved entries fail;
- `dangerouslyAllowAllBuilds` remains forbidden forever.

The M-006 branch adds deterministic retained-gate coverage for the historical
rejection, a durable approved pass, an unapproved failure, and the permanent
blanket-build failure. The accepted 87-test M-005 count above remains the
historical acceptance count; M-006's appended tests are later evidence.
