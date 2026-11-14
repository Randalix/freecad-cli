---
name: cad
description: FreeCAD-Modelle (Python/Part-API) ohne GUI bauen, messen, ansehen und prüfen mit dem Befehl `cad` (run/info/look/hotspots/check/worker/projekt/version). Nutzen, wenn ein CAD-Modell (z. B. ein 3D-Druckteil oder Möbel) per Skript erstellt, geändert oder geprüft werden soll, wenn Maße/Volumen gebraucht werden oder wenn man das Ergebnis ansehen und kritische Stellen heranzoomen will.
---

# cad — CAD per Skript bauen, messen, ansehen

Ein persistenter headless FreeCAD-Worker hält das Dokument im Speicher; `cad` ist der Client. Bilder rendert Blender headless. Installation und Konfiguration: README des Repos.

## Schleife (so arbeiten)
1. **Parametrisches Skript** schreiben (FreeCAD Part-API, Parameter oben als Konstanten, keine festen Magic Numbers). Beispiele: `gridfinity_*.py` im Repo.
2. **Ausführen und messen:** `cad run skript.py --report` (gültig, Solids, BBox, Volumen, Fläche, Flächenzahl). Im Skript Ergebnisse benennen: `cad.report(Deckel=shape, Behaelter=shape2)`. `cad` ist im Skript ohne Import verfügbar. Ohne `cad.report` zeigt `cad look` alle Part-Objekte des Dokuments, mit `cad.report` nur die gemeldeten.
3. **Ansehen, nicht raten:** `cad look` (Sheet iso/front/right/top mit mm-Lineal), dann gezielt zoomen; das Bild jedes Mal wirklich ansehen, bevor etwas als gut gemeldet wird.
4. **Kritische Stellen prüfen:** im Skript markieren (`cad.focus("Nase", (x,y,z), 8, view="front")`), mit `cad look --focus all` rendern; Maße mit `cad info`; `cad hotspots` und `cad check` für Überhang, Brücke, dünne Wand, Spalt, offenes Netz.
5. **Teststück vor Vollmodell** für Passungen; Parameter erst nach einem Probedruck festschreiben.
6. **Abnahme-Bild:** vor jeder Fertigmeldung das gerenderte Bild vorlegen (siehe unten).
7. **Wandstärken aus den Linienbreiten ableiten (3D-Druck):** Kleine Abweichungen zwischen Wandstärke und den Spuren, die der Slicer legt, erzeugen Gap-Fill und können die Druckzeit erheblich erhöhen. Mit dem Wandgenerator `classic` sind nur gerade Spurzahlen gap-frei. Vor dem Slicen `cad check <datei> --line-w <Linienbreiten>` benutzen, nicht „n × Linienbreite" schätzen.
8. **Druckbarkeit** vor dem Übergeben an den Slicer: Platte unten, keine Überhänge über 45°, Mehrteil-STL mit 5–10 mm Abstand.

## Befehle
```
cad run skript.py [--report] [--look [ansicht]] [--glb out.glb] [-k] [-v] [--json] [--timeout S]
cad run -c "code"                      # Einzeiler im Worker
cad info datei.FCStd|step|stl          # Messwerte
cad look [datei] [--view iso|front|back|left|right|top|bottom[,..]] [--dir az,el] [--at x,y,z --size mm]
         [--box x0,y0,z0,x1,y1,z1] [--focus all|NAME] [--mode shaded|wire|xray|overhang|section]
         [--section x=40] [--hotspot N] [--diff ALT NEU] [--px N] [--persp] [-o bild.png] [--json]
cad look [datei] --style schoen [--dims] [--room] [--explode auto|dx,dy,dz] [--lens 40] [--hide NAME,..] [--glb out.glb]
cad hotspots [datei] [--min-wall 0.8] [--profile print|moebel] [--json]
cad check [datei] [--bed 256x256x256] [--line-w std,0.6] [--profile print|moebel] [--json]
cad materials list|add KEY --rgb r,g,b [--label --rough --metal --alias --match REGEX]|rm KEY
cad worker status|stop|restart         # restart = Abbruch hängender Skripte
```
Exit-Codes: 0 ok, 1 Befund, 2 Skript-/Aufruffehler, 3 Infrastruktur (Worker/Blender). Ohne Datei arbeiten `look`/`hotspots`/`check` auf dem letzten Lauf im Worker. Negative Werte mit Gleichheitszeichen: `--dir=-30,24`.

## Projekt und Versionen
Jedes Projekt hat einen Ordner `<CAD_PROJEKT_ROOT>/<projekt>/` mit `PROJEKT.md`, `CHANGELOG.md`, `aktuell` (Symlink) und je Version `vNNN_<datum>_<label>/{modell,slice,vorschau,messung}`.
```
cad projekt <name>|list|show|aus        # aktives Projekt setzen
cad version "<Label>" [--basiert-auf vNNN]   # neue Version; Ausgaben gehen dorthin
cad freigabe "<Notiz>"                  # freigabe.md; sperrt die Version (nur auf ausdrücklichen Wunsch des Nutzers)
```
`cad look` ohne `-o` schreibt nach `vorschau/`, `--glb` nach `modell/`, `--report` und `--json` nach `messung/`; im Skript `cad.outdir("modell"|"slice"|"vorschau"|"messung")`. Jede Änderung ist eine neue Version; in eine freigegebene Version schreibt `cad` nicht. Liegen die Projekte auf einer Netzfreigabe ohne Symlinks, legt `cad` sie per ssh an (`CAD_SYMLINK_HOST`); nie über Symlinks schreiben, nur in den echten Versionsordner.

## Abnahme: immer das gerenderte Bild vorlegen
Bevor ein Modell oder eine Änderung als fertig gemeldet wird, muss der Nutzer das aktuell gerenderte Bild bekommen: Textbericht, Messwerte oder Prüfergebnisse allein reichen nicht. Der Nutzer nimmt ab, nicht der Agent.
- Menschliche Ansicht: `cad look --style schoen --dims`; bei mehreren Teilen je Teil ein Bild (`--hide`), bei Baugruppen zusätzlich `--explode auto`. Bei Passungen zusätzlich der Schnitt der kritischen Stelle, bei Änderungen Vorher/Nachher (`--diff`).
- Das Bild nach der letzten Änderung neu rendern und selbst ansehen; nie ein altes Bild wiederverwenden. Im Bericht sagen, welcher Stand gerendert wurde.

## Stil `schoen` und GLB
Perspektive mit Materialien, Schatten, Bemaßung (`--dims`: Länge/Breite/Höhe der Bounding Box der sichtbaren Teile), Schnitt (`--section`), Explosion (`--explode`, mit Nummern und Legende), Raum-Kulisse (`--room`) und GLB-Export (Meter, Y oben, Teile als benannte Meshes, PBR). Material je Bauteil: im Skript `cad.material("Name", "eiche|multiplex|hartholz|platzhalter|<eigene>")` oder Namensregel; eigene Materialien (`materials.json`) mit `cad materials add`.

## Bekannte Fallen
- FreeCAD headless: `freecad -c` braucht `</dev/null`; `App` ist im Skript ohne Import verfügbar; nie `PySide`/`pivy` importieren; ohne `DISPLAY` stürzt VTK ab.
- Blender muss mit `env -u LD_LIBRARY_PATH -u DISPLAY` laufen (macht `cad` selbst); sein Python braucht `numpy` und `Pillow`.
- Skripte, die alles am Ursprung ablegen, mit `cad.report(Name=shape)` und `--focus` auswählen; Mehrteil-Ausgaben beim Export auseinanderrücken.
- Die Rechenzeit der Hotspots hängt an großen waagerechten Flächen, nicht an der Dreieckszahl.

## Grenzen
Die Prüfungen sind Geometrie-Schätzungen (Überhang ab 45°, Brücken über ca. 10 mm) und ersetzen keinen Probedruck. Nichts drucken oder slicen, solange der Nutzer es nicht ausdrücklich verlangt.
