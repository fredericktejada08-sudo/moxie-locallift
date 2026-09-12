# AI Evaluation Record

Date: 2026-09-10

This record captures a real two-pass Claude integration test against the fictional Everwell page. It is
useful source material for the interview question about where AI helped and where human intervention was
required.

## Pass 1

The API call completed successfully with `claude-sonnet-5` and returned valid structured JSON. All three
prioritized actions cited issue IDs that existed in the deterministic audit.

Quality review still found two problems:

- One implementation step suggested `MedicalSpa/HealthAndBeautyBusiness`. `MedicalSpa` was not found as a
  canonical Schema.org business type, so the wording could lead to invalid markup.
- The proposed description introduced "smooth, lasting results." The extracted page did not prove that
  outcome, so the copy exceeded the evidence even though its format and character length were valid.

## Intervention

The system prompt was tightened in two places:

- Business schema recommendations are limited to `LocalBusiness`, `HealthAndBeautyBusiness`,
  `MedicalBusiness`, or a type already present in the extracted facts. `MedicalSpa` is explicitly banned.
- Metadata can use only the supplied business, city, service, and supported page claims. Unsupported
  outcomes, credentials, technology, comfort, safety, experience, pricing, and superlatives are banned.

## Pass 2

The second live call completed successfully with 3,007 input tokens and 1,222 output tokens. It returned:

- three actions with valid evidence IDs;
- only allowed business schema types;
- a 46-character title and 127-character description;
- a neutral consultation CTA supported by the page copy;
- four checks explicitly routed to a human, GBP, Search Console, or clinical reviewer.

This test changed the final workflow. Structured output solved response-shape reliability, but it did not
guarantee factual restraint inside a valid string. The evidence-ID validator and human quality review both
remain necessary.

## References

- Anthropic structured outputs: <https://platform.claude.com/docs/en/build-with-claude/structured-outputs>
- Schema.org `LocalBusiness`: <https://schema.org/LocalBusiness>
- Schema.org `HealthAndBeautyBusiness`: <https://schema.org/HealthAndBeautyBusiness>
- Schema.org `MedicalBusiness`: <https://schema.org/MedicalBusiness>

