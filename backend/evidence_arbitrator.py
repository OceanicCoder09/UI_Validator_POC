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

# ==============================================================================
# EVIDENCE ARBITRATION LAYER: PHYSICAL SPECIFICITY & PROVENANCE ARBITRATOR
# ==============================================================================

@dataclass
class DiagnosticDecision:
    case_id: int
    primary_category: str
    primary_evidence_strength: float
    secondary_categories: List[Dict[str, Any]]
    category_results: Dict[str, Any]
    dominant_mechanism: str
    supporting_elements: List[Dict[str, Any]]
    provenance_summary: Dict[str, str]
    competing_explanations: List[str]
    unavailable_evidence: List[str]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class EvidenceArbitrator:
    """
    Arbitrates among five independent EvidenceResult objects using physical specificity,
    provenance priority, reflow compensation, and multi-stream preservation.
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
        # 1. SPECIFICITY-ADJUSTED EVIDENCE STRENGTHS
        # ----------------------------------------------------------------------
        # Evaluate physical specificity scores based on established pairwise relationships
        
        # A. Misalignment Specificity Score
        # Attenuated if movement direction is highly coherent or reflow explanation ratio is high
        mis_m = mis_res.get("measurements", {})
        mis_raw_strength = mis_res.get("evidence_strength", 0.0)
        col_break = mis_m.get("max_column_anchor_break_px") or 0.0
        res_disp = mis_m.get("max_residual_disp_px") or 0.0
        dir_coh = mis_m.get("movement_direction_coherence") or 1.0
        reflow_ratio = mis_m.get("reflow_displacement_ratio") or 0.0
        
        # Penalize uniform reflow movement
        reflow_penalty = max(0.0, reflow_ratio * 0.5) if reflow_ratio >= 0.6 else 0.0
        coherence_penalty = max(0.0, (dir_coh - 0.25) * 0.4) if dir_coh > 0.25 else 0.0
        
        mis_adj_strength = max(0.0, mis_raw_strength - reflow_penalty - coherence_penalty)
        # Strong column anchor breaks boost structural confidence
        if col_break >= 60.0 and res_disp >= 50.0:
            mis_adj_strength = min(1.0, mis_adj_strength + 0.2)
            
        # B. Overlapping Specificity Score
        # Prefers positive intersection area and deep boundary intrusion over 0px touching
        ov_m = ov_res.get("measurements", {})
        ov_raw_strength = ov_res.get("evidence_strength", 0.0)
        max_inter = ov_m.get("max_intersection_area_px2") or 0.0
        total_inter = ov_m.get("total_intersection_area_px2") or 0.0
        h_intrusion = ov_m.get("max_horizontal_intrusion_px") or 0.0
        v_intrusion = ov_m.get("max_vertical_intrusion_px") or 0.0
        unexplained_coll = ov_m.get("residual_unexplained_collisions_count") or 0
        
        ov_adj_strength = ov_raw_strength
        if total_inter >= 1000.0 and (h_intrusion >= 15.0 or v_intrusion >= 15.0):
            ov_adj_strength = min(1.0, ov_adj_strength + 0.15)
        elif total_inter == 0.0:
            ov_adj_strength = min(0.3, ov_adj_strength * 0.5) # Gap collapse alone without intersection
            
        # C. Truncation Specificity Score
        # Prefers verified localized ellipsis ('...') and measured overflow; discounts if accommodated by container
        tr_m = tr_res.get("measurements", {})
        tr_raw_strength = tr_res.get("evidence_strength", 0.0)
        ellipsis_cnt = tr_m.get("verified_ellipsis_elements_count") or 0
        overflow_px = tr_m.get("max_overflow_px") or 0.0
        clipping_cnt = tr_m.get("clipping_elements_count") or 0
        container_accom = tr_m.get("container_expanded_accommodated_count") or 0
        
        tr_adj_strength = tr_raw_strength
        if ellipsis_cnt > 0:
            tr_adj_strength = min(1.0, tr_adj_strength + 0.25)
        if container_accom > 0 and ellipsis_cnt == 0 and overflow_px == 0:
            tr_adj_strength = max(0.0, tr_adj_strength - 0.4) # Container expansion accommodated text
            
        # D. Untranslation Specificity Score
        # Prefers user-facing English strings and high Latin word counts; ignores isolated technical tokens
        un_m = un_res.get("measurements", {})
        un_raw_strength = un_res.get("evidence_strength", 0.0)
        genuine_untrans = un_m.get("genuine_untranslated_strings_count") or 0
        latin_words = un_m.get("total_latin_words_preserved") or 0
        tech_tokens = un_m.get("potential_fp_technical_brand_count") or 0
        
        un_adj_strength = un_raw_strength
        if genuine_untrans >= 2 and latin_words >= 4:
            un_adj_strength = min(1.0, un_adj_strength + 0.2)
        elif genuine_untrans == 0 and tech_tokens > 0:
            un_adj_strength = 0.0 # Only technical terms present
            
        # E. Repeated Hotkey Specificity Score
        # Explicitly preserve VISUALLY_UNSUPPORTED
        hk_adj_strength = -1.0 # Unobservable
        
        # ----------------------------------------------------------------------
        # 2. RANKING & ARBITRATION SELECTION
        # ----------------------------------------------------------------------
        candidate_scores = [
            ("Misalignment", mis_adj_strength, mis_res),
            ("Overlapping", ov_adj_strength, ov_res),
            ("Truncation", tr_adj_strength, tr_res),
            ("Untranslation", un_adj_strength, un_res)
        ]
        
        # Sort by adjusted physical specificity strength descending
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        
        top_cat, top_score, top_res = candidate_scores[0]
        
        # Secondary / coexisting defects (any other stream with adjusted strength >= 0.35)
        secondary_list = []
        for cat_name, score, res_obj in candidate_scores[1:]:
            if score >= 0.35 and res_obj.get("evidence_status") in ["STRONG_EVIDENCE", "MODERATE_EVIDENCE"]:
                secondary_list.append({
                    "category": cat_name,
                    "evidence_strength": round(float(score), 3),
                    "evidence_status": res_obj.get("evidence_status"),
                    "key_measurements": res_obj.get("measurements")
                })
                
        # Handle case where no observable visual defect has sufficient strength
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

        # ----------------------------------------------------------------------
        # 3. CONSOLIDATED PROVENANCE & COMPETING EXPLANATIONS
        # ----------------------------------------------------------------------
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

        # ----------------------------------------------------------------------
        # 4. EXPLANATION GENERATION
        # ----------------------------------------------------------------------
        exp_lines = []
        if primary_category != "NO_STRONG_OBSERVABLE_DEFECT":
            exp_lines.append(f"Primary diagnosis is {primary_category} (strength: {primary_strength:.3f}) driven by {dominant_mech}.")
        else:
            exp_lines.append(f"No single visual defect mechanism exhibited strong physical evidence (top candidate was {top_cat} with strength {top_score:.3f}).")
            
        if secondary_list:
            coexist_names = [f"{s['category']} (strength: {s['evidence_strength']:.3f})" for s in secondary_list]
            exp_lines.append(f"Coexisting secondary defect mechanisms identified: {', '.join(coexist_names)}.")
            
        if reflow_ratio >= 0.60:
            exp_lines.append(f"Reflow compensation noted: {reflow_ratio*100:.1f}% of element displacement is explainable by upstream text expansion.")
            
        exp_lines.append(f"Repeated hotkey remains VISUALLY_UNSUPPORTED as native Win32 mnemonic underlines are unobservable via flat OCR.")
        
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

# ==============================================================================
# PIPELINE ENTRY POINT
# ==============================================================================

def run_arbitration_pipeline(case_id: int, case_payload: Dict[str, Any]) -> Dict[str, Any]:
    engine = EvidenceEngine()
    eval_output = engine.evaluate_case(case_id, case_payload)
    
    arbitrator = EvidenceArbitrator()
    decision = arbitrator.arbitrate(case_id, eval_output["evidence_results"], case_payload)
    
    return decision.to_dict()
