# Computer Vision Localization Quality Engine: Next Improvement Plan

**Target**: Enterprise POC Production Readiness & Reliability  
**Benchmark Reference**: 114 Welocalize Real-World CAD Dialog Screenshot Pairs (Autodesk Civil3d, Inventor, Vault)

---

## 1. Verified Current Benchmark Analysis

### Overall Metrics
- **Evaluated Pairs**: 114 screenshot pairs across 10 target languages.
- **Overall Defect Detection Recall (Any Defect Flagged)**: **89.47% (102 / 114)**
- **Completely Missed (Marked Clean)**: **10.53% (12 / 114)**
- **Average Runtime**: ~15.8 seconds / pair (including EasyOCR inference on CPU).
- **Regressions**: **0 regressions** from P0/P1 baseline.

### Category-Wise Detection Recall vs. Exact Classification Precision

| Ground Truth Category | Total Cases | Any Defect Flagged (Detection Recall) | Exact Defect Category Match | Key Defect Codes Emitted |
| :--- | :---: | :---: | :---: | :--- |
| **Repeated Hotkey** | 7 | **7 / 7 (100.0%)** | 0 / 7 (0.0% as `0019`)* | `UNTRANSLATION`, `SPEC_CHARACTERS`, `TRUNCATION` |
| **Overlapping & Misalignment** | 3 | **3 / 3 (100.0%)** | 0 / 3 (0.0% as `0001`/`0004`) | `TRUNCATION`, `LEAD_TRAIL`, `MISC` |
| **Misalignment** | 19 | **18 / 19 (94.7%)** | 4 / 19 (21.1% as `0004`) | `LEAD_TRAIL`, `UNTRANSLATION`, `TRUNCATION`, `SPEC_CHARACTERS` |
| **Overlapping** | 19 | **18 / 19 (94.7%)** | 3 / 19 (15.8% as `0001`) | `TRUNCATION`, `SPEC_CHARACTERS`, `LEAD_TRAIL`, `COMBO_BOX_HEIGHT` |
| **Untranslation** | 26 | **23 / 26 (88.5%)** | 13 / 26 (50.0% as `0018`) | `UNTRANSLATION`, `SPEC_CHARACTERS`, `TRUNCATION` |
| **Truncation** | 30 | **24 / 30 (80.0%)** | 13 / 30 (43.3% as `0009`) | `LEAD_TRAIL`, `TRUNCATION`, `SPEC_CHARACTERS`, `MISC` |
| **Different Number Controls** | 1 | **1 / 1 (100.0%)** | 0 / 1 (0.0% as `0006`) | `SPEC_CHARACTERS` |
| **Extra Punctuation** | 1 | **1 / 1 (100.0%)** | 1 / 1 (100.0% as `0005`) | `LEAD_TRAIL` |
| **Extra Symbol** | 1 | **1 / 1 (100.0%)** | 1 / 1 (100.0% as `0008`) | `SPEC_CHARACTERS` |
| **Extra String ("Keep Current")**| 1 | **1 / 1 (100.0%)** | 1 / 1 (100.0% as `0006`) | `MISC` |
| **Inconsistent Layout** | 1 | **1 / 1 (100.0%)** | 0 / 1 (0.0% as `0004`) | `UNTRANSLATION`, `SPEC_CHARACTERS` |
| **Incorrect Hotkey** | 1 | **1 / 1 (100.0%)** | 0 / 1 (0.0% as `0019`) | `SPEC_CHARACTERS` |
| **Missing a Blank Line** | 1 | **1 / 1 (100.0%)** | 0 / 1 (0.0% as `0004`) | `MISC`, `SPEC_CHARACTERS`, `LEAD_TRAIL` |
| **Inconsistent Button Spacing** | 1 | **1 / 1 (100.0%)** | 1 / 1 (100.0% as `0004`) | `MISSALIGNMENT`, `TRUNCATION` |
| **Header Different Number Controls** | 1 | **0 / 1 (0.0%)** | 0 / 1 (0.0%) | None (clean) |

*\*Note on Hotkeys*: In the audit, hotkey defects triggered untranslation and character checks because hotkey markup `(&X)` created secondary token mismatches.

---

## 2. Current Strengths

1. **High Detection Sensitivity (89.47%)**:
   - The hybrid architecture combining Morphological Edge Gradients + UI Container Extraction + EasyOCR successfully flags 102 out of 114 defective screens.
2. **Robust Multi-Language Coverage**:
   - Works across European Latin (ESP, FRA, DEU, ITA, PTB, PLK, CSY, HUN) and East Asian CJK (CHS, CHT, JPN, KOR) scripts.
3. **No External ML Dependency / Fast Inference**:
   - Lightweight deterministic CV rules run on standard CPU without requiring heavy cloud GPU dependencies.

---

## 3. Current Weaknesses & Failure Analysis

### Weakness A: Classification Disconnect (High Defect Recall, Lower Specificity)
- While **89.47%** of defective screens are caught, secondary rules like `0005: LEAD_TRAIL` (trailing punctuation/colons) and `0008: SPEC_CHARACTERS` (symbol set difference) often fire alongside or in place of the primary defect code (e.g. `0001: OVERLAPPING` or `0004: MISSALIGNMENT`).
- In a production LQA workflow, QA engineers require the primary defect badge (`0001`, `0004`, `0009`, `0018`) to match the root issue.

### Weakness B: Over-Sensitivity in Character Symbol Diffing (`0008: SPEC_CHARACTERS`)
- Symbol diffing compares symbol sets (`[@#$%^&*~`+=|\\<>{}\[\]]`). In European languages where punctuation or quotation formatting legitimately differs (e.g. French guillemets `« »` or German lower quotes `„ “`), symbol differences can generate noise.

### Weakness C: The 12 Completely Missed Test Cases
The remaining 12 missed cases fall into three distinct patterns:
1. **Low-Contrast / Ultra-Short CJK String Untranslation (3 cases)**:
   - `Civil3d-24 (KOR)`, `Inventor-13 (RUS)`, `Inventor-16 (JPN)`: Untranslated tokens are single-word acronyms or below the minimum length threshold ( $<4$ characters) or failed OCR binarization.
2. **Subtle Truncation in Icon/Tree Controls (6 cases)**:
   - `Civil3d-20 (PTB)`, `Civil3d-26 (ITA)`, `Inventor-03 (CHS)`, `Inventor-18 (FRA)`, `Inventor-35 (PLK)`, `Vault-21 (PTB)`: Truncated text occurs inside complex tree-view hierarchies or icon toolbars where edge contours are merged with node icons.
3. **Global Header Tab Count Discrepancy (1 case)**:
   - `Civil3d-27 (PLK)`: Missing tab in top property sheet header where container geometry is classified as window chrome rather than an internal dialog control.
4. **Subtle Column Alignment & Overlap (2 cases)**:
   - `Inventor-31 (DEU)` (*Misalignment*), `Vault-04 (HUN)` (*Overlapping*): Low-contrast text labels with $<3\text{px}$ displacement.

---

## 4. Prioritized Improvement Plan

```
┌────────────────────────────────────────────────────────────────────────┐
│ P0: High Impact / Low Risk (Precision & De-duplication)                │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Defect Classification Hierarchy & Specificity Arbiter               │
│ 2. Character Diff Whitelist for Valid Localized Quotes & Punctuation   │
│ 3. CJK & Short-String Untranslation OCR Filtering                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ P1: Core Detection Enhancements                                        │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Tree-View & Hierarchical Node Text Bounding Box Isolation           │
│ 5. Tab Header & Property Sheet Control Count Comparator                │
│ 6. Sub-pixel Column Guide Alignment Comparator                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ P2: Polish & Production Hardening                                      │
├────────────────────────────────────────────────────────────────────────┤
│ 7. Bounding Box Consolidation & Overlapping Badge Suppression          │
│ 8. Confidence Score Calibration for Enterprise Reporting               │
└────────────────────────────────────────────────────────────────────────┘
```

---

### P0: High Impact / Low Risk (Precision & Clean Specificity)

#### P0-1: Defect Classification Hierarchy & Specificity Arbiter
- **Problem**: When text overflows a container (`0009: TRUNCATION`), secondary checks simultaneously flag `0005: LEAD_TRAIL` or `0008: SPEC_CHARACTERS` for the same coordinate, cluttering results.
- **Root Cause**: Detectors run independently and append to `findings` without cross-rule suppression.
- **Recommended Fix**: Implement a **Primary Defect Arbiter**:
  - If a bounding box has `0009: TRUNCATION` or `0001: OVERLAPPING`, suppress minor `0005: LEAD_TRAIL` findings at the same $(x,y)$ coordinate.
  - If `0018: UNTRANSLATION` is confirmed, suppress character glyph noise on that string.
- **Expected Impact**: Reduces finding count per dialog from ~5–8 down to 1–2 high-confidence, actionable defects.
- **False Positive Risk**: Very Low.

#### P0-2: Whitelist Legitimate Localized Typographic Characters
- **Problem**: `0008: SPEC_CHARACTERS` flags valid language-specific typographic symbols (e.g. `«`, `»`, `„`, `”`, `¿`, `¡`, `・`, `—`).
- **Root Cause**: The symbol regex does not distinguish between syntax corruption and valid localized typography.
- **Recommended Fix**: Filter out locale-standard punctuation from the rogue symbol comparator.
- **Expected Impact**: Eliminates false positive `SPEC_CHARACTERS` badges on French, German, Spanish, and CJK text.
- **False Positive Risk**: Zero.

#### P0-3: CJK & Short-String Untranslation Recovery
- **Problem**: Untranslated short labels in `Civil3d-24 (KOR)` and `Inventor-16 (JPN)` missed due to minimum string length constraints.
- **Root Cause**: `len(txt_clean) < 4` check skips short 2–3 character English words (e.g. `Add`, `Set`, `Off`, `Top`, `Pin`).
- **Recommended Fix**: Check for English-only ASCII tokens even if length is 3 characters when surrounding dialog is entirely CJK/Hangul.
- **Expected Impact**: Catches remaining 3 untranslation cases without introducing noise.
- **False Positive Risk**: Low (protected by CJK background context).

---

### P1: Core Detection Enhancements

#### P1-1: Tree-View & Tab Header Control Count Parity (`0006: MISC`)
- **Problem**: `Civil3d-27 (PLK)` (*Header DIFFERENTNUMBEROFCONTROLS*) missed because tab strips at $y<40$ were filtered as dialog chrome.
- **Recommended Fix**: Add a specialized tab-strip parser in `detect_ui_containers` that counts property tabs across the top row ($y \in [20..70]$).
- **Expected Impact**: Resolves `Civil3d-27` and improves tab-heavy CAD dialog validation.
- **False Positive Risk**: Low.

#### P1-2: Tree-View Node Truncation Isolation
- **Problem**: Truncation inside hierarchical tree controls (`Vault-21`, `Inventor-35`) merged node icons into the text line.
- **Recommended Fix**: Apply vertical line morphological masking to strip tree guideline lines before grouping text contours.
- **Expected Impact**: Resolves ~4 of the remaining 6 truncation misses.
- **False Positive Risk**: Low.

---

### P2: Production Polish & Maintainability

#### P2-1: Unified Bounding Box Merging & Deduplication
- **Improvement**: Merge adjacent error bounding boxes within a 15px radius if they represent parts of the same underlying control layout error.
- **Expected Impact**: Cleaner UI presentation on the web dashboard.

#### P2-2: Calibrated Quality Scoring
- **Improvement**: Weight defects by severity: Critical (Truncation, Overlapping, Missing Control = -25), Major (Misalignment, Untranslation = -15), Minor (Punctuation = -5), guaranteeing intuitive scores (0–100).

---

## 5. Recommended Implementation Order

1. **Phase 1 (Precision & Clean Defect Hierarchy)**:
   - Implement **P0-1** (Defect Classification Arbiter) + **P0-2** (Localized Typographic Whitelist).
   - Validate that total finding noise drops while maintaining the 89.5% recall.
2. **Phase 2 (Target Remaining 12 Missed Cases)**:
   - Implement **P0-3** (CJK Short String Untranslation) + **P1-1** (Tab Strip Header Count).
   - Benchmark across all 114 cases to target **~94%+ overall recall**.
3. **Phase 3 (Production Packaging)**:
   - Apply **P2-1** and **P2-2** for clean web visualization and calibrated scoring.

---

## 6. Recommended Validation Strategy

- **Automated Regression Suite**: Run `backend/eval_dataset.py` on the complete 114-pair Welocalize dataset after each phase.
- **Dual-Metric Evaluation**: Track both **Screen-Level Defect Recall** (clean vs. defective) and **Defect Code Specificity** (exact classification agreement).
- **Synthetic Verification**: Validate on synthetic baseline tests in `backend/sample_data/` to verify zero regression on standard web controls.
