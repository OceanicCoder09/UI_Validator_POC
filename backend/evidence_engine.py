import os
import sys
import json
import pathlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# ==============================================================================
# EVIDENCE ENGINE ARCHITECTURE: PROVENANCE-PRESERVING PHYSICAL EVALUATORS
# ==============================================================================

@dataclass
class EvidenceResult:
    category: str
    evidence_status: str  # STRONG_EVIDENCE, MODERATE_EVIDENCE, WEAK_EVIDENCE, NO_EVIDENCE, VISUALLY_UNSUPPORTED
    evidence_strength: float  # Normalized continuous strength 0.0 - 1.0 (or -1.0 if unsupported)
    measurements: Dict[str, Any]
    supporting_elements: List[Dict[str, Any]]
    provenance: Dict[str, str]  # DIRECTLY_MEASURED, DERIVED_FROM_MEASUREMENT, UNAVAILABLE, VISUALLY_UNSUPPORTED
    unavailable_reasons: List[str]
    competing_evidence: List[str]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class MisalignmentEvidenceEvaluator:
    """
    Evaluates physical evidence for structural misalignment (column anchor breaks,
    intra-column variance, directional incoherence, and unexplained residual drift).
    """
    def evaluate(self, case_evidence: Dict[str, Any]) -> EvidenceResult:
        mov = case_evidence.get("movement_pattern", {})
        mis = case_evidence.get("misalignment_v2", {})
        
        col_break = mov.get("max_column_anchor_break_px")
        col_dx_std = mov.get("max_column_dx_std")
        res_disp = mov.get("max_residual_disp_px")
        indep_frac = mov.get("fraction_independently_displaced")
        dir_coherence = mov.get("movement_direction_coherence")
        reflow_ratio = mov.get("reflow_displacement_ratio")
        
        measurements = {
            "max_column_anchor_break_px": col_break,
            "max_column_dx_std": col_dx_std,
            "max_residual_disp_px": res_disp,
            "fraction_independently_displaced": indep_frac,
            "movement_direction_coherence": dir_coherence,
            "reflow_displacement_ratio": reflow_ratio
        }
        
        provenance = {}
        for k, v in measurements.items():
            provenance[k] = "DIRECTLY_MEASURED" if v is not None else "UNAVAILABLE"
            
        unavailable_reasons = []
        if col_break is None:
            unavailable_reasons.append("Insufficient matched element pairs aligned in ENU baseline to evaluate column anchor.")
            
        # Determine evidence status and continuous strength based purely on physical measurements
        if col_break is not None and res_disp is not None and indep_frac is not None:
            # Strength continuous calculation: normalized combination of column anchor break and residual drift
            strength = min(1.0, (col_break / 120.0) * 0.5 + (res_disp / 150.0) * 0.3 + (indep_frac) * 0.2)
            if col_break >= 40.0 and res_disp >= 30.0 and indep_frac >= 0.20:
                status = "STRONG_EVIDENCE"
            elif col_break >= 15.0 or res_disp >= 15.0:
                status = "MODERATE_EVIDENCE"
            elif col_break > 0.0 or res_disp > 0.0:
                status = "WEAK_EVIDENCE"
            else:
                status = "NO_EVIDENCE"
        else:
            status = "NO_EVIDENCE"
            strength = 0.0
            
        # Identify supporting element displacement items
        supporting_elements = []
        top_disp = mis.get("top_10_displaced_elements", [])
        for el in top_disp[:5]:
            supporting_elements.append({
                "enu_bbox": el.get("enu_bbox"),
                "loc_bbox": el.get("loc_bbox"),
                "corrected_dx": el.get("corrected_dx"),
                "corrected_dy": el.get("corrected_dy"),
                "disp_magnitude": el.get("displacement_magnitude")
            })
            
        competing_evidence = []
        if reflow_ratio is not None and reflow_ratio >= 0.70:
            competing_evidence.append(f"High reflow explanation ratio ({reflow_ratio*100:.1f}%): displacement is largely preceded by text growth.")
            
        return EvidenceResult(
            category="Misalignment",
            evidence_status=status,
            evidence_strength=round(float(strength), 3),
            measurements=measurements,
            supporting_elements=supporting_elements,
            provenance=provenance,
            unavailable_reasons=unavailable_reasons,
            competing_evidence=competing_evidence,
            notes="Physical structural alignment evaluation based on column anchor consistency and residual drift."
        )

class OverlapEvidenceEvaluator:
    """
    Evaluates physical evidence for bounding-box collisions, multi-axis intrusions,
    and sibling gap collapse.
    """
    def evaluate(self, case_evidence: Dict[str, Any]) -> EvidenceResult:
        ov = case_evidence.get("overlap_v2", {})
        
        max_inter = ov.get("max_intersection_area_px2")
        total_inter = ov.get("total_intersection_area_px2")
        h_intrusion = ov.get("max_horizontal_intrusion_px")
        v_intrusion = ov.get("max_vertical_intrusion_px")
        gap_collapse = ov.get("max_gap_collapse_px")
        gaps_le_zero = ov.get("num_gaps_became_non_positive")
        unexplained_coll = ov.get("residual_unexplained_collisions_count")
        
        measurements = {
            "max_intersection_area_px2": max_inter,
            "total_intersection_area_px2": total_inter,
            "max_horizontal_intrusion_px": h_intrusion,
            "max_vertical_intrusion_px": v_intrusion,
            "max_gap_collapse_px": gap_collapse,
            "num_gaps_became_non_positive": gaps_le_zero,
            "residual_unexplained_collisions_count": unexplained_coll
        }
        
        provenance = {}
        for k, v in measurements.items():
            provenance[k] = "DIRECTLY_MEASURED" if v is not None else "UNAVAILABLE"
            
        unavailable_reasons = []
        if max_inter is None:
            unavailable_reasons.append("No matched sibling bounding box pairs within spatial proximity.")
            
        # Strength calculation
        if total_inter is not None and h_intrusion is not None:
            strength = min(1.0, (total_inter / 5000.0) * 0.6 + (h_intrusion / 80.0) * 0.4)
            if (max_inter and max_inter > 0) and ((h_intrusion and h_intrusion >= 10) or (v_intrusion and v_intrusion >= 10)):
                status = "STRONG_EVIDENCE"
            elif (max_inter and max_inter > 0) or (gap_collapse and gap_collapse >= 15):
                status = "MODERATE_EVIDENCE"
            elif gap_collapse and gap_collapse > 0:
                status = "WEAK_EVIDENCE"
            else:
                status = "NO_EVIDENCE"
        else:
            status = "NO_EVIDENCE"
            strength = 0.0
            
        supporting_elements = []
        for col in ov.get("detailed_collisions", [])[:5]:
            supporting_elements.append({
                "element_1": col.get("element_1"),
                "element_2": col.get("element_2"),
                "collision_type": col.get("collision_type"),
                "intersection_area_px2": col.get("intersection_area_px2"),
                "h_intrusion_px": col.get("h_intrusion_px"),
                "v_intrusion_px": col.get("v_intrusion_px"),
                "explained_by_reflow": col.get("explained_by_reflow")
            })
            
        competing_evidence = []
        reflow_exp_count = ov.get("reflow_explained_collisions_count", 0)
        if reflow_exp_count > 0:
            competing_evidence.append(f"{reflow_exp_count} collision(s) explained by upstream text width growth.")
            
        return EvidenceResult(
            category="Overlapping",
            evidence_status=status,
            evidence_strength=round(float(strength), 3),
            measurements=measurements,
            supporting_elements=supporting_elements,
            provenance=provenance,
            unavailable_reasons=unavailable_reasons,
            competing_evidence=competing_evidence,
            notes="Geometric boundary collision and intrusion evaluation across matched siblings."
        )

class TruncationEvidenceEvaluator:
    """
    Evaluates physical evidence for text truncation, container boundary overflow,
    glyph edge clipping, and verified localized ellipsis.
    """
    def evaluate(self, case_evidence: Dict[str, Any]) -> EvidenceResult:
        tr = case_evidence.get("truncation_v2", {})
        
        verified_ellipsis = tr.get("verified_ellipsis_elements_count")
        max_overflow = tr.get("max_overflow_px")
        clipping_elems = tr.get("genuine_clipping_elements_count")
        container_accom = tr.get("container_expanded_accommodated_count")
        text_expansion = tr.get("max_text_expansion_px")
        min_margin = tr.get("min_right_margin_px")
        
        measurements = {
            "verified_ellipsis_elements_count": verified_ellipsis,
            "max_overflow_px": max_overflow,
            "clipping_elements_count": clipping_elems,
            "container_expanded_accommodated_count": container_accom,
            "max_text_expansion_px": text_expansion,
            "min_right_margin_px": min_margin
        }
        
        provenance = {}
        for k, v in measurements.items():
            provenance[k] = "DIRECTLY_MEASURED" if v is not None else "UNAVAILABLE"
            
        unavailable_reasons = []
        if verified_ellipsis is None:
            unavailable_reasons.append("No matched text elements available for boundary fit evaluation.")
            
        # Strength calculation
        ellipsis_val = verified_ellipsis or 0
        overflow_val = max_overflow or 0
        clipping_val = clipping_elems or 0
        
        strength = min(1.0, (ellipsis_val * 0.6) + (overflow_val / 50.0) * 0.3 + (clipping_val * 0.3))
        if ellipsis_val > 0 or overflow_val > 0 or clipping_val > 0:
            status = "STRONG_EVIDENCE"
        elif text_expansion and text_expansion >= 20.0 and (container_accom or 0) == 0:
            status = "MODERATE_EVIDENCE"
        elif text_expansion and text_expansion > 0.0:
            status = "WEAK_EVIDENCE"
        else:
            status = "NO_EVIDENCE"
            
        supporting_elements = []
        for el in tr.get("detailed_text_elements", [])[:5]:
            if el.get("is_clipped") or el.get("verified_new_ellipsis") or (el.get("text_expansion_px") or 0) >= 15:
                supporting_elements.append({
                    "element_id": el.get("element_id"),
                    "text_enu": el.get("text_enu"),
                    "text_loc": el.get("text_loc"),
                    "text_expansion_px": el.get("text_expansion_px"),
                    "overflow_px": el.get("overflow_px"),
                    "verified_new_ellipsis": el.get("verified_new_ellipsis"),
                    "element_state": el.get("element_state")
                })
                
        competing_evidence = []
        if container_accom and container_accom > 0:
            competing_evidence.append(f"{container_accom} text element(s) accommodated by dynamic container widening.")
            
        return EvidenceResult(
            category="Truncation",
            evidence_status=status,
            evidence_strength=round(float(strength), 3),
            measurements=measurements,
            supporting_elements=supporting_elements,
            provenance=provenance,
            unavailable_reasons=unavailable_reasons,
            competing_evidence=competing_evidence,
            notes="Text boundary containment, physical overflow, and verified ellipsis evaluation."
        )

class UntranslationEvidenceEvaluator:
    """
    Evaluates physical evidence for preserved user-facing English text with technical/brand filtering.
    """
    def evaluate(self, case_evidence: Dict[str, Any]) -> EvidenceResult:
        un = case_evidence.get("untranslation_v2", {})
        
        genuine_untrans = un.get("genuine_untranslated_strings_count")
        latin_words = un.get("total_latin_words_preserved")
        en_chars = un.get("total_english_chars_preserved")
        fp_tech_tokens = un.get("potential_fp_technical_brand_count")
        
        measurements = {
            "genuine_untranslated_strings_count": genuine_untrans,
            "total_latin_words_preserved": latin_words,
            "total_english_chars_preserved": en_chars,
            "potential_fp_technical_brand_count": fp_tech_tokens
        }
        
        provenance = {}
        for k, v in measurements.items():
            provenance[k] = "DIRECTLY_MEASURED" if v is not None else "UNAVAILABLE"
            
        unavailable_reasons = []
        if genuine_untrans is None:
            unavailable_reasons.append("No matched text elements available for lexical audit.")
            
        gen_val = genuine_untrans or 0
        words_val = latin_words or 0
        
        strength = min(1.0, (gen_val / 5.0) * 0.5 + (words_val / 10.0) * 0.5)
        if gen_val >= 1 and words_val >= 2:
            status = "STRONG_EVIDENCE"
        elif gen_val >= 1 or words_val >= 1:
            status = "MODERATE_EVIDENCE"
        elif fp_tech_tokens and fp_tech_tokens > 0:
            status = "WEAK_EVIDENCE"
        else:
            status = "NO_EVIDENCE"
            
        supporting_elements = []
        for el in un.get("genuine_untranslated_elements", [])[:5]:
            supporting_elements.append({
                "element_id": el.get("element_id"),
                "enu_text": el.get("enu_text"),
                "loc_text": el.get("loc_text"),
                "preserved_words": el.get("preserved_english_words"),
                "latin_char_ratio": el.get("latin_char_ratio")
            })
            
        competing_evidence = []
        if fp_tech_tokens and fp_tech_tokens > 0:
            competing_evidence.append(f"{fp_tech_tokens} universal non-translatable token(s) (brands, units, acronyms, DWG) filtered.")
            
        return EvidenceResult(
            category="Untranslation",
            evidence_status=status,
            evidence_strength=round(float(strength), 3),
            measurements=measurements,
            supporting_elements=supporting_elements,
            provenance=provenance,
            unavailable_reasons=unavailable_reasons,
            competing_evidence=competing_evidence,
            notes="Lexical preservation audit differentiating user-facing UI text from universal technical terms."
        )

class RepeatedHotkeyEvidenceEvaluator:
    """
    Evaluates physical evidence for duplicate keyboard mnemonic accelerators.
    Explicitly preserves VISUALLY_UNSUPPORTED status for standard plain OCR.
    """
    def evaluate(self, case_evidence: Dict[str, Any]) -> EvidenceResult:
        hk = case_evidence.get("hotkey_v2", {})
        
        conflicts = hk.get("hotkey_conflict_count")
        duplicates = hk.get("duplicate_accelerators_count")
        total_accs = hk.get("total_accelerators_detected")
        
        measurements = {
            "hotkey_conflict_count": conflicts,
            "duplicate_accelerators_count": duplicates,
            "total_accelerators_detected": total_accs
        }
        
        # Mnemonic accelerators are visually unobservable via plain OCR because Win32 uses font underlines
        status = "VISUALLY_UNSUPPORTED"
        strength = -1.0
        
        provenance = {
            "hotkey_conflict_count": "VISUALLY_UNSUPPORTED",
            "duplicate_accelerators_count": "VISUALLY_UNSUPPORTED",
            "total_accelerators_detected": "VISUALLY_UNSUPPORTED"
        }
        
        unavailable_reasons = [
            "Native Win32 keyboard mnemonics are rendered as font underlines or compiled in dialog resource tables (.rc), which are stripped by standard plain OCR."
        ]
        
        supporting_elements = []
        competing_evidence = []
        
        return EvidenceResult(
            category="Repeated hotkey",
            evidence_status=status,
            evidence_strength=strength,
            measurements=measurements,
            supporting_elements=supporting_elements,
            provenance=provenance,
            unavailable_reasons=unavailable_reasons,
            competing_evidence=competing_evidence,
            notes="Native mnemonic accelerator evaluation is visually unobservable from standard flat OCR screenshots."
        )

# ==============================================================================
# UNIFIED EVIDENCE ENGINE
# ==============================================================================

class EvidenceEngine:
    """
    Unified Evidence Engine orchestrating five independent category evaluators.
    Never forces mutual exclusivity; evaluates all five defect mechanisms simultaneously.
    """
    def __init__(self):
        self.evaluators = {
            "Misalignment": MisalignmentEvidenceEvaluator(),
            "Overlapping": OverlapEvidenceEvaluator(),
            "Truncation": TruncationEvidenceEvaluator(),
            "Untranslation": UntranslationEvidenceEvaluator(),
            "Repeated hotkey": RepeatedHotkeyEvidenceEvaluator()
        }

    def evaluate_case(self, case_id: int, case_evidence: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for cat_name, evaluator in self.evaluators.items():
            results[cat_name] = evaluator.evaluate(case_evidence).to_dict()
            
        return {
            "case_id": case_id,
            "product": case_evidence.get("product", "Unknown"),
            "folder": case_evidence.get("folder", "Unknown"),
            "language": case_evidence.get("language", "Unknown"),
            "ground_truth": case_evidence.get("ground_truth", "Unknown"),
            "evidence_results": results
        }
