"""Prepare Manual GT annotation scenes for seed + holdout (no GT coordinates)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_v07_manual_gt_annotation_scene_prepare.py"
OUT = ROOT / "dist" / "v0.7" / "manual_gt"
SCENES = OUT / "scenes"
MANUAL_GT_PARAM_HASH = "4375a4bc9c08e72edd809c0112e3e099b563c4a35cfc351ee4b34fe1371e1f2c"

ASSETS = [
    {
        "label": "ai-aba.15",
        "zip": ROOT / "dist/v0.4/gate8c/inbox/ai-aba.15.zip",
        "expectedZipSha256": "535da28538c13153a3a07c2a89a23287dbfb75634b3fae34321d172c2c705c85",
        "expectedFbxSha256": "552f43cf01cfdcd07728ad62eaf48d96421c4134306fd014b357eecff8b98330",
        "role": "SEED",
    },
    {
        "label": "Jjajang_Nara_Chef",
        "zip": ROOT / "Meshy_AI_Jjajang_Nara_Chef_Uni_0812002117_texture_fbx.zip",
        "expectedZipSha256": "2f92d6b3dec96c4f940d8642e749ea52e661b11e6f770a7cf8aad424ba5a5949",
        "expectedFbxSha256": "02da3923b434a3b815e3ed8c83a4ab9c2b6dbcabb7094543e2c3c8d3d36b67ff",
        "role": "HOLDOUT",
    },
]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _stable_hash(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    if not BLENDER.is_file():
        raise SystemExit(f"Blender not found: {BLENDER}")
    if not SCRIPT.is_file():
        raise SystemExit(f"missing script: {SCRIPT}")

    track = json.loads((OUT / "V07_MANUAL_GT_TRACK_STATUS.json").read_text(encoding="utf-8"))
    if track.get("parameterHash") != MANUAL_GT_PARAM_HASH:
        raise SystemExit("manual GT parameter hash mismatch")
    if not track.get("protocolLocked"):
        raise SystemExit("protocol not locked")

    SCENES.mkdir(parents=True, exist_ok=True)
    results = []
    failures = []

    for asset in ASSETS:
        label = asset["label"]
        zpath = asset["zip"]
        if not zpath.is_file():
            # Fallback for holdout inbox copy
            alt = ROOT / "dist/v0.7/gate7/inbox" / zpath.name
            if alt.is_file():
                zpath = alt
            else:
                failures.append({"label": label, "error": f"missing zip: {asset['zip']}"})
                continue
        zip_sha = _sha(zpath)
        if zip_sha != asset["expectedZipSha256"]:
            failures.append({"label": label, "error": f"zip sha mismatch {zip_sha}"})
            continue

        out_dir = SCENES / label
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(SCRIPT),
            "--",
            "--zip",
            str(zpath),
            "--label",
            label,
            "--out-dir",
            str(out_dir),
            "--expected-zip-sha256",
            asset["expectedZipSha256"],
            "--expected-fbx-sha256",
            asset["expectedFbxSha256"],
        ]
        print("RUN", label, flush=True)
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        (out_dir / "blender_stdout.txt").parent.mkdir(parents=True, exist_ok=True)
        (out_dir / "blender_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (out_dir / "blender_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        receipt_path = out_dir / "V07_MANUAL_GT_ANNOTATION_SCENE_RECEIPT.json"
        if proc.returncode != 0 or not receipt_path.is_file():
            failures.append(
                {
                    "label": label,
                    "error": f"blender exit {proc.returncode}",
                    "tail": (proc.stderr or proc.stdout or "")[-2000:],
                }
            )
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        results.append(
            {
                "label": label,
                "role": asset["role"],
                "status": receipt.get("status"),
                "gtPointsPlaced": receipt.get("gtPointsPlaced", -1),
                "gtLeak": receipt.get("leakGuard", {}).get("gtLeak"),
                "worldMatrixSha256": receipt["locks"]["worldMatrixSha256"],
                "meshGeometrySha256": receipt["locks"]["meshGeometrySha256"],
                "evidenceReceiptSha256": receipt["locks"]["evidenceReceiptSha256"],
                "sourceZipSha256": receipt["source"]["sourceZipSha256"],
                "sourceFbxSha256": receipt["source"]["sourceFbxSha256"],
                "blendFile": str((out_dir / receipt["blendFile"]).relative_to(ROOT)).replace("\\", "/"),
                "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
            }
        )

    all_ok = len(results) == len(ASSETS) and not failures and all(
        r["status"] == "SCENE_PREPARED_WAITING_FOR_MANUAL_ANNOTATIONS"
        and r["gtPointsPlaced"] == 0
        and r["gtLeak"] == "PASS"
        for r in results
    )

    prepare_status = {
        "schema": "NURION_V07_MANUAL_GT_ANNOTATION_SCENE_PREPARE_STATUS",
        "track": "NURION Homepage Performance Rig v0.7 Manual GT Accuracy Track",
        "command": "NURION Homepage Performance Rig v0.7 Manual GT Annotation Scene Prepare GO",
        "manualGtParameterHash": MANUAL_GT_PARAM_HASH,
        "status": "PASS" if all_ok else "FAIL",
        "gtPointsPlacedTotal": sum(r.get("gtPointsPlaced", 0) for r in results),
        "coordinateInvention": "DENY",
        "autoAnnotation": "DENY",
        "estimatedCoordinates": "DENY",
        "accuracy": "NOT_VALIDATED",
        "finalSeal": "HOLD_FOR_MANUAL_GT",
        "production": "NO-GO",
        "sourceMutation": 0,
        "sealedBaselineMutation": 0,
        "assets": results,
        "failures": failures,
        "next": "AWAIT_MANUAL_ANNOTATOR_A_B_POINT_PLACEMENT_AND_SEAL",
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    prepare_status["prepareReceiptSha256"] = _stable_hash(
        {k: v for k, v in prepare_status.items() if k != "prepareReceiptSha256"}
    )
    _write(OUT / "V07_MANUAL_GT_ANNOTATION_SCENE_PREPARE_STATUS.json", prepare_status)

    # Update track status
    asset_map = {r["label"]: "SCENE_PREPARED_WAITING_FOR_MANUAL_GT" for r in results}
    for f in failures:
        asset_map[f["label"]] = "SCENE_PREPARE_FAILED"
    track.update(
        {
            "status": "IN_PROGRESS_SCENES_PREPARED_WAITING_FOR_MANUAL_ANNOTATIONS"
            if all_ok
            else "IN_PROGRESS_SCENE_PREPARE_FAILED",
            "assets": {
                "ai-aba.15": asset_map.get("ai-aba.15", track["assets"].get("ai-aba.15")),
                "Jjajang_Nara_Chef": asset_map.get("Jjajang_Nara_Chef", track["assets"].get("Jjajang_Nara_Chef")),
            },
            "annotationCompleted": 0,
            "accuracyEvaluationExecuted": False,
            "accuracy": "NOT_VALIDATED",
            "finalSeal": "HOLD_FOR_MANUAL_GT",
            "production": "NO-GO",
            "scenePrepare": prepare_status["status"],
            "scenePrepareReceipt": "V07_MANUAL_GT_ANNOTATION_SCENE_PREPARE_STATUS.json",
            "gtPointsPlacedTotal": prepare_status["gtPointsPlacedTotal"],
            "next": "AWAIT_MANUAL_ANNOTATOR_A_B_POINT_PLACEMENT_AND_SEAL"
            if all_ok
            else "FIX_SCENE_PREPARE_FAILURES",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    _write(OUT / "V07_MANUAL_GT_TRACK_STATUS.json", track)

    # Touch contract
    contract_path = OUT / "V07_MANUAL_GT_ACCURACY_TRACK_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["execution"] = track["status"]
    contract["annotationCompleted"] = 0
    contract["next"] = track["next"]
    contract["updatedAt"] = datetime.now(timezone.utc).isoformat()
    _write(contract_path, contract)

    print(json.dumps({"status": prepare_status["status"], "assets": len(results), "failures": len(failures)}, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
