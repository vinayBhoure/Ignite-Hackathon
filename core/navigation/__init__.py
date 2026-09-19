"""Live navigation for Track B: Google Routes API candidates, dose scoring on
the replayed zone layer, the PRD decision rule, assignment and reroute.

Kept separate from core/routing, core/exposure and core/dispatch (Track A's
modules) so the two tracks never edit the same files; it writes the same
graph shape (Route{provider:'google'}, PASSES_THROUGH{idx, seconds, bucket})
so Track A's code can take over without a migration.
"""
