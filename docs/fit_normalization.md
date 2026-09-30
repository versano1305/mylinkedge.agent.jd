# Fit normalization against ontology growth

The Skill ontology keeps growing: the skill-expansion pipeline
(`skills.ai.agents/notebooks/skill_expand/apply_edge_proposals.ipynb`) adds
LLM-proposed `REQUIRES` / `USES` / `ENABLES` / `PART_OF` edges. Before this
change, every added edge could only *raise* a candidate's fit, so fit scores
moved with the ontology rather than with the candidate. This document explains
why, what changed, and how to read the new fields in `gap_collect` and
`resume_generate`.

## The problem

For session `da8d372f-1f59-4901-b277-1a411e6e6a4f` (113 held skills, 76 JD
skills), the expansion took the gap collector's headline from about 25% to
89%, even though nothing about the candidate changed.

Measured on the live graph (37,182 Skill→Skill edges). The pre-expansion graph
is reproduced by dropping the 1,292 edges with `source = "LLM"`:

| Graph | Demand closure `d*` | Fit on JD-listed skills only | Fit | Degree-matched random profile |
| --- | --- | --- | --- | --- |
| Pre-expansion | 80 skills | 0.25 | 0.25 | 0.23 |
| Post-expansion | 280 skills | 0.91 | 0.89 | **0.90** |

The last column is the key finding. A random profile with the same number of
skills and the same degree mix scores 0.90 on the expanded graph. The raw 0.89
mostly reflects how saturated the graph is around this JD, not the candidate.

### Why raw fit inflates

1. **Noisy-OR compounds parallel paths.** Supply `s*` combined *every*
   incoming contribution over 3 hops: `s = 1 − Π(1 − αᵢ·sᵢ)`. Each new path
   into a skill can only raise it, and an expansion adds many parallel paths.
   For example, three independent 0.5 contributions give 0.875.
2. **Hubs pass full α to every neighbor.** `PART_OF` makes up 97% of the graph.
   A parent category passes `α = 0.55` to each child, and categories have a
   median of 30 children (up to 546). Owning one hub credits hundreds of skills.
3. **Absolute thresholds.** The latent zone used `s* > 0.35`. When the graph
   lifts `s*` everywhere, skills move from true gap to latent, from 18 to 236
   latent skills for this session. The "if all hidden skills check out"
   counterfactual inflates with them.
4. **More demand to cover.** The new `REQUIRES` / `USES` edges also grew the
   demand closure from 80 to 280 skills. These are generic prerequisites that
   a large profile tends to be credited with.

The same closures feed `resume_generate`: `fit_profile`, per-atom
licensing / `standalone_value`, and the greedy allocation `delta_fit`. So the
resume pipeline inherited the same drift.

## What changed

All changes live in the shared layer, so both graphs use one definition.

### 1. Density-damped supply propagation (`shared/skill_closures.py`)

- **Fan-out scaling.** Each arc's α is multiplied by
  `min(1, (SUPPLY_FANOUT_REF / fanout) ** SUPPLY_FANOUT_BETA)`. `fanout` is
  the number of arcs of the same edge type and direction leaving the source.
  A skill that "implies" 200 others passes less to each one.
- **Top-k noisy-OR.** Only the `SUPPLY_TOP_K` strongest contributions into a
  skill are combined, so extra parallel paths stop compounding.

| Constant | Value | Meaning |
| --- | --- | --- |
| `SUPPLY_FANOUT_REF` | `5` | Sources with at most 5 arcs of a type/direction are not damped. |
| `SUPPLY_FANOUT_BETA` | `0.5` | Damping exponent (`1/√` beyond the reference). |
| `SUPPLY_TOP_K` | `3` | Contributions combined per skill per hop. |

Values were chosen with a sweep on the pre- and post-expansion graphs. Stronger
damping (for example `ref=1`, `beta=1`) flattened raw fit further, but it made
the normalized score *less* stable for a genuinely matching profile, because it
also suppresses legitimate propagation.

**Fan-out is a property of the full graph.** `resume_generate` runs closures
over the pruned `demand["edges_subset"]`, and pruning drops arcs, which would
change fan-out. Every closure over a subset therefore takes the full-graph
`fanout=supply_fanout(edges, is_domain)`. With it, the pruned closure is still
identical to the full closure on `d*` (see `tests/unit/test_supply_edge_prune.py`).

Damping alone is not enough. On the live graph, raw fit still moves from 0.15
to 0.83 with damping on, because the expansion really does connect the
profile's skills to the JD. Part of that rise is legitimate graph knowledge.
The question the next section answers is how much of it is specific to *this*
candidate.

### 2. Chance-corrected fit (`shared/fit_baseline.py`)

The baseline is the mean fit of `BASELINE_SAMPLES = 32` random profiles scored
against the same demand closure on the same graph. Each random profile is built
by `DegreeMatchedSampler`: every seed skill is replaced by a random skill from
the same degree bucket (`⌊log₂(degree + 1)⌋`), keeping its seed weight. The
random profile therefore has the same **size** and the same **ontology
complexity** (hubs versus leaves) as the real one.

```text
fit_normalized = max(0, (fit − fit_baseline) / (1 − fit_baseline))
```

This is the share of the headroom above chance that the profile actually earns
(Cohen's-κ-style). When an expansion makes the graph denser around a JD, the
baseline rises by the same mechanism as the raw fit, and the normalized score
stays put.

- Sampling is deterministic. The RNG is seeded from the demand closure and
  the seeds, so re-running a session gives the same baseline.
- The baseline runs on the pruned supply subset with full-graph fan-out. On
  the live graph, a full `compute_gaps` run including both baselines takes
  well under a second.
- `fit_if_all_latent` is normalized against a baseline for the *augmented*
  seed set (profile plus all latent skills), because a larger profile has a
  higher chance level.

### 3. Chance-corrected latent zone (`shared/gap_zones.assign_zone`)

`assign_zone(..., s_star_baseline=...)` compares the chance-corrected supply
`(s* − s*_baseline) / (1 − s*_baseline)` with `LATENT_DELTA`, instead of the
raw `s*`. Here `s*_baseline` is the mean `s*` of the random profiles for that
skill. A skill the graph credits to almost any profile is no longer "you may
already have this". Both `gap_collect` and `resume_generate.score_demand`
pass the baseline. `resume_generate` licensing reads these zones, so implied
licensing becomes more conservative, never less. The PPR "adjacent" rule is
unchanged, because its threshold is already a percentile.

### 4. Diagnostics

- `fit_explicit` is the fit from seed evidence alone, with no propagation.
  If this stays flat while `fit` jumps, the change came from the ontology.
- `ontology` is `{edge_count, edge_hash, supply: {...}}`, stamped on
  `gaps.meta`, `demand`, and the resume trace. Two scores are only comparable
  when their fingerprints match.

## Results

Same sessions, real graph, new code (`fit` is damped raw fit):

| Session | Graph | `fit` | `fit_explicit` | `fit_baseline` | **`fit_normalized`** | Latent | Normalized fit if all latent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `da8d372f…` | pre | 0.15 | 0.08 | 0.14 | **0.01** | 18 | 0.20 |
| `da8d372f…` | post | 0.83 | 0.07 | 0.85 | **0.00** | 104 | 0.13 |
| `85bff9d6…` | pre | 0.24 | 0.15 | 0.16 | **0.10** | 18 | 0.15 |
| `85bff9d6…` | post | 0.67 | 0.11 | 0.64 | **0.10** | 149 | 0.10 |

Raw fit still moves with the ontology, while `fit_normalized` stays within
±0.01. As a check that the normalized score still rewards real matches, a
synthetic profile holding half the JD's listed skills scores 0.56 before and
0.51 after expansion.

For `da8d372f…` the honest reading is that this profile covers this JD at
about chance level. The previous 89% headline came from the ontology.

The latent counts after expansion (104 and 149) are larger than before because
the demand closure itself grew (from 80 to 280 skills for `da8d372f…`). For
that session the latent share of the closure goes from 23% to 37% across the
expansion. With the previous code it went to 84%.

## Where the fields appear

**`gap_collect` → `user_resume_builder.gaps`** (see
[`gap_collect/README.md`](../src/jd_agent/graphs/gap_collect/README.md)):

- `meta.fit`, `meta.fit_if_all_latent`, `meta.fit_uplift_latent`: raw
  (damped) scores, kept for analytics and backward compatibility.
- `meta.fit_normalized`, `meta.fit_if_all_latent_normalized`,
  `meta.fit_uplift_latent_normalized`, `meta.fit_baseline`,
  `meta.fit_baseline_sd`, `meta.fit_explicit`, `meta.ontology`: new.
- `review.headline` and `review.latent_fit` now use the **normalized**
  values.
- `skills[].s_star_baseline`: new per-skill chance level.

**`resume_generate`:**

- `demand.fit_profile_normalized`, `fit_profile_baseline`,
  `fit_profile_baseline_sd`, `fit_profile_explicit`, `ontology`.
- `allocation.resume_fit_baseline`, `allocation.resume_fit_normalized`. The
  baseline uses random profiles the size of the selected resume seeds.
- `trace.fit.{before_interview_normalized, profile_baseline,
  profile_normalized, resume_baseline, resume_normalized, ontology}`.
- Atom selection still maximizes raw `delta_fit`. For a fixed JD and seed
  count, the normalization is a monotone transform, so it would not change
  which atoms win. The damping from section 1 does change the gains.

## Known limits and follow-ups

- **Stored scores are not re-computed.** Sessions saved before this change
  keep their old `gaps`. Re-run `gap_collect` to refresh them, and compare
  only scores whose `meta.ontology.edge_hash` match.
- **Provenance weighting.** Expansion edges carry `source = "LLM"` in Neo4j,
  but `mylinkedge_agent_tools.skills` does not load edge properties. Loading
  them would allow a per-source α multiplier, for example trusting curated
  edges more than LLM edges.
- **Demand-closure growth.** The expansion's new `REQUIRES` / `USES` edges add
  implied prerequisites to `d*`, which grows the number of rows and zone counts.
  Fit is a ratio, so this does not inflate it by itself, but counts such as
  "N to plan for" still grow with the ontology.
- **Calibration.** The damping constants and `BASELINE_SAMPLES` were tuned
  on two sessions. Re-check them with a before/after edge snapshot after large
  expansions.
