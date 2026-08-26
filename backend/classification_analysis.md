# 114-Case Ground Truth & Classification Error Analysis

**Audit Source**: Complete Welocalize Dataset (114 Autodesk Dialog Screenshot Pairs)  
**Evaluated Data File**: `backend/eval_results.json`

---

## 1. Executive Classification Health Summary

- **Total Evaluated Cases**: 114 pairs
- **Any Defect Caught (Detection Recall)**: **89.47% (102 / 114)**
- **Exact Primary Defect Matches**: **39.47% (45 / 114)**
- **Misclassified Cases (Caught, but Wrong Code)**: **50.00% (57 / 114)**
- **Completely Missed (Clean)**: **10.53% (12 / 114)**

---

## 2. Complete 57-Case Misclassification Matrix

The table below breaks down all 57 cases where a defect was detected, but the primary emitted code did not match the Ground Truth category.

| # | Case ID | Language | Ground Truth | Emitted Detector Codes | Available OCR / Geometry Evidence | Root Cause of Misclassification | Evidence That Should Win |
| :---: | :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | `Civil3d-12` | FRA | Misalignment | `OVERLAPPING`, `UNTRANSLATION`, `MISC` | Text column shifted left by 12px; overlaps margin | Overlapping detector fired on shifted margin bounding box | Left-anchor column shift delta (`MISSALIGNMENT`) |
| 2 | `Civil3d-14` | CHT | Misalignment | `COMBO_BOX_HEIGHT`, `HOTKEY_DEFECT`, `MISC`, `LEAD_TRAIL`, `SPEC_CHARACTERS` | Form labels have vertical pitch displacement | Control height differences masked row baseline shift | Vertical row baseline guide (`MISSALIGNMENT`) |
| 3 | `Civil3d-23` | FRA | Misalignment | `TRUNCATION` | Input box shifted right by 8px, touching container | Container edge proximity interpreted as text clipping | Input left anchor delta (`MISSALIGNMENT`) |
| 4 | `Inventor-01` | JPN | Misalignment | `MISC`, `LEAD_TRAIL`, `SPEC_CHARACTERS` | Radio buttons displaced horizontally | Secondary trailing punctuation emitted before anchor | Button left anchor delta (`MISSALIGNMENT`) |
| 5 | `Inventor-12` | FRA | Misalignment | `OVERLAPPING`, `MISC` | Two rows shifted into adjacent column | Column displacement evaluated as overlap | Column guide offset (`MISSALIGNMENT`) |
| 6 | `Inventor-17` | CSY | Misalignment | `MISC`, `LEAD_TRAIL` | Row pitch delta of 18px vs baseline | Trailing colon detector fired on misaligned line | Inter-row vertical pitch shift (`MISSALIGNMENT`) |
| 7 | `Inventor-27` | JPN | Misalignment | `TRUNCATION`, `UNTRANSLATION` | Japanese label displaced rightwards | Shift caused label to cross container border | Shift relative to English anchor (`MISSALIGNMENT`) |
| 8 | `Inventor-37` | RUS | Misalignment | `LEAD_TRAIL` | Column labels shifted left by 14px | Trailing colons on labels flagged as punctuation | Column left anchor delta (`MISSALIGNMENT`) |
| 9 | `Vault-28` | HUN | Misalignment | `TRUNCATION` | Checkbox group shifted 20px right | Text pushed against panel edge | Group left margin offset (`MISSALIGNMENT`) |
| 10 | `Vault-32` | PLK | Misalignment | `TRUNCATION`, `UNTRANSLATION` | Tree node labels indented inconsistently | Indentation overflowed tree node border | Node indentation delta (`MISSALIGNMENT`) |
| 11 | `Vault-35` | ESP | Misalignment | `TRUNCATION`, `MISC` | Dialog form fields displaced vertically | Displaced fields hit dialog border | Form field anchor grid (`MISSALIGNMENT`) |
| 12 | `Vault-36` | CHT | Misalignment | `TRUNCATION` | Dropdown shifted 15px right of label | Shift pushed dropdown past right boundary | Label-to-control horizontal gap (`MISSALIGNMENT`) |
| 13 | `Vault-37` | CSY | Misalignment | `TRUNCATION` | Text labels vertically compressed | Compressed text hit bottom margin | Vertical row baseline pitch (`MISSALIGNMENT`) |
| 14 | `Vault-40` | HUN | Misalignment | `OVERLAPPING`, `TRUNCATION`, `MISC` | Header columns misaligned with data rows | Misaligned header collided with adjacent text | Column header alignment guide (`MISSALIGNMENT`) |
| 15 | `Civil3d-30` | CHT | Overlapping | `UNTRANSLATION`, `MISC` | Label overlaps dropdown control | Untranslated technical term on overlapping label | Bounding box collision with dropdown (`OVERLAPPING`) |
| 16 | `Inventor-08` | JPN | Overlapping | `MISC`, `LEAD_TRAIL` | Two radio button labels collide horizontally | Trailing punctuation fired on colliding strings | Text-to-text horizontal collision (`OVERLAPPING`) |
| 17 | `Inventor-34` | KOR | Overlapping | `COMBO_BOX_HEIGHT`, `MISC` | Shrunken container forced text collision | Combo box height symptom masked collision | Text extending into dropdown border (`OVERLAPPING`) |
| 18 | `Vault-05` | ITA | Overlapping | `TRUNCATION`, `MISC` | Text spills over button into adjacent text | Spillover interpreted as button truncation | Text-to-text collision past button (`OVERLAPPING`) |
| 19 | `Vault-06` | JPN | Overlapping | `TRUNCATION` | Japanese string expands into next input field | Container boundary check emitted truncation | Text-to-input box collision (`OVERLAPPING`) |
| 20 | `Vault-12` | CHT | Overlapping | `UNTRANSLATION`, `HOTKEY_DEFECT`, `MISC` | Label overlaps adjacent edit control | Hotkey and English tokens on overlapping label | Text-to-control collision (`OVERLAPPING`) |
| 21 | `Vault-18` | JPN | Overlapping | `UNTRANSLATION` | English word in Japanese dialog overlaps box | English token flagged as untranslation | Text bounding box collision (`OVERLAPPING`) |
| 22 | `Vault-31` | KOR | Overlapping | `UNTRANSLATION`, `COMBO_BOX_HEIGHT` | Dropdown text collides with status icon | Shrunken dropdown and English token flagged | Label colliding with icon box (`OVERLAPPING`) |
| 23 | `Vault-33` | PTB | Overlapping | `SPEC_CHARACTERS` | Text with brackets collides with adjacent label | Bracket parsed as symbol diff | Horizontal text-to-text collision (`OVERLAPPING`) |
| 24 | `Vault-34` | CHS | Overlapping | `TRUNCATION` | Button text expands into neighboring button | Button overflow classified as truncation | Text colliding with adjacent button (`OVERLAPPING`) |
| 25 | `Inventor-26` | JPN | Overlap + Misalign | `TRUNCATION`, `MISC` | Row shifted left and overlaps container border | Overlap evaluated as truncation | Both shift and overlap present (`OVERLAPPING + MISSALIGNMENT`) |
| 26 | `Inventor-40` | CHT | Overlap + Misalign | `SPEC_CHARACTERS` | Shifted labels collide with formatting symbols | Rogue symbol rule fired on collided text | Multi-row collision & shift (`OVERLAPPING + MISSALIGNMENT`) |
| 27 | `Civil3d-22` | FRA | Repeated hotkey | `OVERLAPPING`, `TRUNCATION`, `MISSALIGNMENT`, `COMBO_BOX_HEIGHT`, `MISC` | Multiple controls share `(&P)` mnemonic | General structural rules fired on form | Duplicate shortcut mnemonic `(&P)` (`HOTKEY_DEFECT`) |
| 28 | `Inventor-02` | ITA | Repeated hotkey | `UNTRANSLATION` | 15 list items repeat accelerator mnemonic | Dimension presets flagged as untranslation | Duplicate shortcut mnemonic (`HOTKEY_DEFECT`) |
| 29 | `Inventor-28` | JPN | Repeated hotkey | `TRUNCATION`, `MISSALIGNMENT` | Duplicate hotkey letter in Japanese label | Japanese shift masked hotkey collision | Duplicate mnemonic letter (`HOTKEY_DEFECT`) |
| 30 | `Inventor-29` | CSY | Repeated hotkey | `OVERLAPPING`, `MISC` | Duplicate hotkey assigned to 2 buttons | Button collision masked hotkey duplicate | Duplicate accelerator mnemonic (`HOTKEY_DEFECT`) |
| 31 | `Inventor-30` | FRA | Repeated hotkey | `TRUNCATION`, `UNTRANSLATION` | Multiple presets share `(&A)` mnemonic | Dimension terms flagged as untranslation | Duplicate accelerator mnemonic `(&A)` (`HOTKEY_DEFECT`) |
| 32 | `Inventor-36` | PTB | Repeated hotkey | `OVERLAPPING`, `COMBO_BOX_HEIGHT` | Preset dropdowns share shortcut key | Dropdown height delta masked hotkey | Duplicate accelerator mnemonic (`HOTKEY_DEFECT`) |
| 33 | `Vault-09` | PTB | Repeated hotkey | `TRUNCATION`, `MISSALIGNMENT`, `UNTRANSLATION` | Duplicate mnemonic on action buttons | Alignment delta masked hotkey | Duplicate accelerator mnemonic (`HOTKEY_DEFECT`) |
| 34 | `Civil3d-04` | PLK | Truncation | `HOTKEY_DEFECT`, `LEAD_TRAIL`, `SPEC_CHARACTERS` | Truncated string cut off before hotkey | Partial hotkey mnemonic parsed as hotkey defect | Incomplete text string with trailing cut (`TRUNCATION`) |
| 35 | `Civil3d-05` | DEU | Truncation | `OVERLAPPING`, `UNTRANSLATION` | German compound word clipped at border | Text crossing border classified as overlap | Text cut off at container right boundary (`TRUNCATION`) |
| 36 | `Civil3d-10` | PTB | Truncation | `LEAD_TRAIL` | Truncated sentence missing final period | Missing punctuation flagged as trailing punct | Text line width exceeding control (`TRUNCATION`) |
| 37 | `Civil3d-17` | HUN | Truncation | `OVERLAPPING` | Hungarian text cut off by adjacent panel | Text touching panel classified as overlap | Text clipped by rigid border (`TRUNCATION`) |
| 38 | `Civil3d-19` | ESP | Truncation | `MISC`, `LEAD_TRAIL` | Spanish label cut off at column boundary | Trailing delimiter diff emitted before clip | Text line width exceeding container (`TRUNCATION`) |
| 39 | `Civil3d-21` | ITA | Truncation | `LEAD_TRAIL` | Italian string truncated before colon | Missing colon emitted as LEAD_TRAIL | Text cut off at container boundary (`TRUNCATION`) |
| 40 | `Civil3d-32` | HUN | Truncation | `UNTRANSLATION` | Hungarian string with English acronym clipped | English acronym flagged as untranslation | Text clipped at control right edge (`TRUNCATION`) |
| 41 | `Inventor-19` | CSY | Truncation | `OVERLAPPING` | Czech label clipped by container border | Border overflow classified as overlap | Ellipsis / visual cutoff at edge (`TRUNCATION`) |
| 42 | `Vault-02` | FRA | Truncation | `UNTRANSLATION` | French label clipped; contains English term | English term flagged as untranslation | Text cut off at right container edge (`TRUNCATION`) |
| 43 | `Vault-03` | DEU | Truncation | `UNTRANSLATION` | German label clipped; contains brand name | Brand name flagged as untranslation | Text cut off at right container edge (`TRUNCATION`) |
| 44 | `Vault-17` | ITA | Truncation | `MISC`, `LEAD_TRAIL` | Italian text cut short at panel margin | Trailing delimiter flagged as LEAD_TRAIL | Text line clipped by container margin (`TRUNCATION`) |
| 45 | `Vault-20` | PLK | Truncation | `LEAD_TRAIL` | Polish label truncated before delimiter | Missing trailing delimiter flagged | Text line clipped by container boundary (`TRUNCATION`) |
| 46 | `Vault-24` | CHT | Truncation | `MISC`, `SPEC_CHARACTERS` | Traditional Chinese text clipped by icon | Icon symbol diff flagged as SPEC_CHARACTERS | Text cut off by icon boundary (`TRUNCATION`) |
| 47 | `Vault-26` | FRA | Truncation | `MISC`, `LEAD_TRAIL` | French label truncated at button border | Trailing punctuation diff flagged | Text cut off by button border (`TRUNCATION`) |
| 48 | `Civil3d-02` | CHS | Untranslation | `TRUNCATION`, `MISC` | Untranslated English text in Chinese dialog | English text boundary checked for truncation | English ASCII phrase in CJK view (`UNTRANSLATION`) |
| 49 | `Inventor-04` | KOR | Untranslation | `OVERLAPPING`, `COMBO_BOX_HEIGHT` | Untranslated English table headers | Table headers overlap cell padding | Baseline identical English string (`UNTRANSLATION`) |
| 50 | `Inventor-09` | DEU | Untranslation | `LEAD_TRAIL` | Untranslated English label with trailing colon | Trailing colon diff flagged before string match | English baseline word match (`UNTRANSLATION`) |
| 51 | `Inventor-23` | KOR | Untranslation | `SPEC_CHARACTERS` | English symbols & tokens untranslated | English characters flagged as rogue symbols | English baseline phrase match (`UNTRANSLATION`) |
| 52 | `Vault-07` | KOR | Untranslation | `SPEC_CHARACTERS` | Untranslated English word in Korean tree | Word characters flagged as symbol diff | English ASCII word in CJK view (`UNTRANSLATION`) |
| 53 | `Vault-13` | CSY | Untranslation | `TRUNCATION` | Untranslated English string hits margin | Margin contact classified as truncation | English baseline string identity (`UNTRANSLATION`) |
| 54 | `Vault-15` | DEU | Untranslation | `SPEC_CHARACTERS` | Untranslated technical term with dashes | Dashes flagged as symbol diff | English baseline phrase match (`UNTRANSLATION`) |
| 55 | `Vault-19` | KOR | Untranslation | `TRUNCATION` | Untranslated English button in Korean UI | Button boundary check emitted truncation | English ASCII word in CJK view (`UNTRANSLATION`) |
| 56 | `Vault-25` | CSY | Untranslation | `TRUNCATION` | Untranslated Czech-view English label | Container edge contact flagged truncation | English baseline string identity (`UNTRANSLATION`) |
| 57 | `Vault-30` | JPN | Untranslation | `TRUNCATION` | Untranslated English string in Japanese UI | Japanese text check skipped; edge overflowed | English baseline string identity (`UNTRANSLATION`) |

---

## 3. Four Core Architectural Conflict Patterns

### Conflict Pattern A: Misalignment Masked by Edge Clipping & Secondary Badges (14 cases)
- **Manifestation**: A control or text line shifts left or right by $8\text{px}..25\text{px}$. When it shifts, it either touches an adjacent container border (triggering `TRUNCATION` or `OVERLAPPING`) or its trailing punctuation offset triggers `LEAD_TRAIL`.
- **Architectural Flaw**: The classifier evaluates edge boundary collisions locally without checking whether the entire left anchor column has a baseline X-displacement delta ($\Delta X \ge 4\text{px}$).
- **Solution**: If a bounding box has an anchor displacement delta ($\Delta X \ge 4\text{px}$) relative to the English baseline, the primary defect is `MISSALIGNMENT (0004)`, and edge contact is treated as a secondary byproduct unless true ellipsis truncation exists.

### Conflict Pattern B: Untranslation Masked by Truncation, Symbols & Overlap (10 cases)
- **Manifestation**: An untranslated English string in a CJK or European dialog is evaluated by the geometry engine before the OCR language engine, causing it to be flagged as `TRUNCATION`, `OVERLAPPING`, or `SPEC_CHARACTERS`.
- **Architectural Flaw**: The classifier does not check whether the text inside a colliding or overflowing container is an exact 1:1 match with an English baseline phrase.
- **Solution**: If a text element in a localized dialog is $\ge 90\%$ identical to an English baseline phrase (excluding whitelisted brands), classify as `UNTRANSLATION (0018)`.

### Conflict Pattern C: Repeated Hotkeys Masked by Secondary Symptoms (7 cases)
- **Manifestation**: Hotkey mnemonic conflicts across multiple buttons (e.g. `Default (ISO)` vs `Default (DIN)` or duplicate `(&P)`) trigger untranslation or overlapping.
- **Architectural Flaw**: Hotkey checking required strict single-letter `(&X)` regex and was subordinated to text-to-control overlap.
- **Solution**: Scan the dialog globally for duplicate hotkey letters/mnemonics; if duplicate accelerator keys exist across 2 or more controls, emit `HOTKEY_DEFECT (0019)` as the primary dialog finding.

### Conflict Pattern D: Truncation vs. Overlapping Discrimination (14 cases)
- **Manifestation**: Text expanding into an adjacent input box is sometimes flagged as Truncation (when container boundary is detected) or Overlapping (when text line is detected).
- **Solution**: Explicitly check the right neighbor entity. If a neighboring control/input exists within the overflow corridor ($x \in [cx+cw .. ox+ow]$), classify as `OVERLAPPING (0001)`. If no control exists and text is clipped by a panel border or ends in `...`, classify as `TRUNCATION (0009)`.
