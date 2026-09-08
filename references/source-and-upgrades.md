# Source identity and upgrades

This distribution is `Zero-State-LLC/Sigil-Forge`, version `0.13.1`, based on commit
`26e72a071db27e7ce123a9459748661803897a11` before the local audit-fix commit. Record the actual installed commit
with `git rev-parse HEAD` before installation; do not use a version string alone
as a source identity. Root and hub packaging are distribution surfaces, not a
claim that organizational, personal, or legacy embedded variants are identical.
No personal version is deprecated by this change.

Before switching sources, stop runtime writers, record current source/commit,
review the destination under `${HERMES_HOME:-$HOME/.hermes}`, compare contracts,
and retain a separate backup of outputs, sessions, and local customization.
Do not install two different contracts with the same skill name into one profile.
A successful compatibility check does not grant deployment/publication authority.

The bundled LICENSE controls this distribution. No license grant is changed by
these fixes; earlier grants and third-party notices remain intact.

The installer validates a fresh stage on the target filesystem before replacement,
then reads back the activated contract/version/provenance receipt. Checks use an
isolated temporary home. Legacy `out` contents (including an out symlink) survive.
Backups are unique, keyed by canonical destination under the active Hermes home's
`backups/<skill>/<target-hash>/`; `.install-provenance.json` records source, base
commit, dirty status, version, destination, and skipped checks. Stop writers during
upgrades. Two renames have an absent-target window: this is NOT crash-atomic.
On a reported recovery failure, retain the printed recovery directory and backup;
do not delete it or retry blindly. Inspect the exact target and restore from the
named backup only after validating it. No automatic source migration is implied.

New default products: `${HERMES_HOME:-$HOME/.hermes}/state/sigil-forge/products`.
Sessions: the adjacent `wizard-sessions` directory. `SIGIL_FORGE_STATE_DIR` overrides
that state root; explicit `--out` still controls product output. Legacy installed
`out/wizard-sessions/<id>.json` is read as a fallback and copied into external state
on the next update, without removing the old file. Existing products remain at their
old paths. Keep the same session id through final wizard application.

## Interrupted installs and stale locks

SIGKILL or power loss can leave `.<target-name>.install-lock` beside the target.
Locks are never automatically reclaimed: age, an empty directory, or a reused PID
cannot prove that no installer is active. To recover:

1. Stop install launchers and runtime writers. Confirm no installer is active on
   this target (including other sessions/hosts sharing the filesystem).
2. Inspect the exact target, sibling `.<skill>-stage-*` recovery directories
   (especially `previous` and `failed-package`), and target-keyed backups. Retain
   all recovery data until the original installation and outputs are accounted
   for. Restore/validate a complete package first if activation was interrupted.
3. Only then set `lock` to the exact path printed in the error and run
   `rmdir -- "$lock"`. This removes only an empty lock; never use recursive
   deletion or remove a lock whose owner/activity is uncertain. Keep launchers
   stopped through inspection and removal to avoid races, then retry installation.

Backup copies are staged in `.backup-incomplete-*` outside the target's selectable
backup directory and published by rename after copying and writing the destination
record. Hard termination can leave these incomplete staging trees; never select
one for rollback. Inspect them manually after quiescing writers. Rollback skips
legacy partial entries without a valid matching destination record.

Git is optional. Archive sources, failed Git lookups, and unrelated enclosing
worktrees record unknown Git fields as JSON `null`, never a false clean claim.
A source-root worktree or the tracked `skills/neon-genie` hub with matching root
contract/version supplies Git provenance. Receipts distinguish
`source_repository_root` from `source_subdirectory` (`.` or `skills/neon-genie`).
A dirty status lookup failure remains `null` even in a recognized worktree.
