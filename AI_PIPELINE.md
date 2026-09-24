# MedLM AI extraction and verification pipeline

> Phase 1 implementation update (2026-09-24): the foundation is now implemented. See [PHASE_1_REPORT.md](PHASE_1_REPORT.md), [current API contract](contracts/openapi.json) and [scope decisions](docs/adr/0001-phase-one-boundaries.md). The remaining design below describes future behavior, not implemented clinical functionality.

Status: design only. Research checked 2026-09-24. GPT output is untrusted proposed data, never the source of a medical fact.

## OpenAI API and OCR findings

Official documentation lists model ID `gpt-6-astra`, image input, text output, Responses API and structured outputs. Use a server project key, configured model ID and bounded output budget. Production credentials, billing, geographic eligibility, rate limits and actual project model access have not been tested. Before integration, perform a synthetic image/schema smoke test; if unavailable, disable AI analysis with a clear error rather than silently substituting a model. Pin a documented snapshot when available; otherwise monitor alias changes and rerun evaluations. [Model](https://developers.openai.com/api/docs/models/gpt-6-astra).

Send validated images as `input_image` using an inline data URL to avoid public storage URLs. Use `detail: high` initially, measuring small-text accuracy and cost; preserve readable crop context. Small text, rotation and image quality can affect vision interpretation. [Vision guide](https://developers.openai.com/api/docs/guides/images-vision).

Request a strict JSON Schema through Responses `text.format`; handle refusal, truncation and invalid application semantics independently. Schema conformity does not establish factual correctness. [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Phase 0 recheck (2026-09-24): the published API ID remains `gpt-6-astra`; image input and structured outputs are documented, but project access has not been exercised. Strict schemas use required properties, nullable unions for missing values and `additionalProperties:false`; model extraction DTOs must use the supported JSON Schema subset rather than blindly reusing every API discriminated union. Validate SDK serialization and refusal/incomplete responses with synthetic fixtures in Phase 1. Documentation support is not evidence of medical OCR accuracy, Telugu handwriting quality or zero hallucinations.

Native ML Kit text recognition is an optional on-device printed-text aid for supported scripts; it is not a shared desktop/web OCR engine or validation of handwriting. A server OCR adapter may benchmark Google Cloud Vision `DOCUMENT_TEXT_DETECTION` for handwriting. That adds a separate processor and requires privacy/region review. Initial end-to-end extraction may use Astra vision alone; independent OCR disagreement is useful evidence of uncertainty, not a majority vote. No cloud OCR fallback is enabled without provider review. [ML Kit](https://developers.google.com/ml-kit/vision/text-recognition/v2), [Cloud Vision handwriting](https://docs.cloud.google.com/vision/docs/handwriting).

ML Kit's documented script list does not include Telugu. Telugu text therefore uses the server vision path only after language-specific evaluation, or an independently validated OCR adapter; otherwise request clearer input/manual review. English/Hindi/Telugu explanation capability and source translation rights are separate release checks. Validate fonts, numeral/decimal preservation, transliterated brand names and mixed-script prescription lines.

## Staged processing

1. **Accept and validate.** Require authentication, market context, consent and an owned, completed upload. Check magic bytes, dimensions, byte limit and decode limits. Strip EXIF/location, re-encode safely, assess blur/glare/cropping. Reject malicious or unusable files.
2. **Minimize.** Crop to relevant medicine/instruction regions where feasible. Exclude patient name, address, prescriber identity and unrelated content from provider requests. Redaction quality is not guaranteed: disclose processing of the submitted image and treat all derived text as sensitive.
3. **Extract observations.** Model returns document type, lines, literal text, field candidates, normalized values only where clear, bounding boxes, alternatives and ambiguity flags. OCR/vision never fills absent text from pharmacological knowledge. Multi-medicine prescriptions retain line boundaries.
4. **Validate structure.** Check schema, units, decimal punctuation, repeated lines, image coordinates and missing fields. Preserve `0.5` versus `5`, micrograms versus milligrams, salt names and modified-release designations. A model-generated confidence number is not a calibrated probability.
5. **Generate candidates.** Query normalized name/ingredient identifiers using structured, allowlisted adapters. Include selected country. Compare complete ingredient sets, strength/concentration, dosage form, route, release type, manufacturer/labeler and product identifiers where visible. Brand-name similarity alone cannot identify a product.
6. **Verify evidence.** Resolve product identifiers to current applicable documents. Record source revision and section. Contradictory visible fields block product verification. Distinguish product verification, ingredient-only information, ambiguous candidates and unsupported market.
   **Uncertain identity gate:** return `identity_review_required` with a versioned candidate set and no identified-product report. Require explicit choice/correction/rejection through the identity-review API, then rerun matching and evidence checks. Store review and verification as separate dimensions. A selected candidate can still remain unverified; unresolved cases offer retake or explicitly manual entry, never automatic candidate acceptance. Candidate information, if shown for comparison, is labeled as such.
7. **Assemble facts.** Deterministic parsing produces evidence-linked facts; missing sections become explicit unavailable values. Keep source conflicts rather than synthesizing a third answer. Product-specific label evidence outranks generic information for that product; conflicts needing judgment remain unresolved.
8. **Explain.** Astra receives only the validated evidence bundle and allowed claim IDs. It may simplify and translate; it cannot add new ingredients, dosage directions or claims from memory. It returns claim-to-evidence mappings with exact source spans. Never stream unvalidated medical text directly to users.
9. **Gate and publish.** Validate cited IDs, source applicability, numeric/ingredient consistency, prohibited personalized advice and translation preservation. Semantic support needs evaluation and clinical review; automated checks are not proof. Failed explanation falls back to reviewed deterministic templates or source excerpts, otherwise abstains.
10. **Review prescription.** Show all lines and uncertainties. Require explicit user confirmation of a particular draft version before conversion to medication records. Re-extraction creates a new version and invalidates old confirmation for new conversion. No AI tool has permission to activate a reminder.
11. **Delete and audit.** Purge processing copies when the job ends; retain a minimized review copy only if requested for identity/prescription review, until review ends or 24 hours from upload, whichever is earlier. Cancellation deletes all copies. Store pipeline/model/schema versions and decision codes without raw prompts in logs. Expired image does not block later review of saved text, but user is told the original is unavailable.

Job states: `queued -> validating -> extracting -> retrieving -> validating_output -> completed`; alternate terminals `needs_input`, `failed`, `cancelled`. Completed means processing finished, not verified identity. Result `verification_status` is independently `verified_product`, `ingredient_only`, `ambiguous`, `unverified`, or `unsupported_market`. Timeout/source outage can yield an unverified draft, never a verified result.

## Medicine-source strategy

| Source | Authorized architectural role | Limits |
| --- | --- | --- |
| DailyMed/NLM SPL | US product label sections, product identifiers, document revisions | Match correct product/formulation; database inclusion is not equivalent to approval or package authentication |
| RxNorm/RxNav | US-oriented normalized concepts and identifier mapping | Not a global brand registry; not comprehensive clinical content |
| openFDA drug labels | Supplementary label discovery and structured access | Same SPL lineage as DailyMed is not independent corroboration; no medical-care decisions based on this API |
| Licensed clinical provider, e.g. DrugBank | Candidate for structured interaction and additional clinical content | Contract, target-market coverage, redistribution, translation and cache rights must be verified; no assumed free production license |
| Regional regulator / approved manufacturer label | Exact-market product evidence through curated, governed ingestion | Need reliable identifiers and update process; no invented public API or blanket country coverage |

DailyMed exposes versioned REST resources and SPL history. RxNorm provides terminology APIs. openFDA explicitly cautions against reliance for medical-care decisions. [DailyMed services](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm), [RxNorm API](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html), [openFDA labels](https://open.fda.gov/apis/drug/label/).

RxNav discontinued its drug-interaction features on January 2, 2024. Do not implement against the removed API. DrugBank documents clinical endpoints, but access and intended-use rights need procurement review. [RxNav FAQ](https://lhncbc.nlm.nih.gov/RxNav/information/FAQs.html), [DrugBank API](https://docs.drugbank.com/v1/).

For India, CDSCO publishes approved-new-drug information; this research did not establish a comprehensive public API for all marketed brands and formulations. A CDSCO entry alone cannot resolve every photographed Indian brand. Seek licensed regional product data and legally reusable manufacturer labels; abstain until coverage is validated. [CDSCO approved drugs](https://cdsco.gov.in/opencms/opencms/en/Approval_new/Approved-New-Drugs/).

India is the confirmed launch market. A coverage registry must enumerate supported product categories, languages and clinical fields per provider. Local prescription/OTC status requires current Indian evidence; never infer OTC status from an absent schedule flag or a US label. Ayurvedic/traditional products, supplements and uncommon formulations receive an explicit unsupported result unless separately covered and evaluated. MIMS exposes a developer portal, but its public page does not establish Indian API coverage; procurement must verify regional availability rather than scrape its consumer site. [MIMS portal](https://developer.mims.com/).

Do not query arbitrary websites, search snippets or model memory for missing facts. Do not send prescriptions or medication histories as public search queries. For interactions, general label statements may appear with citations; comprehensive patient-list screening is a separately gated feature, never implied by an empty result.

## Provenance contract

Every medical field contains `status`, `value`, `claim_ids` and `evidence_ids`. Status is `supported`, `not_available`, `conflicting` or `not_applicable`; the last also requires evidence. Evidence captures provider, stable external document ID, version, market, locale, URL, section locator, permitted excerpt, content hash, source publication/update date, retrieval time and last successful verification time. Distinguish label publication date from verification time. Translations reference the original claim and locale/reviewer version.

Extraction fields additionally contain literal `raw_text`, nullable normalized value, location, ambiguity reason, alternatives and review status. User corrections have author/time and old/new value. User confirmation cannot turn an unverified source identity into a verified product.

## Failure and quality policy

Bounded retries with jitter apply only to transient timeouts/429/5xx; respect Retry-After, job expiry and cancellation. Never retry ambiguity until a guess emerges. Source circuit breakers expose provider unavailability. Enforce per-job image/token/cost budgets and per-user quotas; no unbounded agent loops.

Build a consented/synthetic, expert-labeled evaluation set spanning each package type, mixed scripts, languages, handwriting, abbreviations, multi-drug lines, look-alike names, low quality, combination products, decimals, adversarial image instructions and unsupported markets. Measure exact critical-field accuracy, false verification, abstention, unsupported-claim rate, source freshness, citation correctness, translation errors, latency and cost. Split by product and handwriting author to reduce leakage.

Release requires zero known critical false-verification, invented-dose or confirmation-bypass failures in the release suite, 100% provenance coverage for displayed medical claims and no unresolved high-severity safety defects. Clinical reviewers must predefine minimum sample sizes and statistical error bounds per market/language before collecting release results; passing a finite suite does not establish zero real-world risk. Keep abstention permissive until calibrated thresholds have clinical approval.
