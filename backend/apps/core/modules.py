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



# What GEIDA is built on, shown on the home page (general: no project names, counts or countries).
COMPONENTS = [
    {
        "key": "A",
        "name": "Technology",
        "title": "One platform for Earth observation",
        "image": "/img/comp-technology.jpg",
        "text": "Satellite data, ready-made analyses and maps in one secure place, built into the way projects "
                "are prepared, supervised and evaluated.",
        "items": ["Data Catalog of global and national layers", "Analyses for every sector",
                  "Interactive maps and print layouts", "Reports traced to their data"],
    },
    {
        "key": "B",
        "name": "Practice",
        "title": "Evidence inside real projects",
        "image": "/img/comp-action.jpg",
        "text": "Earth observation applied across sectors and regions, from site screening to post-evaluation, "
                "with results checked against information from the field.",
        "items": ["Projects across all sectors", "Sector deep-dives", "Evidence for the Results Framework",
                  "Field validation"],
    },
    {
        "key": "C",
        "name": "People",
        "title": "Skills that stay with the Bank",
        "image": "/img/comp-people.jpg",
        "text": "Training and certification so staff and partners can use Earth observation in their own work, "
                "supported by Regional Hubs and a shared Knowledge Hub.",
        "items": ["Foundation and advanced training", "Certification", "Regional Hubs", "GEIDA Knowledge Hub"],
    },
]
