Last reviewed: 2025-09-27

# Next Steps – bl-shap

## Geplante Umsetzung
1) SHAP für aktuelles Churn‑Modell integrieren (RandomForest/Alt‑Modelle):
   - Global: Aggregierte SHAP‑Importances (Mean/Abs‑Mean), Ranking Top‑N.
   - Lokal: Pro Kunde Top‑K Treiber mit Vorzeichen und Beitrag.
2) Artefakt‑Export (JSON/CSV/Bilder) nach `dynamic_system_outputs/outbox/shap/experiment_<id>/`.
3) DAL/Paths nutzen (keine direkten Dateipfade), Architektur‑Konformität sicherstellen.
4) Anbindung CF:
   - CF‑Suche auf SHAP‑Top‑K je Kunde begrenzen (Whitelist).
   - Richtungs‑/Bounds‑Policies aus SHAP‑Vorzeichen ableiten.
5) Reporting/UI: Management‑taugliche Zusammenfassungen (Top‑Treiber, Segment‑Sichten, Stabilität).

## Architektur-Vorgaben (einzuhalten)
- Separation of Concerns: SHAP‑Berechnung getrennt von BL‑Modellen; keine Datenzugriffs‑Logik in SHAP‑Komponenten.
- DAL‑only für Daten/Modelle; Pfade zentral aus `paths_config.py`.
- JSON‑DB‑Richtlinien beachten (Artefakte auditierbar und versioniert).
- Keine ML‑Fallbacks: Fehlen Bibliotheken → sauberer Fehler (Fail‑Fast).

## Nächste konkrete Schritte
- Modul‑Skeleton vervollständigen (`bl-shap/bl/Shap/*`, `config/shared/config/*`).
- SHAP‑Berechnungen kapseln (Funktionen: global, lokal; Schnittstellen zu `bl-churn`).
- Experiment‑ID‑Handling wie in Churn/CF übernehmen (FK `id_experiments`).


## Offene Punkte (Analyse & Maßnahmen)

1) Warum erscheint nur `I_CONSULTING` in `shap_local_topk` besonders häufig?
   - Prüfen, ob in `customer_churn_details` die engineered Feature‑Abdeckung ungleichmäßig ist (7 Modell‑Features fehlen bereits → Verdrängungseffekt möglich).
   - Korrelation/Ko‑Linearität: `I_CONSULTING` könnte mehrere Rolling/Trend‑Ableitungen dominieren; Ranking über mean(|SHAP|) bevorzugt konzentrierte Treiber.
   - Zielgerichtete Stichprobe: 50 Kunden mit hoher Churn‑Wahrscheinlichkeit nehmen und die Top‑5‑Verteilung über Features aggregieren (Anteil je Feature, Gini der Verteilung).
   - Action: Heatmap „Feature × Rang (1..K)“ auf Basis `shap_local_topk` bauen, um Konzentration sichtbar zu machen.

2) Zurück zu Basis‑Features für Erklärungen (Vorschlag)
   - Feature‑Gruppierung: Engineered Features per Mapping auf Basis‑Quellen (`I_*`) konsolidieren, SHAP‑Beiträge je Basis‑Gruppe summieren (global/lokal) und zusätzlich exportieren.
   - Alternativ: SHAP direkt auf Basis‑Features rechnen, indem `customer_churn_details` um das reine Basis‑Set ergänzt wird (oder per Pipeline‑Recompute eine reine Basis‑Matrix erzeugt wird) – Modell bleibt unverändert; Erklärungsebene wird um „Group‑SHAP“ ergänzt.
   - Export‑Erweiterung: zusätzliche Artefakte `shap_global_basis.json` und `shap_local_topk_basis.jsonl` mit gruppierten Beiträgen; CF kann beide Sichten nutzen (fein vs. grob).


