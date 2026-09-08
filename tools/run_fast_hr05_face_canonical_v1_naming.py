#!/usr/bin/env python3
"""Build NURION FACE Canonical v1 naming table from Jake forensic inventory."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
FORENSIC = ROOT / "fast_track/working/meshy_silver_starlight/evidence/FAST-HR05_jake_forensic_report.json"
OUT = ROOT / "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
RECEIPT = ROOT / "fast_track/working/meshy_silver_starlight/evidence/FAST-HR05_face_canonical_v1_naming_receipt.json"

# Jake original -> (canonical, tier, legacy_pres list or None)
# tier: ESSENTIAL_V1 | V1_1 | HOLD
EXPLICIT = {
    # EYE essential
    "Eye_Blink_L": ("FACE_eyeBlinkLeft", "ESSENTIAL_V1", ["PRES_Blink_L"]),
    "Eye_Blink_R": ("FACE_eyeBlinkRight", "ESSENTIAL_V1", ["PRES_Blink_R"]),
    "Eye_Squint_L": ("FACE_eyeSquintLeft", "ESSENTIAL_V1", None),
    "Eye_Squint_R": ("FACE_eyeSquintRight", "ESSENTIAL_V1", None),
    "Eye_Wide_L": ("FACE_eyeWideLeft", "ESSENTIAL_V1", None),
    "Eye_Wide_R": ("FACE_eyeWideRight", "ESSENTIAL_V1", None),
    # BROW essential
    "Brow_Raise_Inner_L": ("FACE_browInnerUpLeft", "ESSENTIAL_V1", None),
    "Brow_Raise_Inner_R": ("FACE_browInnerUpRight", "ESSENTIAL_V1", None),
    "Brow_Raise_Outer_L": ("FACE_browOuterUpLeft", "ESSENTIAL_V1", None),
    "Brow_Raise_Outer_R": ("FACE_browOuterUpRight", "ESSENTIAL_V1", None),
    "Brow_Drop_L": ("FACE_browDownLeft", "ESSENTIAL_V1", None),
    "Brow_Drop_R": ("FACE_browDownRight", "ESSENTIAL_V1", None),
    # MOUTH essential
    "Mouth_Smile_L": ("FACE_mouthSmileLeft", "ESSENTIAL_V1", ["PRES_SmileMild"]),
    "Mouth_Smile_R": ("FACE_mouthSmileRight", "ESSENTIAL_V1", ["PRES_SmileMild"]),
    "Mouth_Frown_L": ("FACE_mouthFrownLeft", "ESSENTIAL_V1", None),
    "Mouth_Frown_R": ("FACE_mouthFrownRight", "ESSENTIAL_V1", None),
    "Mouth_Pucker": ("FACE_mouthPucker", "ESSENTIAL_V1", ["PRES_Viseme_O"]),
    "Mouth_Widen": ("FACE_mouthWiden", "ESSENTIAL_V1", ["PRES_Viseme_E"]),
    "Mouth_Open": ("FACE_mouthOpen", "ESSENTIAL_V1", ["PRES_JawOpen", "PRES_Viseme_A"]),
    "Mouth_Lips_Part": ("FACE_lipsPart", "ESSENTIAL_V1", None),
    "Mouth_Lips_Tight": ("FACE_lipsTight", "ESSENTIAL_V1", None),
    # CHEEK essential
    "Cheek_Raise_L": ("FACE_cheekRaiseLeft", "ESSENTIAL_V1", None),
    "Cheek_Raise_R": ("FACE_cheekRaiseRight", "ESSENTIAL_V1", None),
    # SPEECH essential
    "Mouth_Plosive": ("FACE_mouthPlosive", "ESSENTIAL_V1", ["PRES_Viseme_M"]),
    "Dental_Lip": ("FACE_dentalLip", "ESSENTIAL_V1", None),
    # V1.1
    "Mouth_Dimple_L": ("FACE_dimpleLeft", "V1_1", None),
    "Mouth_Dimple_R": ("FACE_dimpleRight", "V1_1", None),
}

# HOLD shapes get stable FACE_* names derived from Jake tokens for future unlock.
HOLD_CANONICAL = {
    "Affricate": "FACE_speechAffricate",
    "Brow_Raise_L": "FACE_browRaiseLeftCombined",
    "Brow_Raise_R": "FACE_browRaiseRightCombined",
    "Cheek_Blow_L": "FACE_cheekBlowLeft",
    "Cheek_Blow_R": "FACE_cheekBlowRight",
    "Cheek_Suck": "FACE_cheekSuck",
    "Explosive": "FACE_speechExplosive",
    "Eye_Blink": "FACE_eyeBlinkBoth",
    "Lip_Open": "FACE_lipsOpen",
    "Mouth_Blow": "FACE_mouthBlow",
    "Mouth_Bottom_Lip_Bite": "FACE_mouthBottomLipBite",
    "Mouth_Bottom_Lip_Down": "FACE_mouthBottomLipDown",
    "Mouth_Bottom_Lip_Trans": "FACE_mouthBottomLipTrans",
    "Mouth_Bottom_Lip_Under": "FACE_mouthBottomLipUnder",
    "Mouth_Down": "FACE_mouthDown",
    "Mouth_Frown": "FACE_mouthFrownBoth",
    "Mouth_L": "FACE_mouthShiftLeft",
    "Mouth_Lips_Jaw_Adjust": "FACE_mouthLipsJawAdjust",
    "Mouth_Lips_Open": "FACE_mouthLipsOpen",
    "Mouth_Lips_Tuck": "FACE_mouthLipsTuck",
    "Mouth_Pucker_Open": "FACE_mouthPuckerOpen",
    "Mouth_R": "FACE_mouthShiftRight",
    "Mouth_Skewer": "FACE_mouthSkewer",
    "Mouth_Smile": "FACE_mouthSmileBoth",
    "Mouth_Snarl_Lower_L": "FACE_mouthSnarlLowerLeft",
    "Mouth_Snarl_Lower_R": "FACE_mouthSnarlLowerRight",
    "Mouth_Snarl_Upper_L": "FACE_mouthSnarlUpperLeft",
    "Mouth_Snarl_Upper_R": "FACE_mouthSnarlUpperRight",
    "Mouth_Top_Lip_Under": "FACE_mouthTopLipUnder",
    "Mouth_Top_Lip_Up": "FACE_mouthTopLipUp",
    "Mouth_Up": "FACE_mouthUp",
    "Mouth_Widen_Sides": "FACE_mouthWidenSides",
    "Nose_Flank_Raise_L": "FACE_noseFlankRaiseLeft",
    "Nose_Flank_Raise_R": "FACE_noseFlankRaiseRight",
    "Nose_Flanks_Raise": "FACE_noseFlanksRaise",
    "Nose_Nostrils_Flare": "FACE_noseNostrilsFlare",
    "Nose_Scrunch": "FACE_noseScrunch",
    "Open": "FACE_speechOpen",
    "Tight": "FACE_speechTight",
    "Tight_O": "FACE_speechTightO",
    "Tongue_Curl_D": "FACE_tongueCurlDown",
    "Tongue_Curl_U": "FACE_tongueCurlUp",
    "Tongue_Lower": "FACE_tongueLower",
    "Tongue_Narrow": "FACE_tongueNarrow",
    "Tongue_Out": "FACE_tongueOut",
    "Tongue_Raise": "FACE_tongueRaise",
    "Tongue_up": "FACE_tongueUp",
    "Wide": "FACE_speechWide",
}


def main() -> int:
    forensic = json.loads(FORENSIC.read_text(encoding="utf-8"))
    shapes = forensic["uniqueShapeKeys"]
    rows = []
    missing = []
    for jake in shapes:
        if jake in EXPLICIT:
            canonical, tier, legacy = EXPLICIT[jake]
        elif jake in HOLD_CANONICAL:
            canonical, tier, legacy = HOLD_CANONICAL[jake], "HOLD", None
        else:
            missing.append(jake)
            continue
        rows.append(
            {
                "jakeOriginal": jake,
                "nurionCanonical": canonical,
                "tier": tier,
                "legacyPres": legacy or [],
            }
        )

    if missing:
        raise SystemExit(f"Unmapped Jake shapes: {missing}")

    legacy_index = {}
    for row in rows:
        for pres in row["legacyPres"]:
            legacy_index.setdefault(pres, []).append(row["nurionCanonical"])

    # Contract lock: SmileMild must stay dual-mapped and must not become PRES_Smile.
    if set(legacy_index.get("PRES_SmileMild", [])) != {"FACE_mouthSmileLeft", "FACE_mouthSmileRight"}:
        raise SystemExit("PRES_SmileMild mapping contract broken")

    table = {
        "schema": "NURION_FACE_CANONICAL_V1_NAMING_TABLE",
        "canonicalTarget": "NURION FACE Canonical v1",
        "sourceDonor": {
            "asset_role": "HR05 facial reference/donor",
            "product_use": False,
            "local_asset": "fast_track/assets/external/hr05_jake/Jake.fbx",
            "local_sha256": "b2fbef9f40a941cbb705d7cb01a1300e7f34aa6f29d4f58ae2083a447ac98468",
            "creator_attribution": "Canino3d",
        },
        "axes": [
            "jakeOriginal",
            "nurionCanonical",
            "tier(ESSENTIAL_V1|V1_1|HOLD)",
            "legacyPres",
        ],
        "counts": {
            "totalJakeShapes": len(rows),
            "ESSENTIAL_V1": sum(1 for r in rows if r["tier"] == "ESSENTIAL_V1"),
            "V1_1": sum(1 for r in rows if r["tier"] == "V1_1"),
            "HOLD": sum(1 for r in rows if r["tier"] == "HOLD"),
        },
        "legacyAdapterContract": {
            "PRES_JawOpen": ["FACE_mouthOpen"],
            "PRES_Blink_L": ["FACE_eyeBlinkLeft"],
            "PRES_Blink_R": ["FACE_eyeBlinkRight"],
            "PRES_SmileMild": ["FACE_mouthSmileLeft", "FACE_mouthSmileRight"],
            "PRES_Viseme_A": ["FACE_mouthOpen"],
            "PRES_Viseme_E": ["FACE_mouthWiden"],
            "PRES_Viseme_O": ["FACE_mouthPucker"],
            "PRES_Viseme_M": ["FACE_mouthPlosive"],
            "renamePresSmileMildToPresSmile": "DENY",
        },
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    receipt = {
        "receiptId": "FAST-HR05_FACE_CANONICAL_V1_NAMING_20260829T055000Z",
        "stage": "FAST-HR05_FACE_CANONICAL_V1_NAMING",
        "verdict": "PASS_NAMING_TABLE_LOCKED",
        "officialStartColor": "GREEN",
        "namingTable": str(OUT),
        "counts": table["counts"],
        "legacyAdapterContract": table["legacyAdapterContract"],
        "next": "Legacy Adapter implementation PRES_* ↔ FACE v1",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"table": str(OUT), "receipt": str(RECEIPT), "counts": table["counts"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
