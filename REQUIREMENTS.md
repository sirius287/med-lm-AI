# MedLM AI requirements

> Phase 1 implementation update (2026-09-24): the foundation is now implemented. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md), [current API contract](contracts/openapi.json) and [scope decisions](docs/adr/0001-phase-one-boundaries.md). The remaining design below describes future behavior, not implemented clinical functionality.

Status: reviewed product baseline. Date: 2026-09-24. Launch market: **India**, confirmed by the user. Required launch languages: **English, Hindi and Telugu** (`en-IN`, `hi-IN`, `te-IN`), subject to clinical translation release gates; licensed data budget remains open. No medical capability is implied outside validated coverage.

## Purpose and safety boundary

MedLM AI provides sourced medication information and user-controlled medication management. It does not diagnose, prescribe, recommend changing treatment, tell users to stop prescription medication, invent dose instructions, or certify the authenticity of a physical medicine. A matching label establishes a reference-data match, not that the contents of a photographed package are genuine.

## Functional requirements and acceptance

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| ING-01 | Camera or file input for strip, bottle, tube, box/label and handwritten/printed prescription | Every class has supported, blurred, cropped, rotated and unsupported test examples; file picking works on all five platforms |
| ING-02 | Guide capture, preview, rotate/crop, retake, upload consent and progress | User sees privacy purpose and can cancel; low-quality images receive a retake request, never a fabricated identity |
| ING-03 | JPEG, PNG and WebP first; HEIC converted through vetted local/platform codec | Server validates decoded content; initial limit 10 MiB/image, 5 images/analysis, 30 MiB/analysis, 40 megapixels/image; unsupported formats rejected clearly |
| MED-01 | Extract packaging fields and resolve candidates against approved sources | Observed text, user corrections and verified claims remain distinguishable; conflict or insufficient evidence prevents product verification |
| MED-02 | Report requested information when supported | Every field below exists in the schema; absent evidence displays `not available in checked sources`, never an inferred negative |
| MED-03 | Field-level provenance and verification date | Every displayed medical claim references an applicable source revision and section; country and stale/conflict states are visible |
| MED-04 | Mandatory confirmation of uncertain medicine identity | No ambiguous candidate is preselected, attached to a medication or presented as the identified product before explicit versioned user review; user can reject all candidates or retake; selection alone never establishes authoritative verification |
| RX-01 | Extract prescription fields per medicine line | Medicine, strength, dose, frequency, route, duration, time, before/after-food and special instructions preserve literal text and nullable normalized values |
| RX-02 | Mandatory review | All extracted lines and schedule-driving fields shown with uncertainty; no line pre-confirmed; immutable confirmation required by API before prescription-derived schedules |
| RX-03 | Ambiguity handling | Competing readings shown without choosing one; unresolved dose/unit/frequency blocks activation; user can leave line unresolved or exclude it |
| REM-01 | Manual entry and confirmed-prescription entry | Manual values explicitly user-entered; no dosage suggestions based on general labels or AI guesses |
| REM-02 | Scheduling | Explicit times, selected weekdays, user-specified fixed intervals, recurrence, start/end, timezone and food notes; preview upcoming occurrences before activation |
| REM-03 | Dose actions | Taken, skipped and snoozed supported with timestamp, optional note and undo/correction event; snooze does not alter prescription dose or next regular occurrence |
| REM-04 | History and editing | Date-filtered history; edits version schedules; deletion cancels future reminders; historical entries retain the original schedule context unless user requests erasure |
| REM-05 | Offline and multiple devices | Native local reminders and action queue work offline; reconnect detects conflicting actions; capability and sync status shown |
| PRIV-01 | Sensitive images are transient | Processing-only copies deleted at completion; an explicitly requested review copy can remain until review ends, cancellation or 24h from upload, whichever comes first; deletion target <=15 minutes after trigger, see SECURITY |
| PRIV-02 | User control | Delete image, report, prescription, medication and account; export machine-readable records; logout clears sensitive local state and pending notifications |
| UX-01 | Five-platform adaptive UX | Bottom navigation on compact screens, rail/sidebar and master-detail on wide screens; keyboard and screen-reader workflows tested |
| UX-02 | Light/dark and subtle neumorphism | Shadows are decorative; control boundaries, text contrast and focus indicators never depend on shadow alone |
| UX-03 | English/Hindi/Telugu interface and reports | Locale catalog, plural/date/number rules, tested Telugu/Devanagari fonts and shaping, RTL-ready layouts; clinical content validated per language; original names and units retained |

## Report fields

Required schema keys: `medicine_name`, `generic_name`, `active_ingredients`, `strength`, `dosage_form`, `manufacturer`, `common_uses`, `mechanism_action`, `common_side_effects`, `serious_adverse_effects`, `warnings`, `contraindications`, `precautions`, `drug_interactions`, `food_beverage_interactions`, `pregnancy`, `breastfeeding`, `pediatric`, `older_adult`, `kidney`, `liver`, `storage`, `prescription_otc_status`, `other_information`. Each is an evidence-bearing field; source references and verification dates are report metadata and available per field.

Product identity fields must match product-level evidence. Ingredient information cannot establish a particular manufacturer's product, release type, concentration or prescription status. Pregnancy and organ-function fields convey sourced general information, never personalized risk clearance or dose adjustment. Interaction sections are documented label information until a licensed interaction checker passes validation; no match never means no interaction.

## Prescription and reminder semantics

1. Preserve source text and image coordinates during review; missing values remain missing. Recognition quality and source match are separate states.
2. Review must distinguish strength (amount per unit) from prescribed dose (amount taken). Do not convert milligrams to tablets or milliliters without an explicit, verified relationship and user confirmation; initial release avoids automatic conversions.
3. Confirmation attests to the user's transcription review, not medical validity. An unreadable instruction should be clarified with the prescriber/pharmacist; the application must not choose the most plausible reading.
4. A missing clock time can be supplied as a user scheduling preference, recorded separately from prescription instructions. `Twice daily` does not automatically mean `every 12 hours`. Before/after-food text does not imply a number of minutes.
5. MVP schedule templates: daily explicit clock times, selected weekdays, explicit interval hours and one-time. PRN entries can be logged but receive no invented recurring schedule. Tapers, alternating doses and complex cycles remain stored as instructions until a dedicated, validated schedule editor is available.
6. Calendar schedules store IANA timezone and wall times; fixed intervals use elapsed time from a UTC anchor. Travel never silently changes dose spacing. Preview and confirm timezone changes.
7. DST gap default proposal: next valid local instant; overlap: first occurrence only. User sees this policy at activation; clinical review must approve the scheduling UX. Never generate two doses for a repeated local time.
8. No response to a reminder is `unrecorded`, not `skipped`. History is user-reported, not proof of adherence. No missed-dose advice is generated.
9. Prescription-derived schedule activation must compare its clinical fields with the confirmed line. A client cannot relabel it `manual` to bypass review. Changes to medicine/dose/route/frequency/duration/food instructions require a newly reviewed instruction revision; clock-time preferences remain separately identified.

Report language, text-recognition language and product market are independent. Telugu UI support does not establish Telugu handwriting accuracy. Each required language needs its own extraction/clinical explanation evaluation and safe unavailable state; never silently substitute English for an unvalidated clinical translation. Zero hallucinations is a safety objective, not a proven model capability: unsupported output is withheld, and finite evaluation success must not be marketed as infallibility.

## Accessibility and quality

Target WCAG 2.2 AA for the web and equivalent native accessibility: 4.5:1 normal text contrast, 3:1 large text, keyboard access, visible focus, meaningful labels and status announcements. Product design target is >=48 logical-pixel touch targets and 200% text scaling without loss of core actions. These are acceptance targets to verify in both themes, not a current conformance claim. [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

Use readable typography, plain-language warnings and progressive disclosure for long reports. Provide Home/Today, Scan, Medicines, History and Settings destinations. Do not hide unresolved extraction behind an overall confidence badge. Render source links alongside medical statements and explain unsupported coverage in plain language.

Performance, availability and recovery targets are in ARCHITECTURE. No supported platform ships until upload, review, medication CRUD, history and its documented reminder capability pass end-to-end tests. Disabled browser notifications must never block medication management.

## Exclusions and unresolved decisions

No diagnosis, prescribing, treatment recommendations, emergency monitoring, counterfeit detection, clinician dashboard, caregiver sharing or automatic interaction-based treatment changes. Medical images are not training data. English/Hindi/Telugu require reviewed terminology and evaluation sets; subsequent languages follow the same gates. Age eligibility, data residency, retention obligations, licensed database budget and regulatory classification need explicit decisions before public launch.
