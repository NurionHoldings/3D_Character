# Intent DNA — Post-V2 runtime hardening

- Base inspected: `43733b9` (`main`), 2026-09-08 UTC.
- Scope decision: preserve all V2 adaptation/CR01–CR04 consume-only material,
  v0.5/v0.6 seal/receipt/status values, and V07/CCS locked PASS artifacts.
  Implement only a new `nurion_post_v2_runtime` layer. The full v0.6 Gate 6
  source is consume-only and restored byte-for-byte to `43733b9`.
- Risks addressed: unvalidated FBX input; output-root escape and partial export;
  order-dependent armature/mesh selection; non-finite or inconsistent timing;
  malformed landmark profiles; no headless CI contract suite; workstation paths.
- Sol correction record: the first Terra attempt incorrectly modified Gate 6,
  accepted stale state, and added a top-level landmarker dependency. This was
  BLOCKED. The correction isolates a new operator/runtime, invalidates stale
  descendants, validates write evidence, embeds landmarker validation, and uses
  transaction-wide data-block rollback.
- Safety decisions: fail closed; no production action; no external payment, SMS,
  mail, order, or deletion; output is symlink-safe/no-clobber within the
  allowlisted root; import rollback covers all tracked newly created data blocks.
- Baseline failure record: a fresh historical full pytest collection fails before
  Post-V2 tests because the locked V07 canonical fixture under `dist/` is absent
  and one historical test imports undeclared `cv2`. These are recorded as
  independent baseline/dependency gaps and are not repaired by altering locked
  V07 material. The CI scope is the complete portable Post-V2 contract suite.
- Verification record: `compileall` PASS; default pytest uses the explicit
  Post-V2 `testpaths` and PASS (8 tests, including state invalidation,
  no-write/false-state failure, symlink/no-clobber contract, fake Blender
  all-data-block rollback, and runtime/add-on zip isolation); offline smoke
  PASS; `git diff --check` PASS; the four Gate 6 source files compare equal to
  `43733b9`. No Blender-scene result is claimed without an installed executable.
- Commit record: this file, implementation, tests, CI workflow, and portable
  documentation are committed together on `chore/post-v2-runtime-hardening`.
- HEAD change policy: only this Post-V2 change set was reviewed after the base
  `43733b9`; no re-review of unchanged locked material was performed.
- Credit guard: no reliable in-repository credit meter exists. This bounded Terra
  implementation is to stop and report before any additional broad work.
