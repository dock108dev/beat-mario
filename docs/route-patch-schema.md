# Route Patch Schema

This is the existing **engineering source-change** workflow. The September 23 [personal-beta packet](personal-beta-engineering.md) requires a separate player-facing, typed plan/revision flow for live custom paths. That flow must not translate conversational edits into unchecked source patches or worktree promotion while a game runs. Reuse provenance and review principles while keeping runtime plan authority distinct from source-patch validation and historical route acceptance.

Rank 33 adds `beat-mario.route-patch/v1`, the only executable route-change
contract accepted by the CLI and Game Companion Lab. Descriptive variant proposals
remain review aids; they cannot validate or promote themselves.

## Contract

The tracked example is `data/lab/route-patch-template.yaml`. A patch records:

- patch and variant ids;
- source kind (`route_lab_issue` or `codex_task`), session, issue, notes, and
  optional task packet;
- parent variant and full repository base commit;
- reviewed file allowlist;
- SHA-256 preimage and expected postimage for every changed file;
- ordered `replace_text` operations containing complete UTF-8 postimages;
- summary, internally selected validation profile, rollback description,
  timestamps, and producer provenance;
- only the initial `imported` lifecycle state.

Review, validation, comparison, promotion, and rollback decisions live in
separate Route Lab-owned artifacts. A submitted patch cannot declare those
results. Full-file text replacement is deliberate: Rank 33 does not accept raw
hunks, so ambiguous, overlapping, offset, and already-applied hunks cannot be
interpreted differently at preview and application time.

## Lifecycle and artifacts

```text
imported
-> reviewed
-> prepared
-> applied_to_candidate
-> validated
-> promoted
-> rolled_back
```

`rejected` and `failed` are terminal audit states. Every transition is checked
against the state graph. Artifacts are written beneath
`artifacts/route-patches/PATCH_ID/`:

- `contract.yaml` and `state.yaml`;
- `review.yaml`;
- `candidate.yaml` and `candidate.diff`;
- per-gate stdout/stderr plus `validation.yaml`;
- `comparison.yaml`;
- `promotion.yaml`, `inverse-patch.yaml`, and the previous baseline-metadata
  snapshot when present;
- `rollback.yaml` or failure diagnostics.

Records link the exact diff SHA-256, source records, file hashes, candidate base
commit, gate argv arrays, exit codes, elapsed time, environment, and output
artifact hashes.

## Isolation and validation

`prepare` creates a detached temporary Git worktree at the reviewed commit.
Git materializes tracked files only, so ignored local runtime inputs and generated artifacts
are not copied into the candidate. Application is atomic and changes exactly
the reviewed files. The accepted working tree remains untouched.

Validation runs with the candidate as `cwd` and its `src` as `PYTHONPATH`.
Parent gates run in a second detached worktree. Commands come only from the
internal profile map and are passed to `subprocess` as argv arrays with
`shell=False`.

Profiles fail closed:

- `canonical_phase`: non-live route-data and Route Lab changes;
- `canonical_rank27`: canonical gate plus the 5/5 World 8 arrival regression;
- `canonical_rank27_rank28`: canonical gate plus Rank 27 5/5 and Big Tanks
  3/3;
- `documentation_static`: bounded diff/static validation. It is explicitly not
  route-execution proof and cannot be promoted through the route-patch loop.

## Promotion and rollback guards

Promotion requires an explicit patch-id confirmation. It verifies the review,
candidate, validation, comparison, diff hash, artifact hashes, clean accepted
worktree, current HEAD, and current preimages. It writes the exact validated
postimages atomically, verifies them, and records an inverse patch. It never
commits, pushes, or opens a pull request.

Rollback also requires exact patch-id confirmation and a reason. It refuses if
any promoted file no longer matches the recorded postimage, applies only the
recorded inverse, and verifies byte-for-byte restoration. Promotion and
validation history remain intact.

Corrupt ignored patch records do not take down Route Lab discovery, but each
skipped record is logged with its path and parse error. Temporary-worktree
removal and prune failures are also logged, and cleanup refuses broad targets
such as the current directory, repository root, or filesystem root. See
[Error handling and operations](error-handling.md).

## Security boundary

Import rejects absolute and traversal paths, symlink targets, files outside the
reviewed task allowlist, local runtime inputs, savestates, images, logs, archives, generated
evidence, caches, unsupported extensions, binary or malformed UTF-8 content,
stale bases or preimages, missing hashes, duplicate operations, no-op/already
applied content, excessive sizes, protected gate files, command declarations,
and self-declared approval or validation results before an accepted-tree write.

Rank 33 edits existing tracked UTF-8 text files only. File creation, deletion,
rename, binary diffs, and reviewed rebase are intentionally unsupported and
fail closed.
