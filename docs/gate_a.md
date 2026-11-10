# Gate A (pre-registered before touching the held-out season)

Tuning seasons: 2223, 2324 (xi grid 0.001 / 0.0019 / 0.003; result insensitive, chose xi = 0.0019).
Tuning result (4,652 matches): model log loss 1.0034 vs market 0.9811 vs naive 1.0712.

Held-out season: **2425** (all 6 leagues, full Pinnacle closing coverage). Run once, config frozen:
xi = 0.0019, 14-day blocks, 1500-day training window, per-league models.

Pass if ALL of:
1. 1X2 log loss within 0.030 of de-vigged Pinnacle close (gap on tuning seasons was 0.022).
2. 1X2 RPS within 0.010 of market.
3. No 1X2 calibration bin outside its 95% interval (a single bin miss is reviewed, not auto-fail).
4. Over/Under 2.5 log loss within 0.025 of market.

## Result on held-out 2425 (2,292 matches; run once)
| | log loss | Brier | RPS |
|---|---|---|---|
| model | 0.9957 | 0.5949 | 0.2026 |
| Pinnacle close (Shin) | 0.9768 | 0.5821 | 0.1969 |
| naive | 1.0761 | 0.6514 | 0.2301 |

Gaps: log loss 0.0189 (<0.030), RPS 0.0057 (<0.010), O/U 2.5 log loss 0.0082 (<0.025). Calibration: 0/10 bins outside 95% interval.
**Gate A: PASS.** The model is ~0.02 log loss behind the closing line, as expected; Gate B decides whether any edge exists.

## Data finding
Pinnacle closing odds disappear from the football-data CSVs from mid-January 2026 (2526: 51% coverage; Feb-May 0%).
AH/totals Pinnacle close exist only from 1920 on. Market-average close (AvgC*) is still complete for 2526.

## Shrink-weight fit (Phase 2.1)
Fitted on tuning seasons 2223+2324, blend = w*model + (1-w)*Pinnacle close (Shin):
log loss at w=0 (pure market) 0.9811, w=0.25 worse, w=0.5 worse, w=1 (pure model) 1.0034. **Best w = 0.0.**
Held-out 2425: w=0 0.9768, 0.25 0.9781, 0.5 0.9816, 1.0 0.9957. Same story against Pinnacle OPENING odds
(best w = 0.0; open logloss 0.9793 vs close 0.9768).
Meaning: a goals-only Dixon-Coles model carries no information the market has not already priced, even early in the week.
With w=0 the value engine reduces to "best soft-book price vs sharp fair price" (line shopping); CLV tracking tests that.
