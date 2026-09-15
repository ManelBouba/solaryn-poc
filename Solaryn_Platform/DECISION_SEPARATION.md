# Decision-stage correction — 2026-09-14

The physical workflow now distinguishes annual net AC energy, lifetime energy under the declared common degradation scenario, commercial NPV at supplied quotes, and the final review requirement. The previous recommendation section displayed the economic ordering alone.

`decision_chain.py` exports a versioned physical comparison with cell-temperature, off-STC response and rear-gain diagnostics, an explicit net AC top-two gap, and the physical engine's evidence reasons. Price changes cannot alter this physical comparison. Lifetime energy is independently displayed but follows annual energy when all candidates share the same degradation assumption. Commercial scenarios retain the existing financial equations. Exact ties share numerical rank and do not select a brand based on input order.

The UI shows unresolved separation within the existing 2% policy guardrail, rather than treating the numerical maximum as proof of superiority. This is a policy band, not a measured uncertainty interval. The final decision explains physical/commercial agreement or disagreement and does not automatically recommend a purchase.

The default candidate selection now includes the utility-compatible Canadian Solar HJT record alongside the original three. Rear-generation settings are visible, with an explicit warning that the front-only baseline omits bifacial rear output. No geometry or degradation assumptions are silently changed. Sites outside the recorded Riyadh fixture default to live NASA POWER. Older immutable results retain their original payloads and request a new analysis for the separated decision stages.

## Scientific scope

The hourly DC model and AC conversion equations are unchanged. The attached temperature-only diagnostic is not substituted for the full physics model. No manufacturer bonus, climate-specific technology preference or invented degradation model is introduced. Repeated leaders can be mathematically consistent; uncertainty and evidence limitations still control interpretation. The recorded SUPSI benchmark does not validate commercial product ranking.

## Validation

18 platform tests passed, including the real hourly physics/API benchmark, price-versus-physical-rank independence, yield-order reversal, exact ties, missing quotes and small-gap behavior. The separated decision layer was replayed on all four saved climate cases; each original three-module case remained unresolved within the net AC policy guardrail. Browser inspection verified the new sections against the saved Leuven result. JavaScript syntax validation passed.

Refresh the local platform page and run a new physical analysis. Its worker loads the current decision code on each run; historical analysis files are not rewritten.

## Running-app correction

The browser had been connected to a separate older procurement-only checkout, which did not expose the hourly physics workflow. The local server was switched to this corrected checkout after an online SQLite backup and an upgrade check preserving every original table row count. The preserved local database is selected by the root run_saved_workspace.py launcher. Fresh ZIP installations use the standard run.py setup.
