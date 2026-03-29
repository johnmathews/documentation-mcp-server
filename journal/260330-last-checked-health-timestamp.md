# Add last_checked timestamp to health endpoint

**Date:** 2026-03-30

## Problem

The health endpoint's `last_indexed` timestamp only updates when file content actually
changes (new upserts to the knowledge base). For repos with no recent commits, this
appeared as stale timestamps like "5d ago", making it look like the sync system was
broken when it was actually working correctly.

Verified by checking all remote repos via `git ls-remote` — every single one matched
the container's HEAD. The repos genuinely had no new commits.

## Solution

Added a `last_checked` timestamp that updates every time a source is successfully synced,
regardless of whether content changed. The health endpoint now returns both:

- `last_indexed` — when content was last actually re-indexed (content hash changed)
- `last_checked` — when the source was last successfully synced/checked for changes

This lets the UI distinguish "no changes to detect" from "detection is broken."

## Changes

- `Ingester._last_check_times` dict tracks per-source sync timestamps
- `Ingester.get_last_check_times()` exposes timestamps to the health endpoint
- Health endpoint merges `last_checked` into each source's summary
- 6 new tests covering the feature
