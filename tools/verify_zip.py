import zipfile
from pathlib import Path

zip_path = Path(__file__).resolve().parents[1] / "dist" / "NURION_Character_Landmarker_v0.1.0.zip"
with zipfile.ZipFile(zip_path, "r") as zf:
    names = zf.namelist()
    init_text = zf.read("nurion_character_landmarker/__init__.py").decode("utf-8")

print("entries", len(names))
print("bl_info_blender_5_0_0", '"blender": (5, 0, 0)' in init_text)
for item in [
    "nurion_character_landmarker/examples/nurion-character-profile.json",
    "nurion_character_landmarker/reports/practical-smoke-report.json",
    "nurion_character_landmarker/reports/VALIDATION_STATUS.json",
]:
    print(item, "YES" if item in names else "NO")
