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
# EVIDENCE ARBITRATION V3: CONTEXT-DEPENDENT CAUSAL ARBITRATION MODEL
# ==============================================================================

class CausalArbitratorV3:
    """
    Arbitrates among the five independent EvidenceResult streams using a
    context-dependent physical causal arbitration model:
      1. Lexical Root Precedence (Untranslation vs. downstream reflow drift/overlap)
      2. Structural Grid Precedence (Column anchor break vs. downstream edge clipping)
      3. Inter-Sibling Boundary Intrusion vs. Container-Internal Clipping
      4. Downstream Consequence Attenuation
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
        # 1. EXTRACT PHYSICAL EVIDENCE MEASUREMENTS
        # ----------------------------------------------------------------------
        
        # Misalignment
        mis_m = mis_res.get("measurements", {})
        col_break = mis_m.get("max_column_anchor_break_px") or 0.0
        res_disp = mis_m.get("max_residual_disp_px") or 0.0
        col_dx_std = mis_m.get("max_column_dx_std") or 0.0
        indep_frac = mis_m.get("fraction_independently_displaced") or 0.0
        dir_coh = mis_m.get("movement_direction_coherence") or 1.0
        reflow_ratio = mis_m.get("reflow_displacement_ratio") or 0.0
        
        # Overlapping
        ov_m = ov_res.get("measurements", {})
        max_inter = ov_m.get("max_intersection_area_px2") or 0.0
        total_inter = ov_m.get("total_intersection_area_px2") or 0.0
        h_intrusion = ov_m.get("max_horizontal_intrusion_px") or 0.0
        v_intrusion = ov_m.get("max_vertical_intrusion_px") or 0.0
        gap_collapse = ov_m.get("max_gap_collapse_px") or 0.0
        gaps_le_zero = ov_m.get("num_gaps_became_non_positive") or 0
        unexplained_coll = ov_m.get("residual_unexplained_collisions_count") or 0
        
        # Truncation
        tr_m = tr_res.get("measurements", {})
        ellipsis_cnt = tr_m.get("verified_ellipsis_elements_count") or 0
        overflow_px = tr_m.get("max_overflow_px") or 0.0
        clipping_cnt = tr_m.get("clipping_elements_count") or 0
        container_accom = tr_m.get("container_expanded_accommodated_count") or 0
        text_expansion = tr_m.get("max_text_expansion_px") or 0.0
        min_margin = tr_m.get("min_right_margin_px")
        
        # Untranslation
        un_m = un_res.get("measurements", {})
        genuine_untrans = un_m.get("genuine_untranslated_strings_count") or 0
        latin_words = un_m.get("total_latin_words_preserved") or 0
        en_chars = un_m.get("total_english_chars_preserved") or 0
        tech_tokens = un_m.get("potential_fp_technical_brand_count") or 0

        # ----------------------------------------------------------------------
        # 2. CONTINUOUS PHYSICAL SPECIFICITY SCORING (NO DISCRETE HARD THRESHOLDS)
        # ----------------------------------------------------------------------
        
        # A. Misalignment continuous score
        # Strong if column anchor is broken and residual displacement is substantial
        mis_score = 0.0
        if col_break > 0:
            mis_score = min(1.0, (col_break / 100.0) * 0.5 + (res_disp / 100.0) * 0.3 + (indep_frac) * 0.2)
            # Attenuate if movement is uniform reflow
            if reflow_ratio > 0.5:
                mis_score = max(0.0, mis_score - (reflow_ratio - 0.5) * 0.6)
            if dir_coh > 0.3:
                mis_score = max(0.0, mis_score - (dir_coh - 0.3) * 0.5)

        # B. Overlapping continuous score
        # Strong if positive inter-sibling intersection area and intrusion depth exist
        ov_score = 0.0
        if total_inter > 0 or gap_collapse > 0:
            inter_component = min(0.6, (total_inter / 3000.0) * 0.6)
            intrusion_component = min(0.4, (max(h_intrusion, v_intrusion) / 50.0) * 0.4)
            ov_score = inter_component + intrusion_component
            if total_inter == 0 and gap_collapse >= 15:
                ov_score = min(0.35, (gap_collapse / 60.0) * 0.35)

        # C. Truncation continuous score
        # Strong if verified ellipsis exists or positive overflow in rigid container
        tr_score = 0.0
        if ellipsis_cnt > 0 or overflow_px > 0 or clipping_cnt > 0:
            tr_score = min(1.0, (ellipsis_cnt * 0.6) + (overflow_px / 40.0) * 0.3 + (clipping_cnt * 0.2))
            if container_accom > 0 and ellipsis_cnt == 0:
                tr_score = max(0.0, tr_score - 0.35)
        elif text_expansion >= 20.0 and container_accom == 0:
            tr_score = min(0.4, (text_expansion / 80.0) * 0.4)

        # D. Untranslation continuous score
        # Strong if multiple genuine user-facing words and strings exist
        un_score = 0.0
        if genuine_untrans > 0 and latin_words > 0:
            un_score = min(1.0, (genuine_untrans / 3.0) * 0.5 + (latin_words / 8.0) * 0.5)
            if tech_tokens > 0 and genuine_untrans == 0:
                un_score = 0.0

        # E. Repeated Hotkey
        hk_score = -1.0 # Visually unsupported

        # ----------------------------------------------------------------------
        # 3. GENERALIZED CAUSAL ARBITRATION RULES (PHYSICAL ROOT PRECEDENCE)
        # ----------------------------------------------------------------------
        
        causal_rules_applied = []
        
        # RULE 1: UNTRANSLATION ROOT-CAUSE PRECEDENCE
        # If genuine user-facing English words exist (>=2 words, >=1 string) and spatial displacement/overlap
        # is physically explainable by downstream text expansion of neighboring labels:
        if genuine_untrans >= 1 and latin_words >= 2:
            if reflow_ratio >= 0.35 or (container_accom > 0 and total_inter < 3500) or (col_break < 60 and total_inter < 2000):
                un_score = min(1.0, un_score + 0.35)
                mis_score = max(0.0, mis_score - 0.30)
                ov_score = max(0.0, ov_score - 0.25)
                tr_score = max(0.0, tr_score - 0.25)
                causal_rules_applied.append("Causal Rule 1: Untranslated English text outranks downstream layout reflow/contact.")

        # RULE 2: STRUCTURAL COLUMN GRID PRECEDENCE OVER DOWNSTREAM EDGE CLIPPING
        # If a major column anchor break is present (col_break >= 45px, res_disp >= 30px), the lateral shift
        # frequently forces elements against the dialog boundary, causing secondary edge clipping.
        # Prioritize Misalignment over secondary terminal clipping.
        if col_break >= 45.0 and res_disp >= 30.0 and indep_frac >= 0.20:
            if ellipsis_cnt == 0: # If clipping is pure boundary overflow without localized ellipsis
                mis_score = min(1.0, mis_score + 0.30)
                tr_score = max(0.0, tr_score - 0.30)
                if total_inter < 2500:
                    ov_score = max(0.0, ov_score - 0.25)
                causal_rules_applied.append("Causal Rule 2: Structural column grid break outranks downstream viewport edge clipping.")

        # RULE 3: INTER-SIBLING COLLISION VS CONTAINER-INTERNAL CLIPPING
        # When both Overlapping and Truncation fire:
        # If genuine positive sibling intrusion occurs (inter_area > 0 and h/v intrusion >= 10px), prefer Overlapping.
        # If clipping occurs inside rigid container without sibling intrusion, prefer Truncation.
        if total_inter > 0 and (h_intrusion >= 10.0 or v_intrusion >= 10.0) and ellipsis_cnt == 0:
            ov_score = min(1.0, ov_score + 0.25)
            tr_score = max(0.0, tr_score - 0.25)
            causal_rules_applied.append("Causal Rule 3: Positive inter-sibling intrusion outranks internal boundary clipping.")
        elif ellipsis_cnt > 0 or (overflow_px > 0 and total_inter == 0):
            tr_score = min(1.0, tr_score + 0.30)
            ov_score = max(0.0, ov_score - 0.30)
            causal_rules_applied.append("Causal Rule 3: Verified localized ellipsis / rigid container overflow outranks incidental contact.")

        # ----------------------------------------------------------------------
        # 4. DIAGNOSTIC DECISION SYNTHESIS
        # ----------------------------------------------------------------------
        
        candidates = [
            ("Misalignment", mis_score, mis_res),
            ("Overlapping", ov_score, ov_res),
            ("Truncation", tr_score, tr_res),
            ("Untranslation", un_score, un_res)
        ]
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_cat, top_val, top_res = candidates[0]
        
        secondary_list = []
        for cname, score_val, res_obj in candidates[1:]:
            if score_val >= 0.25 and res_obj.get("evidence_status") in ["STRONG_EVIDENCE", "MODERATE_EVIDENCE"]:
                secondary_list.append({
                    "category": cname,
                    "evidence_strength": round(float(score_val), 3),
                    "evidence_status": res_obj.get("evidence_status"),
                    "key_measurements": res_obj.get("measurements")
                })
                
        if top_val < 0.20:
            primary_category = "NO_STRONG_OBSERVABLE_DEFECT"
            primary_strength = round(float(top_val), 3)
            dominant_mech = "INSUFFICIENT_OBSERVABLE_PHYSICAL_EVIDENCE"
            supporting_elems = []
        else:
            primary_category = top_cat
            primary_strength = round(float(top_val), 3)
            
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

        # Construct explanation
        exp_lines = []
        if primary_category != "NO_STRONG_OBSERVABLE_DEFECT":
            exp_lines.append(f"Primary diagnosis is {primary_category} (strength: {primary_strength:.3f}) driven by {dominant_mech}.")
        else:
            exp_lines.append(f"No single visual defect mechanism exhibited strong physical evidence (top candidate was {top_cat} with strength {top_val:.3f}).")
            
        if causal_rules_applied:
            exp_lines.append(f"Causal Precedence: {' '.join(causal_rules_applied)}")
            
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
