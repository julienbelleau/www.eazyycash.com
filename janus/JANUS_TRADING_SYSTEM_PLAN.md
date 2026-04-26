# JANUS — Plan d'architecture système de trading crypto multi-stratégie

**Version:** 1.0
**Cible:** Claude Code Opus 4.7
**Stack principale:** Python 3.11+, Docker, PostgreSQL/TimescaleDB, Redis

---

## 0. MISSION ET PRINCIPES DIRECTEURS

### Mission
Construire un système de trading crypto solo, multi-stratégie modulaire, exploitant 3 inefficacités de marché structurellement décorrélées, avec un meta-layer de détection de régime, gestion de risque institutionnelle, et infrastructure de backtest/paper-trading/production grade.

### Principes non-négociables
1. Pas un module en production sans backtest walk-forward validé + 60 jours de paper trading.
2. Chaque stratégie est isolée, testable seule, débranchable sans casser les autres.
3. Tous les coûts modélisés: fees maker/taker, slippage estimé, funding rates, latence d'exécution.
4. Aucun lookahead bias: point-in-time correctness sur 100% des features.
5. Kill switch global + kill switches par stratégie, déclenchés par drawdown, anomalie, ou perte de connectivité.
6. Reproductibilité totale: seed fixe, version des modèles, snapshots de data.
7. Logs structurés sur tout — chaque trade doit être expliquable post-mortem.

### Anti-patterns explicitement exclus
- Pas de RL deep learning sans supervision (overfitting + non-stationnarité).
- Pas de "LLM qui lit Twitter en temps réel" (latence + hallucinations + déjà arbitragé).
- Pas d'ensemble de >100 features par modèle (PCA cache l'absence d'edge, pas le crée).
- Pas de stratégie sans thèse économique structurelle articulable en 2 phrases.

---

## Phase Gating

| Phase            | Durée                | Gate de passage                           | Kill criterion          |
|------------------|----------------------|-------------------------------------------|-------------------------|
| 0 — Data infra   | 2 sem                | Backtest 3 ans <5min, live stable 7j      | N/A (foundation)        |
| 1 — Refractory   | 3 sem dev + 60j paper| Sharpe OOS >1.5, paper Sharpe >0.75       | Sharpe OOS <1.0         |
| 2 — Narrative    | 4 sem dev + 60j paper| Sharpe OOS >1.2, paper Sharpe >0.6        | Sharpe OOS <0.8         |
| 3 — Stablecoin   | 3 sem dev + 60j paper| Edge net >0.3%/trade                      | Edge net <0.2%          |
| 4 — Regime       | 2 sem                | Improvement Sharpe >0.2 vs always-on      | Improvement <0.1        |
| Live small       | 30j                  | P&L conforme paper ±30%                   | Drawdown >20% portfolio |
| Live scale       | 90j                  | Stable Sharpe sur 90j                     | Drawdown >25%           |

Ce fichier est la spec canonique. Toute déviation doit être motivée dans `docs/decisions/`.
