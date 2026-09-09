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
- Windows delta record: the first Windows 10/Python 3.10 run produced 5 PASS
  and 3 harness failures: WinError 1314 for an unprivileged symlink and two
  subprocess initialization failures caused by replacing the child environment
  with PATH alone. The corrected tests skip only the unavailable Windows
  symlink capability (Linux CI still exercises it) and pass the full inherited
  environment to isolated Python processes.
- CI failure record: GitHub Actions runs 1 and 2 ended before job creation
  because the inline Python command contained an unquoted YAML colon. The
  command is now a fully quoted YAML scalar; this is a workflow-only delta and
  does not change runtime behavior or sealed sources.
- Credit guard: no reliable in-repository credit meter exists. This bounded Terra
  implementation is to stop and report before any additional broad work.
- Release-candidate decision: the deployable unit is a source-only ZIP set,
  not a web/Netlify production service. Runtime, landmarker, and public-guide
  bundles are deterministically timestamped from Git/SOURCE_DATE_EPOCH and
  accompanied by a SHA-256 manifest. The builder verifies archive
  traversal/duplicate/member inventory, required files, checksums, and isolated
  ZIP imports before an Actions artifact can be uploaded.
- Release boundary: PR and ordinary `main` CI may build/upload candidates only.
  GitHub Release publication is excluded from PRs and requires an existing
  explicit `v*` tag at the current `main` commit. `contents: write` exists only
  on that release job;
  actual tag/release publication is an external effect and was not run locally.
- Verification record (release delta): deterministic double-build, manifest
  checksum/inventory/path-traversal checks, isolated import checks, complete
  portable Post-V2 pytest suite, Python compileall, YAML parsing, and diff/seal
  checks are required before this change can request CI. Any release refusal due
  to a non-main tag, missing artifact, or failed recheck is a deployment
  authorization failure, not a sealed-runtime code failure.
- Public-policy base: `6522c775e5b6856138d164c715be8787d48a7629` (`main`)
  was incorporated before this release delta. Its policy is the source of truth:
  engine, pins, and guides are public; Meshy/user meshes, derived GLB/FBX, IRG
  ZIPs, and legacy outputs remain private. No listed binary was resolved,
  copied, uploaded, or used during this work.
- Policy enforcement decision: candidate build/verify now validates
  `ASSETS_MANIFEST.json` as a pin-only schema and checks Git-tracked paths for
  protected mesh/archive suffixes and `dist`/`.nurion_blender_tmp` directories.
  The candidate manifest additionally binds each archive to a static source
  allowlist derived from the checked-out source revision; manifest-only added
  files cannot be accepted. This closes the prior gap where a self-consistent
  manifest could otherwise describe an unexpected member.
- Release-candidate inventory: three deterministic, source-only bundles are
  emitted: Post-V2 runtime, Character Landmarker add-on, and public guides.
  Only Python source or named public Markdown files can enter them; the two
  Python bundles are imported under `-I -S`. GitHub Actions uploads the candidate
  for PR/main CI and permits `contents: write` only in the tag/main-authorized
  Release job. No tag, release, CI dispatch, push, merge, or production action
  was performed locally.
- Expected deployment refusal record: a tag that is not exactly current `main`,
  a non-`v*` manual tag, a missing candidate artifact, a manifest mismatch, or
  a protected asset path is a release authorization/policy refusal. It is not
  evidence that the sealed V2/v0.5/v0.6/V07 sources failed.
