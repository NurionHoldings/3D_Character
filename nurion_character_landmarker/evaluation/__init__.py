"""Evaluation-only utilities. Must not be imported by generation/correction paths."""

from .asset_eligibility import AssetEligibilityResult, evaluate_asset_eligibility

__all__ = ["AssetEligibilityResult", "evaluate_asset_eligibility"]
