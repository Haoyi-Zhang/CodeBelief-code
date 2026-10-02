# Resources, inputs, and licenses

## Execution envelope

The authoritative runner launches one child at a time, pins it to one available CPU where supported, and applies:

* 512 MiB address-space ceiling;
* 30-second soft and 31-second hard CPU limits;
* 32-second wall timeout;
* single-thread environment variables for common numeric runtimes, although the artifact imports no numeric package.

The artifact uses the Python standard library only. It makes no network calls and uses no compiler, solver, GPU, device, service, external model, private dataset, or human participant. Individual tasks are deterministic except for measured duration and OS-reported peak RSS.

## Input inventory

### Original finite fixtures

`inputs/controls/` and `inputs/history/` are original bounded source-text fixtures used by the inherited selection-semantics pilot. They are text only and are never compiled or executed. `inputs/index.json` fixes their order and declared roles.

### Public tagged excerpts

`inputs/public/manifest.json` identifies six exact excerpts:

| Project | Before | After | License | Retained change used for anchoring |
|---|---|---|---|---|
| cJSON | v1.7.17 | v1.7.18 | MIT | explicit `valuestring == NULL` guard |
| inih | r58 | r59 | BSD-3-Clause | explicit consumption of an overlong line through newline |
| mjson | 1.2.6 | 1.2.7 | MIT | integer-digit loop guard changes from remaining value to place multiplier |

Matching notices are stored under `inputs/public/licenses/`. The manifest includes repository URL, tag, upstream path, and source-line description. No VCS history is required at reproduction time.

## Output inventory

`results/expected-files.json` lists 85 deterministic outputs. Large case-level evidence is retained as CSV or JSON Lines rather than summarized away. Machine-dependent files such as `joint-public-timings.jsonl`, `joint-oracle-timings.jsonl`, `joint-scaling-timings.csv`, logs, and reproduction measurements are not included in byte-equality expectations.

The largest retained scientific files are the exact population rows and Horn cases. All remain far below project download, expansion, memory, CPU, and archive ceilings.

## License separation

* Original artifact code and original fixtures: root `LICENSE` (MIT).
* cJSON and mjson excerpts: retained MIT notices.
* inih excerpts: retained BSD-3-Clause notice.
* Scholarly papers: cited only; no paper PDF is redistributed.
* ACM template assets: live only in the project paper directory and retain the supplied template license; they are not copied into the standalone artifact.

## Measurements

Resource measurements report process-level observations from the execution host. `child_peak_rss_kib_cumulative` is the platform's cumulative child high-water mark and is not added to the parent value as if both peaks were simultaneous. Timing is descriptive and excluded from scientific performance claims.
