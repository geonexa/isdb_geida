"""
Single source of truth for GEIDA's sections. The navbar, the home page and the
placeholder pages all read from here, so a module is added in one place.
"""

PRIMARY = [
    # Order follows the development plan: the IsDB project cycle is the spine, so
    # Projects comes first (its Results tab is where evidence meets the Results Framework);
    # Data Catalog (the Geo-Portal, at /geoportal) is the everyday (curated) map; Analytics is the full GIS toolbox.
    {
        "slug": "projects",
        "name": "Projects",
        "icon": "folder-kanban",
        "summary": "One space per IsDB project: area of influence, Results Framework with CRIs, analyses by phase and evidence.",
        "features": [
            "Onboard a project: wizard, bulk import or submission form",
            "Area of influence and Results Framework with CRI codes",
            "Curated analyses by phase: preparation, implementation, completion",
            "Evidence records reviewed before they reach an indicator",
        ],
    },
    {
        "slug": "geoportal",
        "name": "Data Catalog",
        "icon": "map",
        "summary": "Browse raster and vector layers for every member country, compare dates and download clipped data.",
        "features": [
            "Layer catalogue by country, theme and date",
            "Time slider and side-by-side date comparison",
            "Draw or upload a project boundary",
            "Download data clipped to your area",
        ],
    },
    {
        "slug": "analytics",
        "name": "Analytics",
        # Add "roles": ["analyst"] to show it only to staff, reviewers and the "GEIDA analysts" group.
        "icon": "scan-search",
        "summary": "The full GIS toolbox for analysts and trainers: layers, styling, processing and models.",
        "features": [
            "Full GeoLibre workspace with processing tools",
            "Build and test analysis chains",
            "Promote a proven chain to a curated module",
            "For analysts and trainers",
        ],
    },
]

KNOWLEDGE_HUB = [
    {
        "slug": "training",
        "name": "Training and certification",
        "icon": "graduation-cap",
        "summary": "Foundation and Advanced GEIDA certification for IsDB staff and Regional Hubs.",
        "url": "https://geida-lms.terrawatch.net/",  # GEIDA LMS (external site)
        "features": [],
    },
    {
        "slug": "case-studies",
        "name": "Case studies",
        "icon": "book-open",
        "summary": "How Earth observation has supported real development projects.",
        "features": [],
    },
    {
        "slug": "user-guide",
        "name": "User guide",
        "icon": "life-buoy",
        "summary": "Step-by-step help for each part of GEIDA.",
        "features": [],
    },
]

ALL = {m["slug"]: m for m in PRIMARY + KNOWLEDGE_HUB}

# The IsDB project cycle, generalized for every sector. Images live in
# frontend/public/img/cycle/<key>.jpg (see docs/home-images.md for the prompts).
# "phase" is the GEIDA project workspace the stage uses.
PROJECT_CYCLE = [
    {
        "key": "pcn",
        "stage": "Identification",
        "instrument": "PCN",
        "question": "Is this the right place?",
        "phase": "Preparation",
        "image": "/img/cycle/pcn.jpg",
        "alt": "Aerial view over a semi-arid river valley with villages and farmland",
        "outputs": [
            "Site screening and suitability",
            "Terrain, land cover and water at a glance",
            "Exposure to floods, drought and heat",
            "Access to roads, settlements and services",
        ],
        "value": "Stronger concept notes, fewer unsuitable sites and better-prepared missions.",
    },
    {
        "key": "pprr",
        "stage": "Preparation",
        "instrument": "PPRR",
        "question": "What is the starting point?",
        "phase": "Preparation",
        "image": "/img/cycle/pprr.jpg",
        "alt": "Field team with a tablet talking with community members at the edge of a village",
        "outputs": [
            "Baseline of land, people and services",
            "Who the project can reach",
            "Climate and hazard context",
            "Data gaps flagged early",
        ],
        "value": "A clearer project area and an evidence-based case for the investment.",
    },
    {
        "key": "pad",
        "stage": "Appraisal and design",
        "instrument": "PAD",
        "question": "How will success be measured?",
        "phase": "Preparation",
        "image": "/img/cycle/pad.jpg",
        "alt": "Planning team around a table with a large satellite map of the project area",
        "outputs": [
            "Agreed area of influence",
            "Results Framework linked to IsDB Core Result Indicators",
            "Environmental and social screening",
            "Baseline values kept for later comparison",
        ],
        "value": "Better design decisions and indicators that can be verified later.",
    },
    {
        "key": "piasr",
        "stage": "Implementation",
        "instrument": "PIASR",
        "question": "Is it on track?",
        "phase": "Implementation",
        "image": "/img/cycle/piasr.jpg",
        "alt": "Aerial view of construction works in progress with machinery and workers",
        "outputs": [
            "Works progress seen from space",
            "Change and anomaly alerts before missions",
            "Indicator progress backed by evidence",
            "Better-targeted field visits",
        ],
        "value": "Issues spotted earlier, and supervision missions that go where they are needed.",
    },
    {
        "key": "pcr",
        "stage": "Completion",
        "instrument": "PCR",
        "question": "What was delivered?",
        "phase": "Completion",
        "image": "/img/cycle/pcr.jpg",
        "alt": "Completed infrastructure in use: green irrigated fields along a new canal",
        "outputs": [
            "Before-and-after evidence",
            "Outputs checked against the Results Framework",
            "Indicator values with their data and method",
            "Maps ready for the completion report",
        ],
        "value": "Objective verification of outputs and a credible results story.",
    },
    {
        "key": "pper",
        "stage": "Post-evaluation",
        "instrument": "PPER",
        "question": "Did the benefits last?",
        "phase": "Completion",
        "image": "/img/cycle/pper.jpg",
        "alt": "Thriving farmland and a busy village years after the project ended",
        "outputs": [
            "Long-term trends inside the project area",
            "Comparison with similar areas outside it",
            "Persistence of outcomes",
            "Lessons for the next project",
        ],
        "value": "Independent evidence of impact, and better design of future projects.",
    },
]



# The three Phase II components from the GEIDA framework.
COMPONENTS = [
    {
        "key": "A",
        "name": "Technology",
        "title": "Platform development and operational integration",
        "image": "/img/comp-technology.jpg",
        "text": "A scalable, secure platform that turns the EO Toolkit's knowledge base into an engine for the Bank's daily work.",
        "items": ["Data Catalog", "AI-powered analytics", "Sector dashboards", "Automated EO indicators"],
    },
    {
        "key": "B",
        "name": "Action",
        "title": "Sector project integration and deep-dives",
        "image": "/img/comp-action.jpg",
        "text": "EO tools embedded in real pipeline projects, with results checked against field measurements.",
        "items": ["10 to 15 projects onboarded", "Uganda pilot", "Mali and Azerbaijan deep-dives", "Field validation"],
    },
    {
        "key": "C",
        "name": "People",
        "title": "Capacity building and certification",
        "image": "/img/comp-people.jpg",
        "text": "Certified staff and Regional Hubs who use GEIDA in their own projects, supported by a Knowledge Hub.",
        "items": ["Foundation level, about 100 staff", "Advanced level, about 50 staff", "Regional Hubs", "GEIDA Knowledge Hub"],
    },
]
