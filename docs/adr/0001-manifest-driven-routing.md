# ADR 0001: Manifest-driven routing for the analyser family

**Date:** 2026-05-23
**Status:** Accepted

## Context

`auto-analyser` routed files to family members via a hard-coded extension→analyser
map (`detector._ROUTES`) plus a per-analyser `formats` list in its config. This
duplicated routing knowledge that each analyser already owns, and meant adding or
changing an analyser's accepted formats required editing `auto-analyser` too.

Separately, the family needed a way to express that some members are **not**
auto-routable — explicit-only *content interpretations* (e.g. `conversation-analyser`)
that reinterpret bytes already claimed by another analyser, and so must be invoked
deliberately rather than detected from a file extension.

## Decision

Every family member exposes a small capability **manifest**:

```
name, version, role, accepts, extensions, auto_routable, produces
```

surfaced three ways: a module constant `MANIFEST`, a `manifest` CLI subcommand, and
`GET /manifest`. `auto-analyser` builds its routing table by querying the manifests
of the analysers in its config (HTTP or CLI), excluding any with
`auto_routable=False`. The static `_ROUTES` map is retained as an **offline
fallback** so routing still works when services are down (manifests merge over it,
so live manifests win). This trades a small amount of hand-maintained duplication
for robustness; a future option is to generate `_ROUTES` from manifests.

## Consequences

- An analyser's accepted formats live in one place (its own manifest); adding an
  analyser no longer requires editing `auto-analyser`'s routing.
- `auto_routable=False` cleanly marks explicit-only members (conversation-analyser,
  git-analyser, bundle-analyser) so they are never silently auto-routed.
- When a target service is offline, routing falls back to `_ROUTES`, so the user
  reaches the helpful "is the service running? / is it installed?" dispatch error
  instead of a misleading "unknown format".
- `video-analyser` is an outlier (Gradio UI, no FastAPI/HTTP API); it ships a
  manifest constant but no `/manifest` endpoint and routes via the fallback.
