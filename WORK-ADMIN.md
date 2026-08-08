# Cross-Repository Administration

Global repository registry, cross-domain status, and the master calendar are maintained in `krahd/tom-work-admin`.

This repository remains canonical for **modelito** source, releases, tests, documentation, and project-specific technical state.

Any manuscript or publication artefact belongs canonically in `krahd/academic-writing`; submission-specific professional or artistic packages belong in `krahd/professional-opportunities`; grant, funding, and compute application packages belong in `krahd/grant-applications`.

## Mandatory synchronisation rule

`krahd/tom-work-admin` **must be kept current** whenever work here materially changes the project's administratively meaningful state. Updating the administration repository is part of completing the change, not optional later cleanup.

Update this repository first for substantive project changes, then update `krahd/tom-work-admin` in the same work session when any of the following changes:

- project lifecycle state, scope, provider abstraction, supported backends, or major technical direction;
- release/version, distribution, compatibility, API boundary, test state, or major validation milestone;
- relationship to another active project, manuscript, grant, repository, service, or other cross-domain dependency;
- deadline, release target, deprecation, or other material cross-domain date;
- current next action or major technical gate.

## Ownership boundary

Keep source, tests, release artefacts, documentation, and technical evidence here. `tom-work-admin` stores only the concise cross-repository view and must point back to canonical project sources rather than duplicate them.

## Completion check

Before considering a material project-state change complete, verify that:

1. this repository reflects the substantive change;
2. `krahd/tom-work-admin` reflects any resulting global status, relationship, version dependency, date, or next-action change;
3. dependent project records are updated where the change affects them;
4. no stale cross-domain status remains in `tom-work-admin`.
