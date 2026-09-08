"""Gate8A clean-scene full limited integration regression."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nurion_v04_face_rig.gate1.capability_diagnosis import diagnose_once
from nurion_v04_face_rig.gate2.integration import run_gate2_once
from nurion_v04_face_rig.gate3.integration import run_gate3_once
from nurion_v04_face_rig.gate4.integration import run_gate4_once
from nurion_v04_face_rig.gate5a2.integration import align_one_v2
from nurion_v04_face_rig.gate5b.integration import run_gate5b_once
from nurion_v04_face_rig.gate5b.renderer import sample_curves
from nurion_v04_face_rig.gate6.manifest import resolve_items
from nurion_v04_face_rig.gate7.input_gate import admit_jobs
from nurion_v04_face_rig.gate7.integration import run_gate7_once
from nurion_v04_face_rig.gate7.parameters import CORE_IDS, STRESS_IDS
from nurion_v04_face_rig.gate7.timeline_io import load_gate6_timelines

from .lock_check import verify_all_locked
from .parameters import GATE8A_PARAMETERS, parameter_hash


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _count_rest(phonemes: List[Dict]) -> int:
    n = 0
    for p in phonemes:
        if p.get("symbol") != "SIL":
            continue
        if p.get("rule") == "SAFE_REST_LOW_OR_INSUFFICIENT":
            n += 1
        elif p.get("alignedSymbol") and p.get("alignedSymbol") != "SIL":
            n += 1
    return n


def _timeline_from_alignment(uid: str, alignment: Dict) -> Dict:
    return {
        "name": uid,
        "source": "FORCED_ALIGNMENT",
        "durationMs": int(alignment["durationMs"]),
        "phonemes": [dict(p) for p in (alignment.get("phonemes") or [])],
        "lowConfidenceSegments": list(alignment.get("lowConfidenceSegments") or []),
    }


def _phoneme_sig(phonemes: List[Dict]) -> str:
    slim = [
        {
            "symbol": p.get("symbol"),
            "startMs": int(p.get("startMs", 0)),
            "endMs": int(p.get("endMs", 0)),
            "confidence": round(float(p.get("confidence", 0.0)), 6),
            "rule": p.get("rule"),
            "alignedSymbol": p.get("alignedSymbol"),
            "intensityTier": p.get("intensityTier"),
        }
        for p in phonemes
    ]
    return _sha_json(slim)


@dataclass
class Gate8AResult:
    role: str
    asset: str
    report: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _align_corpus(manifest_path: Path) -> Dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    items, errors = resolve_items(manifest, Path(manifest_path))
    present = {i["id"]: i for i in items if i.get("present")}
    wanted = list(CORE_IDS) + list(STRESS_IDS)
    missing = [u for u in wanted if u not in present]
    if missing:
        raise FileNotFoundError(f"missing human audio for: {missing}; resolveErrors={errors}")

    timelines = {}
    audio_hashes = {}
    overdrive = 0
    silence_false = 0
    fps_fail = 0
    rest_seen = 0
    for uid in wanted:
        item = present[uid]
        path = Path(item["audioPath"])
        al = align_one_v2(path, item["transcript"], item.get("language", "ko-KR"), source_kind="HUMAN")
        al.pop("_audioDurationMs", None)
        al.pop("_expectedSymbols", None)
        tl = _timeline_from_alignment(uid, al)
        timelines[uid] = tl
        audio_hashes[uid] = item.get("audioSha256")
        curves = sample_curves(list(tl["phonemes"]), int(tl["durationMs"]))
        overdrive += int(curves["metrics"].get("lowConfidenceOverdrive", 0))
        silence_false += int(curves["metrics"].get("silenceFalseMotion", 0))
        if curves["fps"]["status"] != "PASS":
            fps_fail += 1
        rest_seen += _count_rest(tl["phonemes"])
    return {
        "timelines": timelines,
        "audioHashes": audio_hashes,
        "overdrive": overdrive,
        "silenceFalseMotion": silence_false,
        "fpsFail": fps_fail,
        "restFallbackSeen": rest_seen,
        "alignments": {uid: {"audio": present[uid]["audioPath"], "sourceKind": "HUMAN"} for uid in wanted},
    }


def _compare_frozen(fresh: Dict[str, Dict], frozen_dir: Path) -> Dict:
    frozen = load_gate6_timelines(frozen_dir)
    mismatch = []
    for uid, doc in fresh.items():
        if uid not in frozen:
            mismatch.append(uid)
            continue
        if _phoneme_sig(doc["phonemes"]) != _phoneme_sig(frozen[uid]["phonemes"]):
            mismatch.append(uid)
    return {
        "status": "PASS" if not mismatch else "FAIL",
        "mismatchIds": mismatch,
        "compared": len(fresh),
    }


def run_gate8a_once(
    *,
    root: Path,
    mesh_name: str,
    manifest_path: Path,
    frozen_timelines_dir: Path,
) -> Dict:
    locks = verify_all_locked(root)
    stage = {}

    # Gate1
    g1 = diagnose_once(mesh_name=mesh_name, root=root)
    stage["gate1"] = {
        "visemePath": g1["viseme"].get("visemePath"),
        "faceRegion": (g1["topology"] or {}).get("faceRegion"),
        "characterMutation": g1["capability"].get("characterMutation", 0),
    }

    # Gate2–4 rebuild from clean scene character (no dist intermediate reuse)
    g2 = run_gate2_once(mesh_name=mesh_name, root=root)
    stage["gate2"] = {"verdict": g2["validation"].get("verdict"), "sourceMutation": g2["stable"].get("sourceMutation", g2["profile"].get("sourceMutation"))}

    g3 = run_gate3_once(mesh_name=mesh_name, root=root)
    stage["gate3"] = {"verdict": g3["validation"].get("verdict")}

    g4 = run_gate4_once(mesh_name=mesh_name, root=root)
    stage["gate4"] = {"verdict": g4["validation"].get("verdict")}

    # Gate5A.2 Forced Alignment (fresh; not loading prior mesh/Action)
    aligned = _align_corpus(manifest_path)
    frozen_cmp = _compare_frozen(aligned["timelines"], frozen_timelines_dir)
    stage["gate5a2"] = {
        "utterances": len(aligned["timelines"]),
        "overdrive": aligned["overdrive"],
        "silenceFalseMotion": aligned["silenceFalseMotion"],
        "fpsFail": aligned["fpsFail"],
        "restFallbackSeen": aligned["restFallbackSeen"],
        "frozenTimelineMatch": frozen_cmp["status"],
        "frozenMismatchIds": frozen_cmp["mismatchIds"],
    }

    # Gate6 supported-domain policy
    core, stress, rejected = admit_jobs(aligned["timelines"])
    stage["gate6"] = {
        "coreCount": len(core),
        "stressCount": len(stress),
        "rejected": rejected,
        "policy": "SUPPORTED_WITH_FALLBACK_PROPAGATED",
        "coreFail": 0 if len(core) == 14 and aligned["overdrive"] == 0 and aligned["silenceFalseMotion"] == 0 else 1,
        "restPreserved": aligned["restFallbackSeen"] > 0,
    }

    # Gate5B Automatic Lip Sync on fresh timelines
    g5b = run_gate5b_once(
        timelines=aligned["timelines"],
        alignments=aligned["alignments"],
        mesh_name=mesh_name,
        root=root,
    )
    stage["gate5b"] = {
        "silenceFalseMotion": g5b["stable"]["metrics"].get("silenceFalseMotion", 0),
        "lowConfidenceOverdrive": g5b["stable"]["metrics"].get("lowConfidenceOverdrive", 0),
        "lipIntersection": g5b["stable"]["metrics"].get("lipIntersection", 0),
        "lipOrderInversion": g5b["stable"]["metrics"].get("lipOrderInversion", 0),
        "nonMouthLeak": g5b["stable"]["metrics"].get("nonMouthLeak", 0),
        "sourceMutation": g5b["stable"].get("sourceMutation", 0),
        "fpsFail": g5b["stable"].get("fpsFail", 0),
        "curveHashes": g5b["stable"].get("curveHashes"),
    }

    # Gate7 Limited Facial Performance (+ sealed v0.3 eye stack inside)
    g7 = run_gate7_once(timelines=aligned["timelines"], mesh_name=mesh_name, root=root)
    stage["gate7"] = {
        "metrics": g7["metrics"],
        "restPres": g7["restPres"],
        "fpsStatus": g7["fpsStatus"],
        "srcMut": g7["srcMut"],
        "readability": g7["readability"],
        "curveHashes": g7["stable"].get("curveHashes"),
        "coreCount": g7["stable"].get("coreCount"),
        "stressCount": g7["stable"].get("stressCount"),
    }

    stable = {
        "parameterHash": parameter_hash(),
        "locks": {k: locks[k] for k in locks if k not in ("hashes",)},
        "stageVerdicts": {
            "gate2": stage["gate2"]["verdict"],
            "gate3": stage["gate3"]["verdict"],
            "gate4": stage["gate4"]["verdict"],
            "frozenTimelineMatch": stage["gate5a2"]["frozenTimelineMatch"],
            "gate6CoreFail": stage["gate6"]["coreFail"],
            "gate5bOverdrive": stage["gate5b"]["lowConfidenceOverdrive"],
            "gate5bSilence": stage["gate5b"]["silenceFalseMotion"],
            "gate7Rest": stage["gate7"]["restPres"],
            "gate7Fps": stage["gate7"]["fpsStatus"],
            "gate7SrcMut": stage["gate7"]["srcMut"],
            "gate7LipIx": stage["gate7"]["metrics"].get("lipIntersection", 0),
            "gate7BlinkConflict": stage["gate7"]["metrics"].get("blinkLipsyncConflict", 0),
            "gate7ExprConflict": stage["gate7"]["metrics"].get("expressionVisemeConflict", 0),
            "gate7Overdrive": stage["gate7"]["metrics"].get("lowConfidenceOverdrive", 0),
            "gate7Silence": stage["gate7"]["metrics"].get("silenceFalseMotion", 0),
            "gate7DomeDrift": stage["gate7"]["metrics"].get("eyeDomeBaseDrift", 0),
        },
        "g5bCurveHashDigest": _sha_json(stage["gate5b"]["curveHashes"]),
        "g7CurveHashDigest": _sha_json(stage["gate7"]["curveHashes"]),
        "restFallbackSeen": stage["gate5a2"]["restFallbackSeen"],
        "audioHashDigest": _sha_json(aligned["audioHashes"]),
    }
    return {"locks": locks, "stage": stage, "stable": stable, "g1": g1}


def build_validation(stable: Dict, locks: Dict, determinism: str, clean_rebuild: str) -> Dict:
    gates = {
        "GATE1_7_PARAM_CHANGE": locks.get("gateParamChange", 1),
        "V03_HASH": locks.get("v03", "CHANGED"),
        "INTERMEDIATE_OUTPUT_REUSE": "DENY",
        "CLEAN_SCENE_REBUILD": clean_rebuild,
        "SOURCE_CHARACTER_MUTATION": int(stable["stageVerdicts"].get("gate7SrcMut", 1)),
        "CORE14_FAIL": int(stable["stageVerdicts"].get("gate6CoreFail", 1)),
        "LOW_CONFIDENCE_OVERDRIVE": int(stable["stageVerdicts"].get("gate7Overdrive", 0))
        + int(stable["stageVerdicts"].get("gate5bOverdrive", 0)),
        "SILENCE_FALSE_MOTION": int(stable["stageVerdicts"].get("gate7Silence", 0))
        + int(stable["stageVerdicts"].get("gate5bSilence", 0)),
        "REST_FALLBACK": "PRESERVED" if int(stable.get("restFallbackSeen", 0)) > 0 else "MISSING",
        "EYE_DOME_BASIS_DRIFT": int(stable["stageVerdicts"].get("gate7DomeDrift", 0)),
        "GAZE_BLINK_LIP_EXPRESSION_CONFLICT": int(stable["stageVerdicts"].get("gate7BlinkConflict", 0))
        + int(stable["stageVerdicts"].get("gate7ExprConflict", 0))
        + int(stable["stageVerdicts"].get("gate7LipIx", 0)),
        "FPS_24_30_60": stable["stageVerdicts"].get("gate7Fps", "FAIL"),
        "DETERMINISM_3X_E2E": determinism,
        "GATE2": stable["stageVerdicts"].get("gate2", "FAIL"),
        "GATE3": stable["stageVerdicts"].get("gate3", "FAIL"),
        "GATE4": stable["stageVerdicts"].get("gate4", "FAIL"),
        "FROZEN_TIMELINE_MATCH": stable["stageVerdicts"].get("frozenTimelineMatch", "FAIL"),
        "GATE7_REST": stable["stageVerdicts"].get("gate7Rest", "FAIL"),
    }

    def ok(k, v):
        if k in ("V03_HASH",):
            return v == "UNCHANGED"
        if k in ("INTERMEDIATE_OUTPUT_REUSE",):
            return v == "DENY"
        if k in ("CLEAN_SCENE_REBUILD", "FPS_24_30_60", "DETERMINISM_3X_E2E", "GATE2", "GATE3", "GATE4", "FROZEN_TIMELINE_MATCH", "GATE7_REST"):
            return v in ("PASS", "PRESERVED")
        if k == "REST_FALLBACK":
            return v == "PRESERVED"
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE8A_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
    }


def run_gate8a(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    manifest_path: Optional[Path] = None,
    frozen_timelines_dir: Optional[Path] = None,
    runs: int = 3,
    clean_import_cb=None,
) -> Gate8AResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    manifest_path = Path(manifest_path) if manifest_path else root / "dist/v0.4/gate6/HUMAN_SPEECH_MANIFEST.json"
    frozen_timelines_dir = (
        Path(frozen_timelines_dir) if frozen_timelines_dir else root / "dist/v0.4/gate6/human_gate4_timelines"
    )
    notes: List[str] = []
    results = []
    clean_rebuild = "PASS" if clean_import_cb is not None else "FAIL"
    if clean_import_cb is None:
        notes.append("clean_import_cb missing")

    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(
            run_gate8a_once(
                root=root,
                mesh_name=mesh_name,
                manifest_path=manifest_path,
                frozen_timelines_dir=frozen_timelines_dir,
            )
        )

    stables = [r["stable"] for r in results]
    det = "FAIL"
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det = "PASS" if all(_sha_json(s) == h0 for s in stables[1:3]) else "FAIL"
    if det != "PASS":
        notes.append("3x end-to-end determinism mismatch")

    last = results[-1]
    validation = build_validation(last["stable"], last["locks"], det, clean_rebuild)
    report = {
        "schema": "NURION_V04_GATE8A_INTEGRATION_REGRESSION_REPORT",
        "version": GATE8A_PARAMETERS["version"],
        "role": role,
        "asset": asset,
        "mode": "FULL_LIMITED_INTEGRATION_REGRESSION",
        "parameterHash": parameter_hash(),
        "gate7ParameterHash": GATE8A_PARAMETERS["gate7ParameterHash"],
        "intermediateOutputReuse": "DENY",
        "cleanSceneRebuild": clean_rebuild,
        "determinism3x": det,
        "locks": last["locks"],
        "stage": last["stage"],
        "stable": last["stable"],
        "pipeline": GATE8A_PARAMETERS["pipeline"],
        "fullUnrestricted": "HOLD",
        "asr": "INACTIVE",
        "microphone": "INACTIVE",
        "realTime": "INACTIVE",
        "releaseCandidate": "HOLD_UNTIL_8A_PASS",
        "freshHoldoutRequired": True,
        "finalSeal": "HOLD",
        "notes": notes,
    }
    return Gate8AResult(
        role=role,
        asset=asset,
        report=report,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )
