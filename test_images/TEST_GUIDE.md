# 🧪 Autodesk UI Quality Checker — Complete 22-Scenario Test Suite

Location: `f:\POC__\test_images\`

This suite contains 22 standardized, pixel-accurate Autodesk UI screenshots across **7 languages** (English, German, Spanish, French, Japanese, Italian, Portuguese, Korean) testing all Autodesk Localization QA (LQA) Defect categories.

---

## 📋 Complete Test Matrix (22 Images)

| # | Test Image Filename | Language | Defect / Scenario | Expected Score | Expected LQA Code |
|:---:|---|:---:|---|:---:|:---:|
| **01** | `01_Baseline_English_Reference.png` | **English** | **Baseline Reference Standard** | — | *Baseline Reference* |
| **02** | `02_German_Clean_Perfect_100.png` | German | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **03** | `03_Spanish_Clean_Perfect_100.png` | Spanish | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **04** | `04_French_Clean_Perfect_100.png` | French | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **05** | `05_Japanese_Clean_Perfect_100.png` | Japanese | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **06** | `06_Italian_Clean_Perfect_100.png` | Italian | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **07** | `07_Portuguese_Clean_Perfect_100.png` | Portuguese | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **08** | `08_Korean_Clean_Perfect_100.png` | Korean | Clean Translation (Natural `...` placeholders) | **100 / 100** | **Pass (0 Defects)** |
| **09** | `09_German_Button_Overflow_ERR0009.png` | German | Primary button label spills past 145px border | **75 / 100** | **`[ERR-0009] TRUNCATION`** |
| **10** | `10_French_Button_Overflow_ERR0009.png` | French | Primary button label spills past 145px border | **75 / 100** | **`[ERR-0009] TRUNCATION`** |
| **11** | `11_Spanish_Missing_Button_ERR0006.png` | Spanish | Secondary "Attach Log" button omitted | **75 / 100** | **`[ERR-0006] MISC`** |
| **12** | `12_French_Missing_Help_Icon_ERR0006.png` | French | Header Help (?) utility icon omitted | **75 / 100** | **`[ERR-0006] MISC`** |
| **13** | `13_Spanish_Form_Dropdown_Misaligned_ERR0004.png` | Spanish | Form select input indented +30px off-grid | **95 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **14** | `14_German_Form_Dropdown_Misaligned_ERR0004.png` | German | Form select input indented +30px off-grid | **95 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **15** | `15_Japanese_Header_Bar_Shift_ERR0004.png` | Japanese | Top navigation header shifted down 28px | **85 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **16** | `16_Japanese_Card_Widget_Collision_ERR0001.png` | Japanese | Form card expanded into right widget by 60px | **75 / 100** | **`[ERR-0001] OVERLAPPING`** |
| **17** | `17_Spanish_Missing_And_Misaligned_Combo.png` | Spanish | Missing button + Form dropdown offset | **70 / 100** | **`[ERR-0006] MISC`**<br>**`[ERR-0004] MISSALIGNMENT`** |
| **18** | `18_German_Overflow_And_Misaligned_Combo.png` | German | Button text overflow + Form dropdown offset | **70 / 100** | **`[ERR-0009] TRUNCATION`**<br>**`[ERR-0004] MISSALIGNMENT`** |
| **19** | `19_Italian_Overflow_And_Missing_Combo.png` | Italian | Button overflow + Missing secondary button | **50 / 100** | **`[ERR-0009] TRUNCATION`**<br>**`[ERR-0006] MISC`** |
| **20** | `20_Japanese_Full_Cascade_Overlap_Shift_Combo.png` | Japanese | Card collision + Header shift + Missing icon | **35 / 100** | **`[ERR-0001] OVERLAPPING`**<br>**`[ERR-0004] MISSALIGNMENT`**<br>**`[ERR-0006] MISC`** |
| **21** | `21_French_ComboBox_Height_Defect_ERR0012.png` | French | Dropdown select box height restricted (< 30px) | **85 / 100** | **`[ERR-0012] COMBO_BOX_HEIGHT`** |
| **22** | `22_German_Corrupted_Glyph_Defect_ERR0016.png` | German | Corrupted Unicode replacement diamond glyph () | **75 / 100** | **`[ERR-0016] EXTENDED_CHAR_ISSUE`** |

---

## 🚀 How to Test on [http://localhost:3000](http://localhost:3000)

1. **Left Input Box (Baseline)**: Always upload [01_Baseline_English_Reference.png](file:///f:/POC__/test_images/01_Baseline_English_Reference.png).
2. **Right Input Box (Localized Target)**: Drop any image from `02` through `22`.
3. Click **"Analyze Screenshots"** to inspect findings and bounding box badges.
4. Click **"Download Audit Report (PDF)"** to generate the Autodesk LQA audit document!
