# Architecture exception ledger

No active exceptions.

Each exception must include:

- ADR identifier;
- exact files/imports/diagnostics covered;
- owner;
- reason the normal rule cannot currently hold;
- risk introduced;
- expiry date or objective revisit trigger;
- removal criteria.

Suppressions in code must use a narrow code and include `ARCH-EXCEPTION: ADR-XXXX`.
