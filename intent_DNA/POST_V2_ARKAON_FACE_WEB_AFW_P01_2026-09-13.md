# Intent DNA — AFW-P01 Identity and QA Calibration Proposal

- Change Request: `POST-V2-CR-ARKAON-FACE-WEB-01`
- Profile: `ARKAON FACE WEB PROFILE`
- Phase: `AFW-P01`
- Revision: `R1`
- Status: **HUMAN DESIGN APPROVED**
- Calibration lock: **FALSE — PRIVATE CALIBRATION PENDING**
- Execution: **NOT EXECUTED**
- Implementation authority: **NONE**
- Open status: **NOT OPEN**

## Intent

Define how identity, facial geometry, expression behavior, neutral return, GLB reload, web performance, rights, privacy, external uploads, human review, and failure routing will later be calibrated from rights-confirmed private samples.

The R1 design has explicit human approval for documentation lock only. This document set contains no universal numeric threshold. It does not ingest samples, run measurements, implement tooling, authorize external services, or alter an asset.

## Decision model

Identity is evaluated through approved multi-view references, normalized facial geometry, approved appearance characteristics, and a private Human Visual Receipt. No single face embedding, landmark score, provider label, or automated metric is authoritative.

QA follows:

`NEUTRAL → TARGET → PEAK → RELEASE → NEUTRAL RETURN → COMBINATION → TALKING → GLB RELOAD → REPEAT`

The required minimum runtime evidence remains `Blink_L`, `Blink_R`, `Jaw_Mouth`, `VISEME_AA`, `VISEME_OH`, `VISEME_EE`, a TALKING clip, `sourceUnmutated=true`, and `bodySkinDigestMatch=true`.

## Calibration rule

Thresholds are derived only after eligible private samples, their rights/privacy records, measurement definitions, normalization methods, tool versions, observed distributions, and human decisions are linked by digest. A tool-version, population, character-style, topology, or target-device change triggers applicability review.

Missing evidence, ambiguous mapping, or machine/human disagreement cannot produce automatic PASS.

## Rights and privacy

Rights and privacy are independent classifications. AI processing, derivative use, commercial use, and public redistribution are separately verified claims. Identifying reference images, landmarks, embeddings, prompts, seeds, source/derived models, screenshots, and visual receipts remain private.

## External upload

An upload gate is bound to one provider, purpose, digest-pinned asset bundle, operation, authorization, and validity window. Unknown provider terms, training use, retention/deletion, subprocessors, likeness rights, purchase authority, or redistribution rights block the upload.

No Meshy or other external upload has been authorized or performed.

## Failure routing

- `REPAIR`: smallest evidenced failed region.
- `REGENERATE`: proposal only; requires evidence that partial repair is insufficient and separate human authorization.
- `REJECT`: rights/privacy/provenance, V2 boundary, source mutation, or preservation failure.
- `BLOCKED`: insufficient evidence, ambiguous mapping, or repair-cycle exhaustion.

The default repair-cycle limit remains three. Previous accepted checkpoints are never overwritten.

## V2 and authority boundary

`NURION_ADAPTATION_ENGINE_V2` remains **CLOSED / PASS / CONSUME ONLY / READ_ONLY**. This AFW-P01 design approval does not lock calibration and does not transition `OPEN_PROTOTYPE` or `GRANTED`.

All later actions remain governed by:

`READ → ANALYZE → PROPOSE → AUTHORIZE → EXECUTE → VERIFY → REPORT`
