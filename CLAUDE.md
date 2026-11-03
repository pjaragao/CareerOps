# CareerOps — guidance for Claude

## LinkedIn changes its pages under us
LinkedIn changes how it renders pages without notice, partly to break automations. Examples from late 2026:
- the single-post layout;
- the invite dialog moved into the shadow root of `#interop-outlet`;
- `/jobs/search/` now redirects to `/jobs/search-results/`, which drops the `#fragment` and uses cards without links.

Expect more of this. When a fix for a new layout lands:
- **Keep the old way working as a fallback. Do not replace it.** Try the new selector or flow first, and fall back to the previous one when it finds nothing. The old layout may come back, or may still be served to some accounts and regions.
- **Keep both layouts in the end-to-end fake** (`automation/tests/e2e/fake_linkedin.py`), so neither one breaks unnoticed.
- **Make a miss fail clearly.** It should raise an `error_code` (`selector_not_found`, `unexpected_layout`, `step_stuck`) with a screenshot, which sends the action to the Claude fallback or to the user. It must never be a silent wrong click.
- **Before rewriting, look at the live page.** Use the artifacts in `/app/output/automation/<action id>/`, or CDP inside the automation container.
