import os
import sys
import json
import pathlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.evidence_engine import EvidenceResult, EvidenceEngine
from backend.evidence_arbitrator import DiagnosticDecision

# ==============================================================================
# EVIDENCE ARBITRATION V2: CAUSAL PRECEDENCE HIERARCHY
# ==============================================================================

class CausalEvidenceArbitrator:
    """
    Arbitrates among the five independent EvidenceResult objects using a 3-tier
    causal precedence hierarchy:
      1. Root-Cause Lexical Precedence (Untranslation vs downstream spatial reflow)
      2. Sibling Collision vs Container-Internal Boundary Clipping (Overlapping vs Truncation)
      3. Structural Column Anchor Break vs Incidental Downstream Collision (Misalignment vs Overlap)
    """
    def __init__(self):
        pass

    def arbitrate(self, case_id: int, evidence_results: Dict[str, Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> DiagnosticDecision:
        meta = metadata or {}
        
        # Pull the 5 independent streams
        mis_res = evidence_results.get("Misalignment", {})
        ov_res = evidence_results.get("Overlapping", {})
        tr_res = evidence_results.get("Truncation", {})
        un_res = evidence_results.get("Untranslation", {})
        hk_res = evidence_results.get("Repeated hotkey", {})
        
        # ----------------------------------------------------------------------
        # EXTRACT PHYSICAL EVIDENCE MEASUREMENTS
        # ----------------------------------------------------------------------
        
        # 1. Misalignment measurements
        mis_m = mis_res.get("measurements", {})
        mis_raw_strength = mis_res.get("evidence_strength", 0.0)
        col_break = mis_m.get("max_column_anchor_break_px") or 0.0
        res_disp = mis_m.get("max_residual_disp_px") or 0.0
        col_dx_std = mis_m.get("max_column_dx_std") or 0.0
        indep_frac = mis_m.get("fraction_independently_displaced") or 0.0
        dir_coh = mis_m.get("movement_direction_coherence") or 1.0
        reflow_ratio = mis_m.get("reflow_displacement_ratio") or 0.0
        
        # 2. Overlapping measurements
        ov_m = ov_res.get("measurements", {})
        ov_raw_strength = ov_res.get("evidence_strength", 0.0)
        max_inter = ov_m.get("max_intersection_area_px2") or 0.0
        total_inter = ov_m.get("total_intersection_area_px2") or 0.0
        h_intrusion = ov_m.get("max_horizontal_intrusion_px") or 0.0
        v_intrusion = ov_m.get("max_vertical_intrusion_px") or 0.0
        gap_collapse = ov_m.get("max_gap_collapse_px") or 0.0
        gaps_le_zero = ov_m.get("num_gaps_became_non_positive") or 0
        unexplained_coll = ov_m.get("residual_unexplained_collisions_count") or 0
        
        # 3. Truncation measurements
        tr_m = tr_res.get("measurements", {})
        tr_raw_strength = tr_res.get("evidence_strength", 0.0)
        ellipsis_cnt = tr_m.get("verified_ellipsis_elements_count") or 0
        overflow_px = tr_m.get("max_overflow_px") or 0.0
        clipping_cnt = tr_m.get("clipping_elements_count") or 0
        container_accom = tr_m.get("container_expanded_accommodated_count") or 0
        min_margin = tr_m.get("min_right_margin_px")
        
        # 4. Untranslation measurements
        un_m = un_res.get("measurements", {})
        un_raw_strength = un_res.get("evidence_strength", 0.0)
        genuine_untrans = un_m.get("genuine_untranslated_strings_count") or 0
        latin_words = un_m.get("total_latin_words_preserved") or 0
        en_chars = un_m.get("total_english_chars_preserved") or 0
        tech_tokens = un_m.get("potential_fp_technical_brand_count") or 0

        # ----------------------------------------------------------------------
        # BASELINE SPECIFICITY SCORES
        # ----------------------------------------------------------------------
        
        # Misalignment Base
        mis_base = mis_raw_strength
        if reflow_ratio >= 0.60:
            mis_base = max(0.0, mis_base - reflow_ratio * 0.4)
        if dir_coh > 0.25:
            mis_base = max(0.0, mis_base - (dir_coh - 0.25) * 0.4)
        if col_break >= 60.0 and res_disp >= 50.0:
            mis_base = min(1.0, mis_base + 0.2)
            
        # Overlapping Base
        ov_base = ov_raw_strength
        if total_inter >= 1000.0 and (h_intrusion >= 15.0 or v_intrusion >= 15.0):
            ov_base = min(1.0, ov_base + 0.15)
        elif total_inter == 0.0:
            ov_base = min(0.3, ov_base * 0.5)
            
        # Truncation Base
        tr_base = tr_raw_strength
        if ellipsis_cnt > 0:
            tr_base = min(1.0, tr_base + 0.25)
        if container_accom > 0 and ellipsis_cnt == 0 and overflow_px == 0:
            tr_base = max(0.0, tr_base - 0.4)
            
        # Untranslation Base
        un_base = un_raw_strength
        if genuine_untrans >= 2 and latin_words >= 4:
            un_base = min(1.0, un_base + 0.2)
        elif genuine_untrans == 0 and tech_tokens > 0:
            un_base = 0.0

        # ----------------------------------------------------------------------
        # CAUSAL PRECEDENCE RULES IMPLEMENTATION
        # ----------------------------------------------------------------------
        
        causal_reasons = []
        
        # RULE 1: UNTRANSLATION ROOT-CAUSE PRECEDENCE
        # When genuine user-facing English evidence is present and spatial displacement
        # or collision is explainable by text expansion / reflow, boost Untranslation as root cause.
        has_genuine_untrans = (genuine_untrans >= 1 and latin_words >= 3)
        if has_genuine_untrans:
            # Check if spatial displacement is largely downstream reflow
            if reflow_ratio >= 0.40 or (container_accom > 0 and total_inter < 2500):
                un_base = min(1.0, un_base + 0.30)
                # Attenuate downstream reflow side-effects
                mis_base = max(0.0, mis_base - 0.25)
                causal_reasons.append("Rule 1 (Untranslation Root-Cause): User-facing English words outrank downstream spatial reflow.")
            elif total_inter > 0 and total_inter < 1500 and ellipsis_cnt == 0:
                un_base = min(1.0, un_base + 0.20)
                ov_base = max(0.0, ov_base - 0.15)
                causal_reasons.append("Rule 1 (Untranslation Root-Cause): Lexical preservation outranks incidental boundary contact.")

        # RULE 2: OVERLAPPING VS TRUNCATION DISAMBIGUATION
        # If both are active:
        # Prefer Overlapping if positive sibling intrusion / intersection exists (> 0px2).
        # Prefer Truncation if clipping occurs against text's own container and sibling intrusion is absent.
        has_positive_sibling_collision = (total_inter > 0 and (h_intrusion >= 12.0 or v_intrusion >= 12.0))
        has_container_internal_clipping = (ellipsis_cnt > 0 or (overflow_px > 0 and total_inter == 0))
        
        if has_positive_sibling_collision and ellipsis_cnt == 0:
            ov_base = min(1.0, ov_base + 0.20)
            tr_base = max(0.0, tr_base - 0.20)
            causal_reasons.append("Rule 2 (Sibling Collision Precedence): Positive sibling boundary intrusion outranks container-internal clipping.")
        elif has_container_internal_clipping and total_inter == 0:
            tr_base = min(1.0, tr_base + 0.20)
            ov_base = max(0.0, ov_base - 0.25)
            causal_reasons.append("Rule 2 (Truncation Precedence): Verified container-internal clipping/ellipsis with zero sibling collision.")

        # RULE 3: MISALIGNMENT VS DOWNSTREAM COLLISION
        # When vertical column grid anchor is broken (col_break >= 50px) and residual drift is large,
        # prefer Misalignment over incidental downstream collision/touching.
        has_strong_column_break = (col_break >= 50.0 and res_disp >= 35.0 and indep_frac >= 0.25)
        if has_strong_column_break:
            if total_inter < 3000.0 and ellipsis_cnt == 0:
                mis_base = min(1.0, mis_base + 0.25)
                ov_base = max(0.0, ov_base - 0.20)
                tr_base = max(0.0, tr_base - 0.20)
                causal_reasons.append("Rule 3 (Column Grid Precedence): Major column anchor break outranks incidental downstream collision/clipping.")

        # ----------------------------------------------------------------------
        # ARBITRATION SELECTION & MULTI-STREAM PRESERVATION
        # ----------------------------------------------------------------------
        candidate_scores = [
            ("Misalignment", mis_base, mis_res),
            ("Overlapping", ov_base, ov_res),
            ("Truncation", tr_base, tr_res),
            ("Untranslation", un_base, un_res)
        ]
        
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        top_cat, top_score, top_res = candidate_scores[0]
        
        secondary_list = []
        for cat_name, score, res_obj in candidate_scores[1:]:
            if score >= 0.30 and res_obj.get("evidence_status") in ["STRONG_EVIDENCE", "MODERATE_EVIDENCE"]:
                secondary_list.append({
                    "category": cat_name,
                    "evidence_strength": round(float(score), 3),
                    "evidence_status": res_obj.get("evidence_status"),
                    "key_measurements": res_obj.get("measurements")
                })
                
        if top_score < 0.20:
            primary_category = "NO_STRONG_OBSERVABLE_DEFECT"
            primary_strength = round(float(top_score), 3)
            dominant_mech = "INSUFFICIENT_OBSERVABLE_PHYSICAL_EVIDENCE"
            supporting_elems = []
        else:
            primary_category = top_cat
            primary_strength = round(float(top_score), 3)
            
            if primary_category == "Misalignment":
                dominant_mech = f"Structural Column Grid Break ({col_break:.1f}px anchor break, {res_disp:.1f}px residual drift)"
                supporting_elems = top_res.get("supporting_elements", [])
            elif primary_category == "Overlapping":
                dominant_mech = f"Geometric Boundary Collision ({total_inter:.0f}px² overlap area, {h_intrusion:.1f}px intrusion)"
                supporting_elems = top_res.get("supporting_elements", [])
            elif primary_category == "Truncation":
                dominant_mech = f"Text Boundary Clipping / Localized Ellipsis ({ellipsis_cnt} verified ellipsis, {overflow_px:.0f}px overflow)"
                supporting_elems = top_res.get("supporting_elements", [])
            elif primary_category == "Untranslation":
                dominant_mech = f"Preserved User-Facing English Lexicon ({genuine_untrans} untranslated strings, {latin_words} Latin words)"
                supporting_elems = top_res.get("supporting_elements", [])
            else:
                dominant_mech = "UNSPECIFIED"
                supporting_elems = []

        prov_summary = {}
        for cname, cdata in evidence_results.items():
            prov_map = cdata.get("provenance", {})
            if cname == "Repeated hotkey":
                prov_summary[cname] = "VISUALLY_UNSUPPORTED"
            else:
                prov_summary[cname] = "DIRECTLY_MEASURED" if any(p == "DIRECTLY_MEASURED" for p in prov_map.values()) else "UNAVAILABLE"

        competing_exps = []
        for cname, cdata in evidence_results.items():
            for comp in cdata.get("competing_evidence", []):
                competing_exps.append(f"[{cname}] {comp}")
                
        unavailable_list = []
        for cname, cdata in evidence_results.items():
            for unavail in cdata.get("unavailable_reasons", []):
                unavailable_list.append(f"[{cname}] {unavail}")

        # Construct explanation text
        exp_lines = []
        if primary_category != "NO_STRONG_OBSERVABLE_DEFECT":
            exp_lines.append(f"Primary diagnosis is {primary_category} (strength: {primary_strength:.3f}) driven by {dominant_mech}.")
        else:
            exp_lines.append(f"No single visual defect mechanism exhibited strong physical evidence (top candidate was {top_cat} with strength {top_score:.3f}).")
            
        if causal_reasons:
            exp_lines.append(f"Causal Precedence Applied: {' '.join(causal_reasons)}")
            
        if secondary_list:
            coexist_names = [f"{s['category']} (strength: {s['evidence_strength']:.3f})" for s in secondary_list]
            exp_lines.append(f"Coexisting secondary defect mechanisms preserved: {', '.join(coexist_names)}.")
            
        exp_lines.append(f"Repeated hotkey remains VISUALLY_UNSUPPORTED via plain OCR.")
        
        explanation_text = " ".join(exp_lines)
        
        return DiagnosticDecision(
            case_id=case_id,
            primary_category=primary_category,
            primary_evidence_strength=primary_strength,
            secondary_categories=secondary_list,
            category_results=evidence_results,
            dominant_mechanism=dominant_mech,
            supporting_elements=supporting_elems,
            provenance_summary=prov_summary,
            competing_explanations=competing_exps,
            unavailable_evidence=unavailable_list,
            explanation=explanation_text
        )
