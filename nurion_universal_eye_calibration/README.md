# NURION Universal Eye Calibration v0.3.0-rc.1

**RELEASE CANDIDATE = TRUE**  
**SEALED = FALSE**  
**HOLDOUT = WAITING**  
**FINAL SEAL = HOLD**

## What this package is

Gate 1–6 locked Universal Eye Calibration runtime for Blender:

1. Universal Face Basis  
2. Flat Eye Plane  
3. Convex Dome  
4. Gaze Motion  
5. Blink (Procedural Lid Proxy)  
6. Expression–Eye Matching  
7. Beauty Eye materials (NATURAL default)

Geometry and motion parameters from Gate 1–5 are immutable. Gate 6 adds materials/optical layers only.

## Install

1. Blender → Edit → Preferences → Add-ons → Install  
2. Select `NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip`  
3. Enable **NURION Universal Eye Calibration**  
4. Sidebar → **NURION** → **NURION Universal Eye**

## UI

- Assert Gate Locks  
- Run Gate1→6 Pipeline  
- Beauty preset: NATURAL / LUMINOUS / AI_PREMIUM  
- Mobile tier: High / Medium / Low / Fallback  
- Export Validation Status  

Engine default beauty preset is **NATURAL**. ARKAON ABA may select **AI_PREMIUM** at product integration time.

## Holdout policy

Captain was used during development cross-validation and is **not** eligible as final holdout.  
Gate 7B requires a fresh Meshy humanoid asset (see VALIDATION_STATUS.json).

## Hash policy

Full 64-character SHA-256 only.
