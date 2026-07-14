# Publication figure inventory

This is the registered inventory for the article _Code faster, cheaper and
better with opinionated templates_. Run `just bench-figures` to regenerate the
complete set from the append-only registry. Each ID below produces `.svg`,
`.png`, and `.csv` siblings; `manifest.json` records the source and CSV hashes.

## Common aggregation and provenance

All figures use one registry query shape. Group rows by `template.version`,
`provider`, `model`, `effort`, `app`, `variant`, `phase`, and `arm`; calculate
the arithmetic mean of each selected numeric metric; count rows as `runs`; and
collect sorted distinct `seed` values as `seeds`. Groups missing any metric
selected by a figure are omitted from that figure and its CSV. Sorting is by
the complete group key, so repeated exports of unchanged input are byte-for-byte
deterministic.

The group fields plus `runs` and `seeds` are present in every sibling CSV and in
each SVG point description. The SVG metadata and PNG `Provenance` text chunk
also inventory every point. Both formats embed the SHA-256 of the sibling CSV,
making the image-to-data relationship independently checkable.

## Figure set

| Figure ID | Claim supported | Registry query |
|---|---|---|
| `quality-vs-time` | Shows whether equal-or-better functional and judged outcomes take more or less elapsed time across models, efforts, template versions, and variants. | Common grouping; `AVG(probe_pass_rate)`, per-arm rate from `judge_primary_endpoint`, and `AVG(wall_time_seconds)`. Plot the two quality endpoints against wall-clock seconds. |
| `quality-vs-cost` | Shows whether quality gains survive the dollar-cost constraint rather than merely buying more model work. | Common grouping; `AVG(probe_pass_rate)`, per-arm rate from `judge_primary_endpoint`, and `AVG(cost_usd)`. Plot the two quality endpoints against USD. |
| `effort-actions` | Shows whether a template configuration changes how many interaction cycles and tool invocations the agent needs. | Common grouping; `AVG(tool_calls)` and `AVG(turns)`. Plot paired bars per group. |
| `effort-tokens` | Shows where model-context effort is spent and prevents cached input or reasoning tokens from being hidden in a single total. | Common grouping; `AVG(input_tokens)`, `AVG(cached_input_tokens)`, `AVG(output_tokens)`, and `AVG(reasoning_tokens)`. Plot one stacked bar per group. |

The judge value is the registry's position-consistent primary endpoint converted
to a per-arm rate: that arm's votes divided by all non-null bare, guardrails,
and tie values. It is not the diagnostic mean of rubric dimension scores.
