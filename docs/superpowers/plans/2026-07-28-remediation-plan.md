# Remediation Plan

## Stated goal

Fix the portfolio backtester so its calculations, user-facing assumptions, reproducibility flow, and summary/report outputs are internally consistent and safe to upload to git.

## Current state

- The backend mixes external cashflows into portfolio return series, which breaks TWRR/CAGR/Sharpe for DCA and withdrawal cases.
- The frontend exposes a cashflow timing input (`beginning`/`end`) but the backend currently ignores it.
- The benchmark curve starts one period later than the portfolio curve, causing alignment drift in frontend comparisons.
- The frontend monthly DCA net profit calculation subtracts initial capital twice.
- The reproducibility script and environment setup are not reliable from the documented command path in this workspace.
- Focused backend tests pass, but the full backend test collection fails in the current environment because dependencies are incomplete.
- This working directory is not an active git checkout, so git-based worktree and diff helper scripts from the SDD skill cannot run as written here.

## Target state

- Cashflow-enabled backtests compute TWRR and benchmark-relative statistics from a return series that is not distorted by contributions or withdrawals.
- Cashflow timing affects simulation results in the documented way, and the docs/UI/backend agree on the behavior.
- Benchmark and portfolio curves share the same starting anchor and align correctly in downstream frontend analytics.
- Frontend summaries and report tables use correct formulas and do not double-count initial capital.
- Reproducibility instructions and setup behavior are accurate for this project, and tests cover the repaired logic.
- A task ledger and review artifacts exist for this repair pass, even though the git-dependent SDD helper scripts are unavailable in this workspace.

## Ordered steps

### Task 1

Repair backend backtest math and contracts.

- Fix portfolio return construction so cashflows do not contaminate TWRR/CAGR/Sharpe and related benchmark metrics.
- Implement documented `cashflow.timing` behavior.
- Align benchmark and portfolio curves from the same initial anchor.
- Update or add backend tests that prove the corrected behavior.

### Task 2

Repair frontend calculations and result interpretation.

- Fix monthly DCA net profit and any summary/report logic that depends on corrected backend semantics.
- Update benchmark-derived frontend analytics so they use the repaired curve contract correctly.
- Preserve the existing API shape unless Task 1 makes a load-bearing contract change.

Task 2 depends on Task 1 output semantics.

### Task 3

Repair reproducibility, environment docs, and methodology references.

- Update reproducibility tooling/docs to reflect real invocation requirements in this project.
- Update methodology/formula docs where they diverge from repaired engine behavior.
- Add any targeted tests needed around reproducibility or reporting.

Task 3 depends on the final behavior from Tasks 1 and 2.

### Task 4

Run verification and a final review pass.

- Run the most relevant backend/frontend test commands available in this workspace.
- Perform a whole-change review against the repaired files and resolve any critical findings.

## Stop-conditions

Stop and ask before:

- Changing the public request/response schema in a way that would break saved runs or the frontend contract.
- Removing the `cashflow.timing` input instead of implementing it.
- Introducing a materially different performance methodology than the current docs intend.
- Making destructive cleanup changes to saved run artifacts or large data files.
