"""Fictional offline medspa pages and clearly labeled reference AI output."""

from __future__ import annotations

from typing import Any


DEMO_SITES: list[dict[str, str]] = [
    {
        "id": "everwell",
        "business_name": "Everwell MedSpa",
        "city": "Austin",
        "service": "Laser Hair Removal",
        "url": "https://demo.locallift.test/everwell/laser-hair-removal",
        "html": """<!doctype html><html><head>
          <title>Advanced Aesthetic Treatments</title>
          <meta property="og:title" content="Advanced Aesthetic Treatments">
        </head><body><header><a href="/">Everwell</a></header><main>
          <h1>Smoother skin starts here</h1><h1>Our laser technology</h1>
          <p>Our team offers personalized laser hair removal plans with comfortable appointments and clear aftercare guidance.</p>
          <p>Book a consultation to discuss treatment areas, candidacy, session timing, and what to expect.</p>
          <img src="room.jpg"><img src="laser.jpg" alt=""><img src="team.jpg" alt="Everwell clinical team">
          <a href="/contact">Contact</a><a href="/services">Services</a>
        </main></body></html>""",
    },
    {
        "id": "northline",
        "business_name": "Northline Aesthetics",
        "city": "Denver",
        "service": "Botox",
        "url": "https://demo.locallift.test/northline/botox",
        "html": """<!doctype html><html><head>
          <title>Botox in Denver | Northline Aesthetics</title>
          <meta name="description" content="Natural-looking Botox treatments in Denver from experienced aesthetic injectors. Request a personalized consultation with Northline Aesthetics.">
          <meta name="robots" content="noindex, follow">
          <script type="application/ld+json">{"@context":"https://schema.org","@type":"MedicalBusiness","name":"Northline Aesthetics","address":{"@type":"PostalAddress","addressLocality":"Denver"}}</script>
        </head><body><main><h1>Botox treatments in Denver</h1>
          <p>Northline Aesthetics provides individualized Botox consultations in Denver. Our injector reviews your goals, medical history, facial movement, treatment options, and expected aftercare before recommending a plan.</p>
          <p>Appointments include a detailed assessment, conservative dosing, and follow-up guidance. Results and suitability vary, so every treatment begins with a clinical consultation.</p>
          <p>Patients can ask about treatment areas, timing, cost, preparation, and what to expect after an appointment. Contact our Denver studio to request an assessment.</p>
          <a href="tel:+13035550148">(303) 555-0148</a><img src="consult.jpg" alt="Injector consulting with a patient">
        </main></body></html>""",
    },
    {
        "id": "harbor",
        "business_name": "Harbor Skin & Laser",
        "city": "Tampa",
        "service": "Microneedling",
        "url": "https://demo.locallift.test/harbor/microneedling",
        "html": """<!doctype html><html><head>
          <title>Microneedling in Tampa | Harbor Skin & Laser</title>
          <meta name="description" content="Explore personalized microneedling in Tampa at Harbor Skin & Laser. Learn about candidacy, treatment, recovery, and consultation options.">
          <link rel="canonical" href="https://demo.locallift.test/harbor/microneedling">
          <script type="application/ld+json">{"@context":"https://schema.org","@type":"MedicalBusiness","name":"Harbor Skin & Laser","telephone":"+1-813-555-0192","address":{"@type":"PostalAddress","streetAddress":"100 Harbor Way","addressLocality":"Tampa","addressRegion":"FL"}}</script>
        </head><body><main><h1>Microneedling in Tampa</h1>
          <p>Harbor Skin & Laser offers personalized microneedling consultations in Tampa. A qualified provider reviews your skin concerns, medical history, and goals before discussing whether treatment is appropriate.</p>
          <p>Microneedling creates controlled microchannels as part of a clinician-led skin rejuvenation plan. Your appointment covers preparation, comfort options, aftercare, expected recovery, and the number of sessions your provider may recommend.</p>
          <p>Common consultation topics include texture, the appearance of acne scars, fine lines, treatment intervals, and combining services. Outcomes vary and no result is guaranteed.</p>
          <p>Our Tampa team provides written aftercare and schedules follow-up when appropriate. Request a consultation to receive an individualized plan and current pricing.</p>
          <p>Before treatment, the provider explains temporary redness, skin-care restrictions, sun protection, and the signs that should prompt a follow-up call. Patients leave with practical instructions rather than a generic recovery promise.</p>
          <p>The studio serves patients from Tampa and nearby communities by appointment. Consultation time is used to set realistic goals, answer questions, and decide whether another option would better match the patient's needs today.</p>
          <a href="tel:+18135550192">(813) 555-0192</a><a href="/contact">Request a consultation</a>
          <img src="treatment-room.jpg" alt="Private treatment room at Harbor Skin and Laser">
          <img src="consultation.jpg" alt="Provider discussing a microneedling plan">
        </main></body></html>""",
    },
]


DEMO_AI: dict[str, dict[str, Any]] = {
    "everwell": {
        "executive_summary": "This service page has a clear offer, but weak metadata and local signals make its intended Austin query difficult to infer. Fix the search snippet and heading hierarchy before expanding copy.",
        "priority_actions": [
            {
                "title": "Rebuild the search snippet around service and place",
                "why": "The current title omits the service, city, and brand, while the description is missing entirely.",
                "steps": "Publish the proposed title and description, then inspect the rendered snippet and verify each is unique in the crawl.",
                "evidence_ids": ["metadata.service_title", "local.city_title", "metadata.description_missing"],
            },
            {
                "title": "Clarify the primary page heading",
                "why": "Two H1s compete without naming the exact local service target.",
                "steps": "Use one H1 such as 'Laser Hair Removal in Austin' and convert the technology heading to H2.",
                "evidence_ids": ["content.h1_multiple"],
            },
            {
                "title": "Add grounded local business markup",
                "why": "No compatible local business JSON-LD was detected on the page.",
                "steps": "Add the most accurate LocalBusiness subtype with NAP copied from the verified GBP and validate it before release.",
                "evidence_ids": ["schema.local_business_missing"],
            },
        ],
        "metadata": {
            "title": "Laser Hair Removal in Austin | Everwell MedSpa",
            "description": "Explore personalized laser hair removal in Austin at Everwell MedSpa. Discuss treatment areas, timing, and aftercare in a consultation.",
            "title_length": 46,
            "description_length": 135,
            "title_within_limit": True,
            "description_within_limit": True,
        },
        "human_checks": [
            "Confirm the business name, phone, and address against the live Google Business Profile.",
            "Classify each empty-alt image as informative or decorative before writing alt text.",
            "Review treatment copy and claims with the responsible clinical stakeholder.",
        ],
        "scale_note": "Run the same evidence schema across the service-page inventory, then route only critical and high-confidence items into the implementation queue.",
    },
    "northline": {
        "executive_summary": "The page has strong local metadata and useful copy, but a noindex directive blocks the entire organic opportunity. Resolve indexability before spending time on smaller enhancements.",
        "priority_actions": [{
            "title": "Resolve the noindex directive first",
            "why": "The page cannot appear in organic search while its robots meta includes noindex.",
            "steps": "Confirm this is not a staging or compliance decision, remove noindex, add a self-canonical, and request indexing after deployment.",
            "evidence_ids": ["indexability.noindex", "technical.canonical_missing"],
        }],
        "metadata": {
            "title": "Botox in Denver | Northline Aesthetics",
            "description": "Natural-looking Botox treatments in Denver from experienced aesthetic injectors. Request a personalized consultation with Northline Aesthetics.",
            "title_length": 38,
            "description_length": 143,
            "title_within_limit": True,
            "description_within_limit": True,
        },
        "human_checks": [
            "Confirm whether noindex is intentional before changing production directives.",
            "Verify the service claims and injector language with a clinical or compliance owner.",
        ],
        "scale_note": "Treat indexability failures as portfolio-level alerts so they bypass routine content tickets and reach the technical owner immediately.",
    },
    "harbor": {
        "executive_summary": "The sampled page covers the core on-page and local foundations with no material automated issue. The next useful work requires live ecosystem data rather than speculative rewriting.",
        "priority_actions": [],
        "metadata": {
            "title": "Microneedling in Tampa | Harbor Skin & Laser",
            "description": "Explore personalized microneedling in Tampa at Harbor Skin & Laser. Learn about candidacy, treatment, recovery, and consultation options.",
            "title_length": 44,
            "description_length": 137,
            "title_within_limit": True,
            "description_within_limit": True,
        },
        "human_checks": [
            "Validate NAP against the live Google Business Profile and major citations.",
            "Use Search Console queries and conversions to decide whether the page needs expansion.",
            "Run Rich Results and Schema.org validation against the deployed markup.",
        ],
        "scale_note": "Move clean pages into monitoring instead of generating unnecessary work; reserve team capacity for sites with evidenced blockers.",
    },
}


def get_demo_site(site_id: str) -> dict[str, str]:
    for site in DEMO_SITES:
        if site["id"] == site_id:
            return site
    raise KeyError(site_id)
