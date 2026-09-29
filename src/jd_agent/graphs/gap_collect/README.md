# Gap collect graph — `gaps` output reference

The gap collect graph compares a job description’s skill demand to a candidate’s
evidence on the Skill ontology graph. The result is a single JSON document stored
on `user_resume_builder.gaps` (jsonb) after `save_gaps`.

**Invoke:** `{"session_id": "<user_resume_builder uuid>"}` — see
`gap_collect_graph.py` for the full node pipeline.

## Top-level shape

After the graph finishes, `gaps` has this structure:

```json
{
  "schema_version": 1,
  "meta": { ... },
  "review": { ... },
  "skills": [ ... ],
  "interview": { ... }
}
```


| Key              | Added by       | Purpose                                                                                    |
| ---------------- | -------------- | ------------------------------------------------------------------------------------------ |
| `schema_version` | `compute_gaps` | Payload version (currently `1`).                                                           |
| `meta`           | `compute_gaps` | Aggregate scores, counts, resolution diagnostics, tuning thresholds.                       |
| `review`         | `compute_gaps` | Human-facing summary for the gap-review UI.                                                |
| `skills`         | `compute_gaps` | One row per skill in the **demand closure** (JD seeds plus graph-propagated requirements). |
| `interview`      | `rank_queue`   | Ordered gap-interview queue, theme bundles, and stopping hints.                            |


Graph state also carries `interview_candidates` between `compute_gaps` and
`rank_queue`; that list is **not** persisted—only `gaps.interview` is saved.

---



## Background: how scores are computed

Understanding the per-skill fields helps interpret the output:

1. **Demand closure (**`d`***)** — Starting from JD skills, propagate forward along
  `REQUIRES` / `USES` edges: needing skill A also needs its prerequisites and
   tools. Domain skills are excluded.
2. **Supply closure (**`s`***)** — Starting from evidence-backed skills (noisy-OR
  propagation with calibrated α coefficients), estimate implied mastery on
   related skills even when not named on the resume.
3. **Per-skill gap** — For demand `d`*, supply `s*`, weight `w`, exponent `p`
  (currently `1`):
   `gap = w × d* × max(0, d* − s*)^p`
4. **Fit** — Aggregate match score in `[0, 1]`:
  `fit = 1 − (Σ gap) / (Σ w × d*²)`
5. **Three zones** — Each demand-closure skill is labeled for product UX:

  | Zone        | Meaning                                                                                                                                      |
  | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
  | `confirmed` | Explicit evidence or held skill on the profile (`s_explicit > 0`).                                                                           |
  | `latent`    | Not stated, but the graph suggests the candidate may already have it (`s* > latent_delta` **or** high personalized PageRank vs held skills). |
  | `true_gap`  | Neither explicit nor structurally implied—treat as a real gap to plan for.                                                                   |

   Latent sub-kinds: `latent_kind` is `implied` (supply closure) or `adjacent`
   (graph proximity via PPR), or empty for other zones.

---



## `meta`


| Field                       | Type     | Meaning                                                                                                                                                                                                  |
| --------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fit`                       | number   | Current aggregate fit `[0, 1]`. Same basis as `review.headline`.                                                                                                                                         |
| `fit_if_all_latent`         | number   | Counterfactual fit if every **latent** skill were confirmed at full mastery: latent ids are added to supply seeds, supply closure is re-run, then fit is recomputed (includes propagation to neighbors). |
| `fit_uplift_latent`         | number   | `max(0, fit_if_all_latent − fit)`. Potential fit gain from the interview confirming all hidden skills.                                                                                                   |
| `zone_counts`               | object   | Counts of skills in `confirmed`, `latent`, `true_gap`.                                                                                                                                                   |
| `jd_skill_count`            | int      | Number of skills extracted from the JD before graph resolution.                                                                                                                                          |
| `resolved_count`            | int      | JD skills successfully mapped to Skill graph node ids.                                                                                                                                                   |
| `unresolved`                | string[] | JD skill names/ids that could not be resolved to the graph.                                                                                                                                              |
| `thresholds.latent_delta`   | number   | `s*` above this ⇒ structurally “implied” latent (default `0.35`).                                                                                                                                        |
| `thresholds.ppr_rho`        | number   | Personalized PageRank threshold (percentile over demand closure) for “adjacent” latent.                                                                                                                  |
| `thresholds.ppr_percentile` | int      | Percentile used to compute `ppr_rho` (default `70`).                                                                                                                                                     |
| `thresholds.gap_p`          | int      | Deficit exponent in the gap formula (default `1`).                                                                                                                                                       |


---



## `review`

Display-oriented blocks; safe to show candidates without exposing raw closure math.


| Field                              | Type          | Meaning                                                                                                                 |
| ---------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `headline`                         | string        | One-line summary: fit %, matched count, latent count, true-gap count.                                                   |
| `latent_fit`                       | object | null | Present when `zone_counts.latent > 0`; otherwise `null`.                                                                |
| `latent_fit.if_all_confirmed`      | number        | Same as `meta.fit_if_all_latent`.                                                                                       |
| `latent_fit.uplift`                | number        | Same as `meta.fit_uplift_latent`.                                                                                       |
| `latent_fit.uplift_percent_points` | int           | Uplift expressed as percentage points (e.g. `11` for +11 pts).                                                          |
| `latent_fit.sentence`              | string        | Ready-made copy for the UI.                                                                                             |
| `critical_path`                    | string        | Longest `REQUIRES` chain among **true_gap** skills, as a sentence (learning order hint), or a fallback message if none. |
| `themes`                           | array         | Louvain communities over unmet skills (latent + true_gap).                                                              |
| `themes[].id`                      | string        | Stable id, e.g. `theme-1`.                                                                                              |
| `themes[].label`                   | string        | Human label (PART_OF parent name, Knowledge name, or first member).                                                     |
| `themes[].size`                    | int           | Number of skills in the community.                                                                                      |
| `themes[].bars`                    | object        | Counts `{ confirmed, latent, true_gap }` within the theme (usually unmet-only members).                                 |
| `themes[].skill_ids`               | string[]      | Member skill node ids.                                                                                                  |
| `by_skill_type`                    | object        | Per `skill_type` rollup: zone counts plus `total_gap` (sum of row gaps).                                                |
| `hard_vs_soft`                     | object        | Among non-confirmed skills: `hard` = no supply signal (`s* ≤ 0`), `soft` = partial signal.                              |


---



## `skills[]`

Each element is one skill in the demand closure, sorted by descending `gap`.


| Field               | Type    | Meaning                                                                             |
| ------------------- | ------- | ----------------------------------------------------------------------------------- |
| `skill_id`          | string  | Skill graph node id.                                                                |
| `name`              | string  | Display name.                                                                       |
| `skill_type`        | string  | Ontology type (e.g. Tool, Knowledge). Domain nodes are not in closures.             |
| `zone`              | string  | `confirmed` | `latent` | `true_gap`.                                                |
| `latent_kind`       | string  | For latent: `implied` | `adjacent`; otherwise `""`.                                 |
| `requirement_level` | number  | Priority in `[0, 1]` from the JD skill. `1` is required (highest). Closure-only skills default to `1`. |
| `listed_on_jd`      | boolean | `true` if listed on the JD seed list; `false` if only pulled in via demand closure. |
| `weight`            | number  | Importance weight in fit/gap (currently default `1.0` for all).                     |
| `d_star`            | number  | Demand closure strength—how much the role needs this skill.                         |
| `s_star`            | number  | Supply closure mastery—how much the profile implies this skill.                     |
| `s_explicit`        | number  | Direct evidence: `1.0` if evidence-backed, `0.0` if held-only or absent.            |
| `ppr`               | number  | Personalized PageRank score (proximity to held skills in the demand neighborhood).  |
| `gap`               | number  | Weighted deficit contributing to `meta.fit`.                                        |
| `hard`              | boolean | `true` when `s_star ≤ 0` (no supply signal).                                        |


**UI hint:** Prefer `zone`, `name`, `latent_kind`, `listed_on_jd`, and `hard` for
users; use `d_star`, `s_star`, `ppr`, and `gap` for analytics or debug.

---



## `interview`

Built in `rank_queue` from latent and true_gap skills. Queue order uses
**expected yield**, not raw gap size:

`EV = P(has) × weight × gap`, with `P(has) ≈ σ(a·s* + b·PPR_norm − c)` (placeholder
coefficients; ordering only until calibrated on confirm/deny outcomes).

### `interview.queue[]`


| Field                | Type     | Meaning                                                               |
| -------------------- | -------- | --------------------------------------------------------------------- |
| `round_id`           | string   | Stable round key, `skill::<skill_id>`.                                |
| `skill_id`           | string   | Target skill node id.                                                 |
| `skill_name`         | string   | Display name.                                                         |
| `skill_type`         | string   | Ontology type.                                                        |
| `zone`               | string   | Usually `latent` or `true_gap`.                                       |
| `latent_kind`        | string   | Same as in `skills`.                                                  |
| `expected_yield`     | number   | Interview priority score (EV).                                        |
| `p_has`              | number   | Prior probability the candidate already has the skill (uncalibrated). |
| `technique`          | string   | Probe strategy (see below).                                           |
| `bridge_skill_ids`   | string[] | Up to 3 held neighbor ids to anchor the question.                     |
| `bridge_skill_names` | string[] | Names for those anchors.                                              |
| `prerequisite_names` | string[] | Up to 3 held `REQUIRES` prerequisites of the target.                  |
| `theme_id`           | string   | Links to `review.themes[].id`.                                        |
| `probe_hint`         | string   | Short guidance for the interviewer for this technique.                |


**Technique values**


| Value                        | Intent                                                                                   |
| ---------------------------- | ---------------------------------------------------------------------------------------- |
| `requires_prerequisite_path` | Candidate holds prerequisites—ask how they applied them without naming the target skill. |
| `bridge_neighbor`            | Anchor on a related held skill and ask how that work touched this area.                  |
| `confirm_implied`            | Graph implies the skill—one open confirm question, don’t lead with the name.             |
| `open_recall`                | Open recall: what they worked on in this area; let them name tools.                      |




### `interview.bundles[]`


| Field       | Type     | Meaning                                             |
| ----------- | -------- | --------------------------------------------------- |
| `theme_id`  | string   | Theme id from `review.themes`.                      |
| `round_ids` | string[] | `round_id`s in that theme, in expected-yield order. |


