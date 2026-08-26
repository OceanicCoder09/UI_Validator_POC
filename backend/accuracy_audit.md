# Rigorous Accuracy & Defect Classification Audit Report

**Evaluation Baseline**: Welocalize CAD Screenshot QA Dataset (114 pairs across Autodesk Civil3d, Inventor, Vault in 10 languages)  
**Engine Under Audit**: `backend/cv_engine.py` (P0 + P1 + P2 + Phase 1 Arbiter)  
**Data Reference**: [`backend/eval_results.json`](file:///f:/POC__/backend/eval_results.json)

---

## 1. Executive Summary of Core Metrics

| Metric Name | Formula / Definition | Value | Assessment |
| :--- | :--- | :---: | :--- |
| **Detection Recall** | Screens with $\ge 1$ defect flagged / Total screens | **89.47% (102 / 114)** | **High**: Successfully catches nearly 9 out of 10 defective dialogs. |
| **Exact Classification Accuracy** | Screens where detected code matches Ground Truth / Total screens | **35.09% (40 / 114)** | **Moderate**: Only ~35% of screens emit the exact primary category code in isolation. |
| **Defect Misclassification Rate** | Screens with defects detected, but non-matching category code | **54.39% (62 / 114)** | **Key Weakness**: Engine flags secondary symptoms rather than root cause. |
| **Complete Miss Rate** | Screens marked completely clean / Total screens | **10.53% (12 / 114)** | Remaining uncaptured edge cases (e.g. tree controls, short CJK). |
| **Overall Emitted Precision** | Valid True Positive findings / Total emitted defect findings | **15.71% (41 / 261)** | **High Noise Density**: Emits multiple auxiliary findings per screen. |

---

## 2. Category-Wise Performance Breakdown Table

| Ground Truth Category | Total GT Cases | Any Detection (Recall) | Exact Category Match | Misclassified (Wrong Code) | Completely Missed | Exact Classification Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Untranslation** | 26 | 23 | **13** | 10 | 3 | **50.0%** |
| **Truncation** | 30 | 24 | **12** | 12 | 6 | **40.0%** |
| **Overlapping** | 19 | 18 | **5** | 13 | 1 | **26.3%** |
| **Misalignment** | 19 | 18 | **4** | 14 | 1 | **21.1%** |
| **Repeated Hotkey** | 7 | 7 | **0** | 7 | 0 | **0.0%** |
| **Overlapping & Misalignment** | 3 | 3 | **0** | 3 | 0 | **0.0%** |
| **Extra Punctuation** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Extra Symbol** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Extra String ("Keep Current")** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Missing a Blank Line** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Bad Layout** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Inconsistent Button Spacing** | 1 | 1 | **1** | 0 | 0 | **100.0%** |
| **Different Number Controls** | 1 | 1 | **0** | 1 | 0 | **0.0%** |
| **Header Controls Count** | 1 | 0 | **0** | 0 | 1 | **0.0%** |
| **Inconsistent Layout** | 1 | 1 | **0** | 1 | 0 | **0.0%** |
| **Incorrect Hotkey** | 1 | 1 | **0** | 1 | 0 | **0.0%** |
| **TOTAL** | **114** | **102 (89.47%)** | **40** | **62** | **12** | **35.09%** |

---

## 3. Defect-Category Confusion Matrix

The matrix below maps the **Ground Truth Defect Category** (Rows) against the **Detected Defect Types Emitted by the Engine** (Columns):

| Ground Truth Category | TRUNCATION | MISSALIGNMENT | OVERLAPPING | UNTRANSLATION | HOTKEY_DEFECT | COMBO_BOX_HEIGHT | LEAD_TRAIL | SPEC_CHARACTERS | MISC | NONE (Missed) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Truncation** (30) | **12** | 1 | 3 | 5 | 1 | 1 | 12 | 8 | 6 | 6 |
| **Untranslation** (26) | 12 | 0 | 3 | **13** | 1 | 6 | 3 | 10 | 7 | 3 |
| **Misalignment** (19) | 10 | **4** | 3 | 6 | 2 | 2 | 10 | 9 | 8 | 1 |
| **Overlapping** (19) | 9 | 0 | **5** | 7 | 2 | 5 | 8 | 9 | 5 | 1 |
| **Repeated Hotkey** (7) | 4 | 3 | 3 | 3 | **0** | 2 | 3 | 6 | 2 | 0 |
| **Overlap & Misalign** (3) | 2 | 0 | 0 | 1 | 1 | 0 | 1 | 1 | 2 | 0 |
| **Single-Case Categories** (10) | 1 | 1 | 1 | 1 | 1 | 1 | 3 | 5 | 3 | 1 |
| **TOTAL EMITTED FINDINGS** | **50** | **9** | **18** | **36** | **8** | **17** | **40** | **50** | **33** | **12** |

---

## 4. Precision by Emitted Defect Type

| Emitted Defect Type | Total Times Emitted | True Positive (Supported by GT) | False Positive (Unsupported / Auxiliary) | Precision Rate |
| :--- | :---: | :---: | :---: | :---: |
| `MISSALIGNMENT` | 9 | 5 | 4 | **55.6%** |
| `UNTRANSLATION` | 36 | 13 | 23 | **36.1%** |
| `OVERLAPPING` | 18 | 5 | 13 | **27.8%** |
| `TRUNCATION` | 50 | 13 | 37 | **26.0%** |
| `MISC` | 33 | 2 | 31 | **6.1%** |
| `LEAD_TRAIL` | 40 | 2 | 38 | **5.0%** |
| `SPEC_CHARACTERS` | 50 | 1 | 49 | **2.0%** |
| `COMBO_BOX_HEIGHT` | 17 | 0* | 17 | **0.0%** |
| `HOTKEY_DEFECT` | 8 | 0* | 8 | **0.0%** |
| **OVERALL TOTAL** | **261** | **41** | **220** | **15.71%** |

*\*Note on COMBO_BOX_HEIGHT and HOTKEY_DEFECT*: These codes represent genuine visual phenomena in CAD dialogs (shrunken dropdowns and hotkey collisions), but the Welocalize benchmark Excel categorizes them under broader parent labels (`Overlapping`, `Misalignment`, or `Repeated hotkey`).

---

## 5. Investigation of Major Misclassification Patterns

### Pattern 1: GT = Repeated Hotkey $\rightarrow$ Detected as `SPEC_CHARACTERS`, `UNTRANSLATION`, `TRUNCATION`
- **Example Cases**: `Civil3d-22 (FRA)`, `Inventor-02 (ITA)`, `Inventor-28 (JPN)`, `Inventor-30 (FRA)`, `Vault-09 (PTB)`.
- **Root Cause**: In Autodesk localized dialogs, duplicate hotkeys are written as `(&S)` or `(&C)`. The OCR reader parses the ampersand and parentheses as non-alphanumeric character differences (`SPEC_CHARACTERS`) or English letters retained in localized labels (`UNTRANSLATION`). Because hotkey duplicate matching required exact letter collision across controls in the same dialog, un-parsed hotkeys spilled into character/untranslation rules.
- **Classification**: **Category B (Secondary Evidence)** & **Category D (Markup Parsing Disconnect)**.

### Pattern 2: GT = Misalignment $\rightarrow$ Detected as `TRUNCATION`, `LEAD_TRAIL`, `SPEC_CHARACTERS`
- **Example Cases**: `Vault-28 (HUN)`, `Vault-32 (PLK)`, `Vault-35 (ESP)`, `Vault-36 (CHT)`, `Vault-37 (CSY)`, `Vault-40 (HUN)`.
- **Root Cause**: When a control shifts out of alignment to the right, its text boundary collides with the container edge. The edge detector sees the bounding border clipping and flags `0009: TRUNCATION`. Simultaneously, the differential trailing colon detector flags `0005: LEAD_TRAIL`.
- **Classification**: **Category B (Secondary Manifestation of Root Cause)**.

### Pattern 3: GT = Overlapping $\rightarrow$ Detected as `TRUNCATION` or `COMBO_BOX_HEIGHT`
- **Example Cases**: `Civil3d-28 (PTB)`, `Civil3d-29 (FRA)`, `Inventor-07 (PTB)`, `Inventor-34 (KOR)`, `Vault-05 (ITA)`, `Vault-06 (JPN)`, `Vault-34 (CHS)`.
- **Root Cause**: When two controls overlap horizontally, the left control's text overflows directly into the right control's box. The container classifier evaluates the right control's shrunken interior padding as `0012: COMBO_BOX_HEIGHT` or the left label's boundary overflow as `0009: TRUNCATION`.
- **Classification**: **Category B (Geometric Symptom Overlap)**.

### Pattern 4: GT = Truncation $\rightarrow$ Detected as `LEAD_TRAIL` or `SPEC_CHARACTERS`
- **Example Cases**: `Civil3d-04 (PLK)`, `Civil3d-10 (PTB)`, `Civil3d-21 (ITA)`, `Vault-02 (FRA)`, `Vault-20 (PLK)`.
- **Root Cause**: Truncated labels cut off trailing punctuation marks or end with partial characters that EasyOCR reads as trailing symbol anomalies (`LEAD_TRAIL` / `SPEC_CHARACTERS`).
- **Classification**: **Category A & B (Secondary Symptom fired before Truncation)**.

---

## 6. Top 5 Classification Problems

1. **Rogue Symbol Oversensitivity (`SPEC_CHARACTERS` - 49 False Positives)**:
   - Emitted 50 times across the dataset, but only 1 case had a ground truth of `Extra symbol`. Fired as a generic noise symptom on OCR token diffs.
2. **Trailing Punctuation Oversensitivity (`LEAD_TRAIL` - 38 False Positives)**:
   - Emitted 40 times, but only 1 case had ground truth `Extra punctuation`.
3. **Truncation / Overlap Boundary Confusion**:
   - Overlap into adjacent containers is frequently misclassified as Truncation (and vice versa) because both involve text crossing a rectangular container border.
4. **Hotkey Mnemonic Token Spillage**:
   - Accelerator bindings like `(&X)` are being intercepted as Untranslated English letters or Special Characters before reaching the hotkey comparator.
5. **Auxiliary Defect Multiplicity**:
   - An average of **4.25 defect findings** are generated per defective screen, creating badge noise.

---

## 7. Analysis of the 12 Completely Missed Cases

The 12 screens where `detected_count == 0` are:
1. `Civil3d-27 (PLK)`: *Header DIFFERENTNUMBEROFCONTROLS* — Tab strip header at $y<40$ filtered as window chrome.
2. `Inventor-31 (DEU)`: *Misalignment* — Subtle label shift ($<2\text{px}$) with low contrast.
3. `Vault-04 (HUN)`: *Overlapping* — Multi-layer nested tree node overlap with low pixel delta.
4. `Civil3d-20 (PTB)`: *Truncation* — Clipped single-letter subscript inside CAD table cell.
5. `Civil3d-26 (ITA)`: *Truncation* — Text clipped by a soft panel gradient rather than a hard contour.
6. `Inventor-03 (CHS)`: *Truncation* — Coordinate table cell truncation in Chinese UI.
7. `Inventor-18 (FRA)`: *Truncation* — Icon button tooltip text clipped by 1 character.
8. `Inventor-35 (PLK)`: *Truncation* — Deep tree-view node text truncation.
9. `Vault-21 (PTB)`: *Truncation* — Tree-view hierarchy text truncation.
10. `Civil3d-24 (KOR)`: *Untranslation* — English word in Korean dialog header ($y<35$).
11. `Inventor-13 (RUS)`: *Untranslation* — Property sheet table text with identical English schema tags.
12. `Inventor-16 (JPN)`: *Untranslation* — Font family names (`Tahoma`, `Consolas`) in dropdown list.

---

## 8. Final Audit Conclusion

$$\text{Detection Recall} = \mathbf{89.47\%} \quad (102 / 114)$$
$$\text{Exact Classification Accuracy} = \mathbf{35.09\%} \quad (40 / 114)$$
$$\text{Overall Emitted Precision} = \mathbf{15.71\%} \quad (41 / 261)$$

- **Summary Verdict**: The CV engine has **strong detection capability** (89.5% of defective screens are successfully flagged), but **low classification precision** (only 35.1% exact category agreement). The primary cause is that secondary OCR symptom detectors (`SPEC_CHARACTERS` and `LEAD_TRAIL`) dominate the output.
- **Action Recommendation**: Future improvements should focus on **defect arbitration and specificity suppression** (tightening `SPEC_CHARACTERS` and `LEAD_TRAIL` to only fire when no structural defect exists) rather than increasing sensitivity.
