"""Custom Prometheus metrics for EazziDoc domain events.

Import the counters/histograms here and increment them at the relevant
call sites. The /metrics endpoint (wired in main.py via
prometheus-fastapi-instrumentator) exposes all registered metrics
for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram

# ── diagnoses ─────────────────────────────────────────────────────────────────

diagnoses_total = Counter(
    "eazzidoc_diagnoses_total",
    "Total diagnosis requests processed, by final status",
    ["status"],  # pending | ai_complete | failed | flagged
)

diagnosis_pipeline_seconds = Histogram(
    "eazzidoc_diagnosis_pipeline_seconds",
    "Wall-clock time for the full AI pipeline per diagnosis",
    buckets=[5, 10, 30, 60, 120, 300],
)

# ── emails ────────────────────────────────────────────────────────────────────

emails_sent_total = Counter(
    "eazzidoc_emails_sent_total",
    "Total emails sent successfully, by template type",
    ["template"],  # welcome | diagnosis_ready | appointment_* | settings_updated | contact
)

emails_failed_total = Counter(
    "eazzidoc_emails_failed_total",
    "Total email send failures, by template type",
    ["template"],
)

# ── user lifecycle ─────────────────────────────────────────────────────────────

registrations_total = Counter(
    "eazzidoc_registrations_total",
    "Total successful user registrations, by role",
    ["role"],  # patient | doctor
)

account_deletions_total = Counter(
    "eazzidoc_account_deletions_total",
    "Total GDPR account deletions, by role",
    ["role"],
)

# ── admin actions ─────────────────────────────────────────────────────────────

admin_actions_total = Counter(
    "eazzidoc_admin_actions_total",
    "Total admin mutations logged to the audit trail, by action",
    ["action"],
)
