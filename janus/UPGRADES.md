# JANUS — PRO TIER upgrades vs original plan

Le plan v1 (`JANUS_TRADING_SYSTEM_PLAN.md`) cible une qualité institutionnelle.
Ce document liste les écarts que nous prenons pour atteindre une qualité top-tier
(trading firms quant pod / hedge fund crypto). Chaque écart est motivé par une
raison technique précise, pas par du gold-plating.

> **Règle de décision** : tout upgrade doit (a) protéger contre une perte
> financière réelle (pas juste théorique), ou (b) préserver la capacité du
> système à évoluer sans rewrite. Si ni l'un ni l'autre, on s'abstient.

---

## Phase 0 — Data infrastructure

| # | Upgrade | Raison | Statut |
|---|---------|--------|--------|
| 0.1 | **Trades tick-level** ingérés en plus de l'OHLCV | OHLCV cache la microstructure : pour un slippage model honnête (Phase 1+), il faut le tape brut. Sans ça, on backteste avec des hypothèses de slippage qui ne tiennent pas en live. | **appliqué** |
| 0.2 | **Orderbook snapshots L2** (top 50 niveaux) à 1s sur BTCUSDT/ETHUSDT | Idem : sizing optimal et impact-aware execution (Almgren-Chriss) impossibles sans depth historique. | **appliqué** |
| 0.3 | **Continuous aggregates** TimescaleDB pour 5m/15m/1h/4h/1d | Évite de recomputer les bars à chaque backtest. Gain ~10× sur backtests vectorisés. | **appliqué** |
| 0.4 | **Compression + retention policies** TimescaleDB | Trades + orderbook = ~50 GB/an/symbole. Sans compression natif, le stockage devient le bottleneck. | **appliqué** |
| 0.5 | **Idempotency par content-hash** sur chaque batch ingéré | Permet de relancer un backfill sans peur de doublons. Le plan v1 ne traite pas l'idempotence. | **appliqué** |
| 0.6 | **Cross-source price validation** (Binance vs Bybit) avec alerte sur divergence > N bps | Détecte un feed corrompu avant qu'il pollue les features. Vrai cas : Binance mid 2022, USDC index drift. | **appliqué** |
| 0.7 | **NTP drift check** au démarrage de tout process | Point-in-time correctness suppose que l'horloge locale est précise. Drift de 30s = features fausses. | **appliqué** |
| 0.8 | **Outbox pattern** pour publication d'événements live | Atomique avec le commit DB → pas de perte d'événement entre ingestion et stratégies. | **appliqué** |
| 0.9 | **Property-based testing** (hypothesis) sur invariants | Catch les edge cases que les tests par exemple ratent (ex : OHLC monotonicity sur séries dégénérées). | **appliqué** |
| 0.10 | **Pre-commit hooks** : ruff, mypy --strict, detect-secrets, end-of-file-fixer | Empêche un secret de leaker dans git, et garantit que `main` est toujours lintable. | **appliqué** |
| 0.11 | **Schema versioning** : colonne `feature_version` sur toutes les tables dérivées | Rétro-compat sans rewrite quand on change la définition d'une feature. | **appliqué** |
| 0.12 | **Dead-letter queue** pour batches d'ingestion qui échouent après retry | Inspection manuelle plutôt que perte silencieuse. | **appliqué** |

**Hors scope Phase 0 (volontairement)** : tracing OpenTelemetry, event sourcing complet,
DVC pour data lineage. Ces upgrades coûtent plus qu'ils ne rapportent à ce stade.

---

## Phase 1 — Refractory Period (upgrades à appliquer en Phase 1)

| # | Upgrade | Raison |
|---|---------|--------|
| 1.1 | **Adaptive thresholds** : remplacer les seuils fixes ($200M liquidations, 4% drop) par des quantiles online roulants (90 jours) | Les seuils absolus pourrissent quand le marché grossit/rétrécit. Quantile-based = stationnaire. |
| 1.2 | **Order Flow Imbalance (OFI)** + **Cumulative Volume Delta (CVD)** comme confirmation d'épuisement | Plus rapide que "prix stable 30 min" et beaucoup moins de faux signaux. |
| 1.3 | **Multi-asset cascade contagion** : signal renforcé si BTC drop déclenche aussi ETH/top alts dans la même fenêtre | Vraie cascade systémique vs idiosyncratique. |
| 1.4 | **Bayesian Online Changepoint Detection** sur la série de liquidations | Détecte la fin de cascade avant que le critère "rate of change < 10% peak" ne se déclenche. Edge ~20-40 min. |
| 1.5 | **Conformal prediction** intervals sur le take-profit cible | Plutôt qu'un TP fixe à 50% retracement, un intervalle calibré sur l'OOS empirique. |
| 1.6 | **Slippage modeling avec orderbook snapshots historiques** (cf. 0.2) | TP/SL réalistes vs hypothèses optimistes. |

---

## Phase 2 — Narrative Rotation

| # | Upgrade | Raison |
|---|---------|--------|
| 2.1 | **Embedding-based narrative clustering** (Sentence-BERT sur project descriptions) plutôt que tagging manuel YAML | Le tagging manuel ne scale pas et introduit du look-ahead (on tague avec ce qu'on sait *aujourd'hui*). |
| 2.2 | **GitHub dev activity** comme feature primaire (pas juste proxy social) | Dev activity précède le pump narratif de 2-4 semaines. Source structurée, peu arbitragée. |
| 2.3 | **Beta-to-narrative decomposition** : retire la beta-BTC du return alt avant de calculer le momentum | Sinon on capture du beta, pas du flow rotation. |
| 2.4 | **Snapshot historique des CoinGecko categories** (snapshots quotidiens stockés en bronze) | Élimine le look-ahead bias sur les tags qui n'existaient pas à l'époque. |
| 2.5 | **Capacity-aware sizing** : limite de position en % du daily volume du token (pas du portfolio) | Mid-cap alts = 10% du daily volume = on EST le marché. |

---

## Phase 3 — Stablecoin Stress Flow

| # | Upgrade | Raison |
|---|---------|--------|
| 3.1 | **Pool depth at peg level** (Curve 3pool, Uniswap v3 ranges) | Un depeg à 0.15% sur un pool de $5M ≠ même chose que sur $500M. Le edge dépend de la profondeur. |
| 3.2 | **Issuer treasury composition** via on-chain (Tether/Circle) | Confirmation que le depeg est solvability-driven vs liquidity-driven (très différent en termes de durée du signal). |
| 3.3 | **CEX-DEX peg arb spread** comme feature additionnelle | Capture les routes par lesquelles le capital fuit (CEX → DEX → BTC). |
| 3.4 | **Funding rate term structure** (1h/8h/24h) plutôt que funding spot | Permet de détecter si le marché perps anticipe le flow (diminue l'edge). |

---

## Phase 4 — Regime Detector

| # | Upgrade | Raison |
|---|---------|--------|
| 4.1 | **HMM + Bayesian Online Changepoint Detection** ensemble | HMM seul a tendance à lagger sur les transitions abruptes. BOCPD compense. |
| 4.2 | **Macro features** : DXY, VIX, US 10Y, BTC dominance | Crypto est sensitive au risk-on/risk-off. L'omettre = régime mal classifié pendant les pivots Fed. |
| 4.3 | **Confidence-weighted gating** plutôt que seuil binaire 60% | Réduit le flip-flop quand la prob oscille autour du seuil. |
| 4.4 | **Counterfactual evaluation** : "qu'aurait fait la strat sans gating ?" en parallèle | Permet de mesurer l'edge réel du regime layer en continu, pas juste au backtest initial. |

---

## Risk Management (transversal)

| # | Upgrade | Raison |
|---|---------|--------|
| R.1 | **Volatility-targeted overlay** par-dessus Kelly (target σ portfolio = 15% annualisé) | Kelly suppose une vol stationnaire. Crypto = non-stationnaire. Overlay rescale en temps réel. |
| R.2 | **Stress-VaR** régime-conditionné (pas juste historique 1 an) | VaR historique sous-estime massivement le risque hors-régime calibration. |
| R.3 | **Reverse stress test** mensuel : "quel scénario nous met à -30% ?" | Catche les concentrations de risque invisibles (ex : 3 strats long-vol qui shortent toutes la même tail). |
| R.4 | **Risk parity entre stratégies** au lieu d'allocation égale post-Kelly | Évite qu'une strat à haute vol monopolise le risk budget. |

---

## Execution

| # | Upgrade | Raison |
|---|---------|--------|
| E.1 | **Almgren-Chriss optimal execution** (vs TWAP simple) pour positions > 2× ADV/1000 | TWAP naïf paie de l'impact. Almgren-Chriss minimise impact + variance d'exécution. |
| E.2 | **Adaptive participation rate** basé sur queue position et fill probability | Maker rebate optimal si la queue position est bonne, sinon basculer taker plus tôt. |
| E.3 | **Iceberg detection** sur les books pour éviter de chasser de la fausse liquidité | Évite des entries trop agressives quand un large iceberg masque la depth réelle. |

---

## Engineering / DevEx

| # | Upgrade | Raison |
|---|---------|--------|
| X.1 | **Determinism harness** : fixe seed numpy/random, hash check sur les artefacts de backtest | Garantit qu'un même commit + même data → même résultat. Sans ça, debugging cauchemar. |
| X.2 | **Contract tests** sur les exchanges APIs (snapshot des shapes attendues) | Catch les breaking changes Binance/Bybit avant qu'ils crashent en prod. |
| X.3 | **Mutation testing** (mutmut) sur risk + execution paths | Mesure la vraie qualité des tests : un test qui passe avec un mutant = test inutile. |
| X.4 | **Runbook + chaos drills** trimestriels : kill DB, kill websocket, drop network | La résilience non-testée n'existe pas. |
| X.5 | **Secret management via sops/age** plutôt que .env brut | .env en plain text = leak garanti tôt ou tard. |

---

## Ce qu'on NE fait PAS (anti-overengineering)

- ❌ Microservices : un mono-process Python pour la v1. Latence inter-service > gain.
- ❌ Kafka / RabbitMQ : Redis + outbox suffit jusqu'à 10k events/s.
- ❌ Kubernetes : un VPS + docker-compose + systemd. Complexité K8s pour solo dev = piège.
- ❌ Feature store dédié (Feast/Tecton) : nos volumes ne le justifient pas en Phase 0-3.
- ❌ MLOps stack complète (MLflow + DVC + Kubeflow) : on track les modèles avec git tags + S3 jusqu'à preuve d'insuffisance.
