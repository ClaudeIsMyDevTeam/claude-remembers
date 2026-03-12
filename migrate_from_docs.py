"""
One-time migration: populate memory.db from knowledge extracted
from project documentation across srsbznss-inventory, srsbznss-email,
srsbznss-test, and existing MEMORY.md notes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from memory import remember, MemoryType

# ---------------------------------------------------------------------------
# srsbznss-inventory
# ---------------------------------------------------------------------------

remember(
    "srsbznss-inventory is a PHP + React inventory management system "
    "for tracking sneakers/resell items. It manages inventory with CRUD ops, "
    "CSV bulk import, automatic profit calculations, and multi-user support.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory stack: PHP backend (no framework), React 18 via CDN "
    "with Babel JSX transpilation, Tailwind CSS via CDN, MySQL/MariaDB database. "
    "Single-page app in inventory.html (1100+ lines). Separate mobile.html for mobile.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory deployment: GitHub Actions FTP auto-deploy on push to main. "
    "Hosted on NameCheap at /inventory/ directory. "
    "Production DB name: srsbdhhi_inventory. Secrets: FTP_SERVER, FTP_USERNAME, FTP_PASSWORD.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory backend pattern: all financial calculations (total_cost = qty * unit_cost, "
    "net = payout - total_cost) happen server-side in config.php. "
    "Always use calculateTotalCost() and calculateNet() from config.php — never calculate in CRUD endpoints directly.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory security posture: 9.5/10. Has CSRF token protection on all "
    "state-changing operations, login rate limiting (5 attempts/30min per username, "
    "10/15min per IP), HTTPS enforcement + HSTS, bcrypt passwords, "
    "SQL injection protection via prepared statements, Content-Security-Policy. "
    "PhpService on frontend automatically handles CSRF tokens.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/SESSION_SUMMARY_2025-11-03.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory uses database-backed remember-me tokens (not PHP sessions) "
    "because NameCheap shared hosting runs cron jobs that delete PHP session files "
    "regardless of gc_maxlifetime settings. Tokens stored in remember_me_tokens table "
    "with split-token security (selector + hashed validator). 1-year expiration.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/REMEMBER_ME_IMPLEMENTATION.md",
    confidence=0.95,
)

remember(
    "srsbznss-inventory in-progress feature (as of Nov 2025): tabbed interface with "
    "Active / Hold / Sold tabs. Active = not sold AND not on hold. "
    "Hold = hold==1 AND sold==0. Sold = sold==1. "
    "New DB columns needed: purchase_date, hold, hold_until, hold_location, source, selling_site, sold_date. "
    "SQL script add_new_columns.sql prepared but may not have been run yet.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/PLAN_tabbed_interface.md",
    confidence=0.85,
)

remember(
    "srsbznss-inventory sticky table implementation uses z-index layering: "
    ".sticky-column (z-10), .sticky-header (z-20), .sticky-header.sticky-column (z-30). "
    "Must maintain these when modifying table structure.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.9,
)

remember(
    "srsbznss-inventory mobile_list.html has pending updates to sync with inventory.html: "
    "user profile modal, username link styling, net column right-alignment. "
    "Key gotcha: global CSS rule `table input:not(.net-column-field) { border: none !important }` "
    "overrides Tailwind — must use inline styles for critical styling in modal inputs.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/mobile_list_updates_checklist.md",
    confidence=0.85,
)

remember(
    "srsbznss-inventory frontend state: React Context API (InventoryContext) manages "
    "items array, CRUD ops, validation state, delete confirmation modal. "
    "Frontend updates state optimistically and reverts on error via loadItems(). "
    "useFieldValidation hook handles client-side validation.",
    MemoryType.PROJECT,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.9,
)

# ---------------------------------------------------------------------------
# srsbznss-email
# ---------------------------------------------------------------------------

remember(
    "srsbznss-email is a Python tool that extracts order confirmations and shipping "
    "info from Gmail accounts using OAuth2 and Claude API. "
    "Exports consolidated order data to CSV. MySQL support planned. "
    "Uses google-api-python-client + anthropic SDK. Has a venv setup.",
    MemoryType.PROJECT,
    source="srsbznss-email/README.md",
    confidence=0.9,
)

remember(
    "srsbznss-email default Claude model: claude-sonnet-4-20250514. "
    "Cost estimate: ~$0.003-0.01 per email, ~$0.30-1.00 per 100 emails. "
    "Gmail API is free within quota. OAuth credentials stored in credentials/client_secret.json.",
    MemoryType.PROJECT,
    source="srsbznss-email/README.md",
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# srsbznss-test
# ---------------------------------------------------------------------------

remember(
    "srsbznss-test is a standalone PHP sandbox for testing features before integrating "
    "into the main inventory app. Live URL: http://srsbznss.com/test/. "
    "Stack: PHP, React 18 via CDN, Tailwind CSS via CDN, Babel. "
    "Local: `php -S localhost:8001`. API keys in config_private.php.",
    MemoryType.PROJECT,
    source="srsbznss-test/README.md",
    confidence=0.9,
)

# ---------------------------------------------------------------------------
# User profile (inferred from projects)
# ---------------------------------------------------------------------------

remember(
    "User runs multiple projects under the 'srsbznss' brand. "
    "These appear to be personal/small business tools: "
    "an inventory management system (srsbznss-inventory), "
    "an email order extractor (srsbznss-email), "
    "and a feature testing sandbox (srsbznss-test).",
    MemoryType.USER,
    source="project documentation review",
    confidence=0.8,
)

remember(
    "User's primary project stack across srsbznss projects: "
    "PHP for backend, React 18 via CDN (not build-tool-based), "
    "Tailwind CSS via CDN, MySQL. Python for standalone tools. "
    "Hosting on NameCheap shared hosting.",
    MemoryType.USER,
    source="project documentation review",
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------

remember(
    "srsbznss-inventory production database: srsbdhhi_inventory on NameCheap. "
    "phpMyAdmin available via NameCheap hosting panel. "
    "GitHub Actions handles FTP deployment on push to main.",
    MemoryType.REFERENCE,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.9,
)

remember(
    "srsbznss-inventory CLAUDE.md documents: full architecture, calculation patterns, "
    "deployment process, how to add new fields (5-step process), "
    "security notes, and sticky table z-index implementation. "
    "Path: /home/rhrad/projects/srsbznss-inventory/CLAUDE.md",
    MemoryType.REFERENCE,
    source="srsbznss-inventory/CLAUDE.md",
    confidence=0.95,
)

print("Migration complete.")
