---
title: "Article Title Here"
published: false
description: "A short description of the post."
tags: ["tag1", "tag2"]
# cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/<slug>/cover.png"
# canonical_url: ""
# date: "2026-01-01T09:00:00Z"
---

<!--
  dev.to renders the frontmatter `title` as the page H1, so the body starts at
  `##`. A body-level `#` produces a second H1 and trips MD025.

  Frontmatter notes:
  - tags: at most 4, lowercase alphanumeric only. dev.to silently drops the 5th
    and lowercases the rest.
  - cover_image: must be an absolute raw URL. devto-cli does not rewrite it, so
    a relative ./assets/... path will not resolve on dev.to.
  - series: never hand-typed. To put this article in a series, save it at
    `articles/<series-slug>/<this-slug>.md` instead of flat under `articles/`
    (kebab-case dir, e.g. `pipeline-pattern`) — `series` is auto-derived and
    written by `scripts/apply_series_from_dir.py`.
  - date: only needed for scheduled publishing, alongside `published: false`.
-->

## Introduction

Open with the personal motivation or the discovery that made this worth writing.

## Core Concept

Explain the mechanism, driven by a diagram. Store D2 sources under
`articles/assets/<slug>/diagrams/NN-name.d2` and reference the rendered PNG —
assets always live at `articles/assets/<slug>/` regardless of where this
article file lives, so the relative path depends on this file's own depth:

![Diagram description](./assets/<slug>/diagrams/01-overview.png)
<!-- from a series article one level deep instead, use:
![Diagram description](../assets/<slug>/diagrams/01-overview.png) -->

## Deep Dive

Implementation details, cited against real upstream source with file and line
references.

## Hands-on

Runnable commands with real measured output.

```bash
echo "replace me"
```

## Conclusion

What the reader can now do, and where to go next.
