Verifikationsskripte zum Couch-Abnahmetest (13.11.2026). Aufruf immer ueber `cad run`:
  cd /mnt/raid1/3d_print/couch_console && cad run couch_console.py && cad run <bench-skript>
fixtures/couch_console.py   eingefrorene Kopie des Couch-Modells (Referenz fuer Messungen)

Phase 4 (13.11.2026):
run_bench.py                 Regression/Zeit/Soll-Ist-Tabelle (python3 bench/run_bench.py [--quick] [--json]); Exit 0 = alles PASS
ref/couch_hotspots_baseline_20261113.json   Trefferliste von `cad hotspots` am Couch-Modell VOR der Aenderung (Vergleich der Bruecken-Spannweiten)
verify_bridge_span.py        Genauigkeit der Spannweite an Formen mit bekannter Loesung (cad run)
bak/                         Sicherungen von Skill und Plan (*.bak-20261113-p4)
Hinweis: die Maschine war waehrend der Messungen stark belastet (Load 20-60); Zeiten sind Wanduhr, CPU-Zeit liegt bei den Messskripten gleich auf.

14.11.2026: Stil schoen / GLB (cad_schoen.py). run_bench.py nutzt jetzt das EINGEFRORENE Couch-Modell (fixtures/couch_console.py, OUT_DIR umgebogen nach cad_out/test/couch_fixture), weil das Live-Modell nach der Referenz wuchs (41 statt 29 Teile) und die Couch-Pruefungen sonst 5x FAIL melden (Sicherung run_bench.py.bak-20261114-v).
