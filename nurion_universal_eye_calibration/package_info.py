"""Package metadata embedded in RC.1 addon."""

VERSION = "0.3.0-rc.1"
PACKAGE_NAME = "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
RELEASE_CANDIDATE = True
SEALED = False
HOLDOUT = "WAITING"
FINAL_SEAL = "HOLD"

GATE_PARAM_HASHES = {
    "gate2": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "gate3": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
    "gate4a": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
    "gate4b": "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61",
    "gate5": "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e",
    "gate6": "4fc613deb0bc0e79d2b325354adc48ac3d7a73e87ea54af52a93bc477b6ab190",
}

DEFAULT_PRESET = "NATURAL"
SELECTABLE_PRESETS = ["NATURAL", "LUMINOUS", "AI_PREMIUM"]
TIERS = ["High", "Medium", "Low", "Fallback"]
