# Schnapp-Nasen (Snap-Fit) für den Kotbeutel-Deckel – Recherche

Stand 14.11.2026. Recherche, nichts gedruckt, nichts gesliced, keine CAD-Datei geändert.
Kennzeichnung: **[Q]** = Quelle sagt, **[S]** = meine Schlussfolgerung/Rechnung, **[A]** = Annahme (nicht belegt).
Ist-Stand gelesen: `gridfinity_kotbeutel.py` (WALL 1.6, LID_LIP 7, LIP_WALL 1.6, LID_FIT 0.25, SNAP_OUT 0.8, SNAP_H 3.6, SNAP_Z0 1.6, SNAP_W 20, SLIT 1.0, GROOVE_CEIL 1.5), Render `kb_schoen_deckel_dims.png`, Notizen „Schnapp-Nasen am Deckel – Befunde und Auslegung“ und „Kotbeutel-Behälter Gridfinity (FreeCAD)“. Was dort schon steht (45°-Fasen, Druck Platte unten, Reddit-Hinweise), wird hier nicht wiederholt.

## Kurzfazit

1. **[S]** Die Deckel-Lippe kann die 0,55 mm Eingriff elastisch gar nicht aufnehmen. Rechnung nach Bayer: Für 0,55 mm Biegung bräuchte das 1,6 mm dicke und nur 2,6 bis 4,6 mm lange Lippenstück 6 bis 19 % Dehnung, PLA verträgt nur etwa 1 %. Die eigentliche Feder ist die **Behälterwand**: 80 mm frei zwischen den Ecken, sehr weich, und sie biegt sich entlang der Schichten, also in der starken Richtung.
2. **[S]** Daraus folgt: Die Rastkraft hängt vor allem an Wandsteifigkeit × Eingriff × Flankenwinkel. Wand 1,8 statt 1,6 mm ergibt rechnerisch etwa 40 % mehr Rastkraft (Steifigkeit wächst mit t³). Die Lippe selbst sollte **steif** sein. Ihr Bruchrisiko kommt vom Hebeln beim Abnehmen und von scharfen Ecken an der Wurzel, nicht vom Einrasten.
3. **[S]** Wahrscheinlich ein Geometrie-Fehler, bitte im CAD-Schnitt prüfen: Die Nut-Decke steht mit `GROOVE_CEIL = 1.5` steiler als die 45°-Nasenflanke. Beim Abziehen gleitet deshalb die Nasenkante auf der Nut-Decke, wirksam ist ein Rückhaltewinkel von etwa 34° statt 45°. Das kostet rechnerisch rund 40 % Haltekraft. Der Kommentar im Skript („steiler … hält besser“) stimmt dann nicht.
4. **[S]** Empfehlung (Rang 1): beim Nasen-Prinzip bleiben, aber asymmetrisch machen. Einführflanke 30° (im Druck oben, ohne Überhang), Rückhalteflanke 45° (optional 55 bis 60° testen), Nut-Decke gleich steil wie die Rückhalteflanke, Eingriff 0,4 bis 0,7 mm, Wand 1,6 gegen 1,8 testen, Wurzel ausrunden, Fase an der Behälterkante.
5. **[S]** Die vorhandenen Teststücke (freistehende Wandplatte 40 bzw. ca. 89 mm, ohne Ecken) bilden die Federsteifigkeit des echten Behälters nicht ab. Für die Rastkraft taugen sie kaum, sie prüfen vor allem Druckbarkeit und Geometrie. Die Testreihe unten nutzt deshalb Wandsegmente mit Ecken.

## 1. Designs für abnehmbare Deckel

| Design | Prinzip | Vorteile | Nachteile | Passt zu uns? |
|---|---|---|---|---|
| Cantilever-Haken (Biegebalken mit Nase) | Balken biegt beim Fügen aus, Nase rastet in Hinterschnitt | Am besten berechenbar, häufigste Form [Q: Bayer, Hubs, Klahn] | Wurzel ist die kritische Stelle [Q: Bayer]. Balken in Z-Richtung ist schwach (Schichtgrenzen, Treppenstufen-Kerben) [Q: Klahn] | Nur mit langer Feder. Unsere Lippe ist zu kurz und zu dick [S] |
| „Diskontinuierlich ringförmig“ (geschlitzte Lippe mit Nasen) | Wie Ring-Schnapp, aber mit Schlitzen, dadurch vorwiegend Biegung | Bayer rechnet sie als Cantilever [Q: Bayer Fig. 4] | Wie Cantilever | **Das ist unser Ist-Design** [S] |
| Ringförmig / Annular (umlaufende Wulst in Nut) | Wulst weitet Gegenstück (Ring-Dehnung) | „Schon kleine Hinterschnitte ergeben feste Verbindungen“, semi-dicht. Kontinuierlich eher für einmalige Montage [Q: Bayer]. Wenn beide Teile nachgeben, halbiert sich die Dehnung [Q: Bayer] | Theorie gilt für runde Teile. Schwerer zu lösen [Q: Sculpteo] | Eher nein: An den Ecken der quadratischen Box ist die Wand steif, eine Wulst dort erzwingt hohe Dehnung [S] |
| Torsions-Schnapper | Wippe auf Torsionsstab, lösbar per Druck auf einen Hebel | Leicht lösbar, hält gegen Zug [Q: Bayer, Klahn]. Rechteckiger Stab besser als runder, lange Stäbe verformen weniger bleibend [Q: Printables-Testdruck, nur Suchauszug] | Aufwendig, viel Probieren nötig [Q: dto.] | Zu aufwendig für eine Kotbeutelbox [S] |
| U-Haken | Cantilever zurückgebogen, längere Feder auf kleinem Raum | Mehr wirksame Länge [Q: Bayer Fig. 15 „für Deckelverschluss“] | Überhänge im Druck | Möglich, aber druckkritisch [S] |
| Bajonett / Drehverschluss | Drehen in Rampe | Sehr fest, kein Biegen | Braucht runde Kontur | Nein (quadratisch, Gridfinity) [S] |
| Reibpassung (Friction Fit) | Leichtes Übermaß | Einfach. Bei Gridfinity-Deckeln verbreitet, Passung hängt stark von der Kalibrierung ab [Q: Suchauszug Printables/MakerWorld] | PLA kriecht unter Dauerdruck, wird locker [Q: Suchauszug Forum] | Fallback, nicht erste Wahl [S] |
| Kompressions-/Crush-Rippen | Rippen werden beim Fügen plastisch gequetscht | Toleranz-unempfindlich [Q: Hackaday 2020] | Nur einmal verwendbar. Für wiederholtes Fügen „Grip Fins“ (elastisch) nehmen [Q: DigiKey Maker.io] | Nein, Deckel wird oft gewechselt [S] |
| Flex-Zungen / Grip Fins | Dünne elastische Lamellen klemmen | Wiederholbar [Q: Maker.io] | Dünne Lamellen in Z = PLA-Bruch [S] | Nein in PLA [S] |
| Magnete | Magnete in Deckel und Behälterrand | Kein Verschleiß, kein Bruch, leichtes Abnehmen. Gridfinity-Deckel mit Magnet-Option gibt es [Q: MakerWorld-Suchauszug] | Kauf, Einlegepause oder Presssitz. Wand 1,6 mm zu dünn, Taschen in den Ecken nötig | **Guter Rang 3** [S] |
| Schiebedeckel mit Klick-Kerbe | Deckel gleitet in Nut, kleine Kerbe hält | „Finger schiebt auf, Schwerkraft nicht“ [Q: Printables 1041699, Suchauszug] | Andere Box-Geometrie, Frontöffnung im Weg | Nein ohne Umbau [S] |
| Push-to-open | Federmechanik | Komfort | Viele Teile | Nein [S] |

## 2. Kennzahlen und Faustregeln

| Größe | Wert | Quelle | Bemerkung |
|---|---|---|---|
| Biegebalken, konstanter Querschnitt | y = 0,67 · ε · l² / h | Bayer Table 1 (Design 1) | y = Eingriff, l = Länge Wurzel bis Kraftangriff, h = Dicke |
| Balken auf h/2 verjüngt | y = 1,09 · ε · l² / h, über 60 % mehr zulässige Biegung | Bayer S. 12/16 | Verjüngung auf h/2 „wann immer möglich“ |
| Fügekraft | W = P · (µ + tan α) / (1 − µ · tan α) | Bayer S. 14 | Lösekraft gleich, mit Rückhaltewinkel α′ |
| Reibwert | PC 0,45–0,55, ABS 0,5–0,65 (×1,2 bei gleichem Kunststoff) | Bayer Table 3 | **PLA nicht angegeben**. [A] µ ≈ 0,4–0,6 |
| Zulässige Dehnung allgemein | Teilkristallin bis fast an die Streckgrenze, amorph ca. 70 % der Streckdehnung (einmaliges Fügen). Bei häufigem Lösen ca. 60 % davon | Bayer S. 11/12 | Beispiel PC/ABS 2,5 % → 1,5 % |
| PLA Bruchdehnung (Bambu PLA Basic) | 12,2 % XY / 7,5 % Z, E 2680 / 2160 MPa, Zugfestigkeit 39 / 35 MPa | Bambu TDS V2.0 | Proben 100 % Infill, getempert 55 °C/8 h |
| PLA elastisch bis Bruchspannung | σ/E ≈ 1,5 % (XY), 1,6 % (Z) | [S] aus TDS | Keine Streckdehnung im TDS |
| Auslegung nach Engineers Grow | 10–15 % der Bruchdehnung (PLA 8 % → 0,8–1,2 %, PETG 24 % → 2,4–3,6 %) | Hackaday 2022 | |
| **Daraus für uns** | ε ≤ 1 % bei häufigem Abnehmen | [S] | |
| Länge/Dicke | PLA 8:1 bis 10:1, PETG 5:1 bis 8:1 | Sovol | Unsere Lippe: 7/1,6 ≈ 4,4, wirksam bis zur Nase nur 1,6–2,9 [S] |
| Eingriff Start | 0,5–1,2 mm, bei zu lose +0,3–0,5 | Sovol | Gilt für passende Balken |
| Nasenhöhe Beispiel | 1,2 mm, „≥ 2 mm fester“ | Formlabs (SLA-Beispiel) | Widerspricht kleinen FDM-Werten, siehe unten |
| Einführwinkel | 25–35° | Sovol; Bayer-Beispiel 30° | |
| Rückhaltewinkel | 45–70° lösbar, 60–70° verschleißfest, 90° dauerhaft | Sovol | Bayer: lösbar über α′, kein fester Wert |
| Wurzelradius | ≥ 0,5 · Dicke | Hubs | |
| Wurzelradius | R/h ≈ 0,6 optimal (Kompromiss), nie unter 0,015 in (0,38 mm) | Bayer S. 8 | |
| Wurzelradius | 0,5–1,0 · t, mind. 0,8–1,0 mm bei 0,4er Düse | Sovol | |
| Clip-Breite | ≥ 5 mm | Hubs | |
| Spiel FDM | 0,5 mm nominal | Hubs | |
| Spiel FDM | 0,2–0,4 mm je Seite | Wevolver, Sovol | |
| Spiel PLA/PETG | 0,2–0,3 mm (Tabelle 0,25) | Qidi | |
| Wandlinien | 3–5 Wände, 4 bei 1,5–2,5 mm Armen; Arme massiv; keine Überextrusion zum Kaschieren | Sovol | |
| Orientierung | Biegebalken nicht in Z, Treppenstufen wirken als Kerben. Balken quer zur Fügerichtung in XY legen | Klahn et al. 2016 | Kernaussage für AM |
| Orientierung | Zug in Z: Bruchdehnung ca. −50 %, Festigkeit −20 bis −30 % | Formlabs | |
| Orientierung | Arm flach drucken, Biegung entlang der Schichtlinien | Sovol, Wevolver, Hubs | |
| Laufgefühl | Gleiten entlang der Treppenstufen läuft glatt, quer dazu ratscht es | Klahn | Nase in Z gedruckt ratscht beim Fügen [S] |
| Material | ABS, PETG, PA bevorzugt, PLA „weniger geeignet“ | Hubs, Wevolver | |
| Material | PLA für leichte Deckel ok, kriechanfällig | Sovol | |
| Testzyklen | 20–30 Füge-/Lösezyklen | Sovol | |

### Rechnung für unseren Fall [S]

- **Lippe als Feder.** Kontakt am Nasenscheitel liegt 2,6 bis 4,6 mm über der Lippenwurzel (Nase 0,8: Scheitel 2,4 bis 4,4 mm ab Lippenende, Lippe 7 mm). Wird der volle Eingriff y = 0,55 mm von der Lippe allein genommen, ergibt ε = y·h/(0,67·l²): bei l = 4,6 sind es 6,2 %, bei l = 2,6 schon 19 %. Selbst mit der Nase ganz an der Spitze (l = 7) wären es 2,7 %. Bei ε = 1 % schafft die Lippe nur 0,09 bis 0,2 mm.
- **Wand als Feder**, grob als beidseitig eingespannter Balken über 80 mm Spannweite gerechnet. Die Dehnung ε ≈ 12·t·y/L² liegt bei 0,17 % (y 0,55, t 1,6). Die Steifigkeit ist um Größenordnungen kleiner als die der Lippe. Die Wand nimmt also fast die ganze Auslenkung auf, auch Eingriffe bis ca. 1 mm bleiben dehnungsseitig unkritisch. Grenzen des Modells: keine Plattenwirkung, kein Boden, Nut-Schwächung (Restwand 0,95) ignoriert.
- **Folge:** Gegen das Brechen beim Einrasten bringt eine dünnere Lippe nichts. Rastkraft holt man über Wanddicke (∝ t³: 1,8/1,6 → ×1,42), Eingriff (linear) und Flankenwinkel.
- **Flankenwinkel**, mit µ = 0,5 [A]: Faktor (µ+tan α)/(1−µ·tan α) ist bei 30° 1,51, bei 34° 1,77, bei 45° 3,0 und bei 60° 22,6, also nahe an Selbsthemmung. 30° Einführung und 45° Rückhalt bedeuten: Aufsetzen geht halb so schwer wie heute, das Abziehen bleibt gleich. Den Sprung zwischen 45° und 60° hängt stark am unbekannten µ [A]. Deshalb 55 bis 60° nur als Testvariante.
- **Nut-Decke:** Sie hat 1,5:1 Steigung (ca. 56° zur Horizontalen, 34° zur Achse), die Nasenflanke 45°. Beim Abziehen ist der Spalt an der Nasenspitze am kleinsten. Also läuft die Nasenkante auf der Nut-Decke, und die wirksame Rückhaltung liegt bei 34° (Faktor 1,77 statt 3,0). Abhilfe: Nut-Decke mindestens so flach wie die Rückhalteflanke der Nase (45°). Bitte im CAD-Schnitt verifizieren, bevor man darauf baut.
- **Druckbarkeit der Winkel:** Die Einführflanke liegt im Druck (Platte unten) oben, ohne Überhang, beliebig flach. Die Rückhalteflanke zeigt zur Platte, sie ist ein Überhang und deshalb auf ca. 45° begrenzt. 55 bis 60° sind bei nur ca. 0,8 mm Ausladung vermutlich druckbar [A], das zeigt erst der Test. Die Nut-Decke im Behälter (aufrecht gedruckt) ist ebenfalls ein Überhang, 45° gehen sicher.

## 3. Alternativen zu kleinen Nasen an starrer Lippe

- **Umlaufende Wulst mit leichtem Übermaß** [S]: nein. In den Ecken ist die Box steif, dort entstehen Spannungsspitzen. Lokale Nasen in der Seitenmitte nutzen genau die weiche Stelle der Wand. Das ist schon richtig gemacht.
- **Reibpassung mit Kompressionsrippen** [Q+S]: Crush-Ribs sind einmalig [Q: Maker.io], PLA kriecht unter Dauerpressung [Q: Suchauszug]. Für einen oft gewechselten Deckel ungeeignet.
- **Geschlitzte Segmente als Feder** [S]: Damit die Lippe selbst federt, müsste sie L/t ≥ 8 haben, bei 7 mm Länge also ≤ 0,9 mm dick (2 Linien). Das wäre ein Z-Balken, nach Klahn die schlechteste Lage. Die Schlitze bringen also kaum Federweg, schaffen aber Kerben an der Lippenwurzel. Entweder entfallen lassen oder 1 bis 2 mm über der Platte enden lassen bzw. mit Rundung enden. Das ist eine Testfrage.
- **Druck mit Platte oben, Stütze nur an der Nase** [S]: Dann braucht die ganze 83 × 83-Platte Stützen, und die Lippe bleibt ein Z-Balken. Kein Gewinn.
- **Federarm in XY nach Klahn** [Q-Prinzip + S]: Den bekommen wir schon gratis, denn die Behälterwand ist ein horizontaler Balken entlang der Schichten. Eine eigene XY-Feder am Deckel wäre im Druck mit Platte unten ein Überhang.
- **Magnete** [S]: zuverlässigste Alternative, wenn Rastung nicht befriedigt. Z. B. 4 Stück 6 × 2 mm in Eckpfosten [A: Maße, nicht recherchiert].
- **PETG nur für den Deckel** [Q: Hackaday, Hubs, Sovol]: 2 bis 3-fache zulässige Dehnung. Da bei uns die Wand federt, ist der Nutzen gering. Hilft aber gegen Bruch beim Hebeln [S].

## 4. Empfehlung für unseren Fall (Rangliste)

**Rang 1 – Nasen behalten, Wand als Feder auslegen, Flanken asymmetrisch** [S]
Begründung: Das Prinzip passt (Seitenmitte weich, Wand biegt entlang der Schichten, entspricht Klahn). Was fehlt, ist Rastkraft, und die liegt an Eingriff, Wandsteifigkeit und Rückhaltewinkel, nicht an der Nasengröße an sich.

Startwerte:
- Eingriff (SNAP_OUT − LID_FIT) **0,55 mm** (Test 0,4 / 0,55 / 0,7). SNAP_OUT ergibt sich daraus (0,8).
- Einführflanke (Lippenende-Seite, im Druck oben) **30°** zur Achse. Bei 0,8 mm Überstand ca. 1,4 mm hoch.
- Rückhalteflanke (Plattenseite) **45°** (Test 55 bis 60°).
- **Nut-Decke = Rückhalteflanke** (45°, nicht 56°). Nutgrund +0,1 mm wie bisher.
- Nasenhöhe gesamt ≤ 3,6 mm (1,4 + Scheitel ≥ 0,8 + 0,8), Breite 20 mm in Seitenmitte belassen ([Q] Hubs ≥ 5 mm erfüllt).
- Lippe **1,6 mm** steif (bei 0,42-mm-Linien ca. 4 Wände [A: Slicer-Default nicht geprüft]). Schlitze: Variante „ohne“ bzw. „endet 1,5 mm über Platte“ testen.
- Lippenwurzel außen (Zugseite beim Einwärtsbiegen) Fase/Rundung **0,8 mm** ([Q] Hubs ≥ 0,5 t, Sovol ≥ 0,8 mm), dazu passende **Fase 0,8–1,0 × 45° an der Innenoberkante der Behälterwand**. Die dient zugleich als Einführhilfe.
- Spiel Lippe–Wand **0,25 mm** belassen ([Q] liegt in 0,2 bis 0,4 je Seite, Hubs' 0,5 wäre locker).
- Wand **1,6 vs. 1,8 mm** testen. 1,8 bringt ca. +42 % Rastkraft [S], Restwand hinter der Nut 1,15 statt 0,95.

**Rang 2 – wie Rang 1, Deckel in PETG** [S, gestützt auf Q zu Bruchdehnung]
Nur falls die Lippe beim Abhebeln bricht. Geometrie gleich, Spiel ggf. +0,05 mm [A].

**Rang 3 – Magnetdeckel ohne Hinterschnitt** [S]
Falls Rastung „mal zu fest, mal zu lose“ bleibt. Lippe nur zur Führung, Magnete in Eckpfosten. Kostet Teile und Einlegepause.

### Testreihe (eine Platte, ca. 256 × 256 mm) [S]

Problem der bisherigen Teststücke: Die freistehende Wandplatte (14 × 40 × 18 bzw. Serie ca. 89 lang) hat keine Ecken. Ihre Steifigkeit hängt davon ab, wie man sie hält. Darum hier **Wandsegmente mit Ecken**:
- **Wandstück:** eine volle Behälterseite (83,4 mm) mit beiden Ecken und je 10 mm Seitenwand (C-Form), 25 mm hoch (obere 25 mm des Behälters inkl. Nut und Fase). Grobe Schätzung ca. 6 bis 8 g [A].
- **Deckelstreifen:** 83,4 mm lang, Platte 2 × 12 mm, Lippe 7 mm mit einer Nase 20 mm in der Mitte, Platte unten gedruckt.
- Platzbedarf je Paar ca. 84 × 30 mm. 6 Paare in einer Spalte (ca. 200 mm) oder 2 Spalten passen auf die P1S-Platte.
- Einschränkung [A]: Dem Segment fehlt der Boden 78 mm tiefer. Es ist daher vermutlich etwas weicher als die echte Box, die echte Rastung also eher etwas fester. Bestätigung am Ende mit einem ganzen Deckel auf ganzem Behälter.

| Nr. | Wand | Eingriff | Einführ/Rückhalt | Nut-Decke | Schlitze | Zweck |
|---|---|---|---|---|---|---|
| R | 1,6 | 0,55 | 45/45 | 56° (heute) | ja, bis Platte | Referenz = Ist-Stand |
| A | 1,6 | 0,55 | 30/45 | 45° | ja, bis Platte | Effekt Flanken + Nut-Decke |
| B | 1,6 | 0,40 | 30/45 | 45° | ohne | Eingriff klein |
| C | 1,6 | 0,70 | 30/45 | 45° | ohne | Eingriff groß |
| D | 1,8 | 0,55 | 30/45 | 45° | ohne | Wanddicke |
| E | 1,6 | 0,55 | 30/60 | 60° | ohne | steiler Rückhalt + Druckbarkeit Überhang |

(Wurzelrundung 0,8 und Behälterfase in A bis E. Ein Vergleich „ohne Schlitze“ gegen „mit Schlitzen“ steckt in A gegen B bis E nur indirekt. Bei Bedarf eine Variante F = A ohne Schlitze ergänzen.)

Bewertung je Paar:
1. Druckbild der Nase und der Nut-Decke (Überhang sauber?).
2. Klick fühl- und hörbar (1–5).
3. Aufsetzen und Abziehen per Hand (1–5), falls vorhanden mit Gepäckwaage.
4. 20 bis 30 Zyklen ([Q] Sovol), danach Weißbruch oder Risse an Lippenwurzel und Nut?
5. Sitzt der Streifen nach den Zyklen noch?

Danach eine Variante als ganzen Deckel auf ganzem Behälter bestätigen. Die bereits geslicte Nasen-Serie (0,8/1,0/1,2) taugt wegen der freistehenden Wandplatte nur für Druckbild und Geometrie [S].

## 5. Widersprüche zwischen Quellen

- **PLA für Snap-Fits:** Hubs und Wevolver nennen PLA „weniger geeignet / nicht empfohlen“, Sovol hält es für leichte Deckel für geeignet. Ultimaker-Forum (Suchauszug): PLA hält „ein paar Mal“.
- **Zulässige Dehnung PLA:** Engineers Grow/Hackaday rechnet mit PLA-Bruchdehnung 8 % → 0,8–1,2 %. Das Bambu-TDS nennt 12,2 % (XY) / 7,5 % (Z), nach derselben Regel 1,2–1,8 % bzw. 0,75–1,1 %. σ/E aus dem TDS ergibt ≈ 1,5 %. Bayer-Regel (70 % der Streckdehnung) ist nicht anwendbar, weil keine PLA-Streckdehnung belegt ist.
- **Spiel:** Hubs 0,5 mm nominal (FDM), Qidi 0,2–0,3 (PLA/PETG), Wevolver und Sovol 0,2–0,4 je Seite. Hubs sagt außerdem, es gebe keine festen Regeln.
- **Nasenhöhe/Eingriff:** Formlabs 1,2 mm, ≥ 2 mm fester (SLA-Gehäuse, längere Arme). Sovol 0,5–1,2 mm. Bayer: aus Dehnung zu rechnen, kein Pauschalwert.
- **Wurzelradius:** Hubs ≥ 0,5 t, Sovol 0,5–1,0 t / mind. 0,8 mm, Bayer R/h 0,6 optimal, aber Kompromiss, Minimum 0,38 mm.
- **Einführwinkel:** Sovol 25–35°, Bayer-Beispiel 30°. Ein Hobby-Beispiel (Suchauszug, Qualität fraglich) nutzt 45°.
- **Orientierung:** einig, dass Biegebalken nicht in Z liegen sollen. Klahn ergänzt, dass auch die Bahnrichtung in XY zählt, und dass die Lage bei Konflikt durch Umkonstruieren gelöst wird (Feder quer zur Fügerichtung).

## Quellenliste

- Bayer/Covestro: Snap-Fit Joints for Plastics – A Design Guide (Kopie MIT): https://fab.cba.mit.edu/classes/S62.12/people/vernelle.noel/Plastic_Snap_fit_design.pdf. Gleiche Fassung bei SparkFun: https://cdn.sparkfun.com/assets/home_page_posts/1/4/1/0/Plastic_Snap_fit_design.pdf. Seiten 5, 8, 9, 11, 12, 14–17, 20–22 gelesen. Formel Design 1 (0,67) aus Tabelle (Bild), im Text nur 1,09 bestätigt.
- Klahn, Singer, Meboldt: Design Guidelines for Additive Manufactured Snap-Fit Joints, Procedia CIRP 50 (2016) 264–269, DOI 10.1016/j.procir.2016.04.130, Volltext: https://publikationen.bibliothek.kit.edu/1000142464/142615492
- Bambu Lab PLA Basic Technical Data Sheet V2.0: https://cdn.shopify.com/s/files/1/0380/5149/files/Bambu_PLA_Basic_Technical_Data_Sheet.pdf
- Hubs: How to design snap-fit joints for 3D printing: https://hubs.com/knowledge-base/how-design-snap-fit-joints-3d-printing
- Formlabs: Designing snap-fit enclosures: https://formlabs.com/blog/designing-3d-printed-snap-fit-enclosures
- Sovol: 3D Printed Snap-Fit Joints: https://www.sovol3d.com/blogs/news/3d-printed-snap-fit-joints-how-to-design-clips-that-work (Hersteller-Blog, Werte ohne Herleitung)
- Qidi: Clearance Guide: https://qidi3d.com/de/blogs/print-lab/3d-printed-snap-fit-joints-clearance-guide (Hersteller-Blog)
- Wevolver: How to 3D print snap-fit joints: https://www.wevolver.com/article/how-to-3d-print-snap-fit-joints
- Hackaday 2022 (Engineers Grow): https://hackaday.com/2022/11/11/oh-snap-3d-printing-snapping-parts-without-breakage, Video: https://www.youtube.com/watch?v=-jgbd8RUhhY (Video selbst nicht gesehen)
- Hackaday 2020, Crush Ribs: https://hackaday.com/2020/10/15/adding-crush-ribs-to-3d-printed-parts-for-a-better-press-fit
- Nur Suchauszüge (Seite 403 oder nicht geöffnet): Sculpteo https://www.sculpteo.com/blog/2018/04/25/how-to-connect-two-parts-with-3d-printed-joints-and-snap-fits/, Printables Torsion-Test https://www.printables.com/model/151102, Gridfinity-Deckel https://printables.com/model/613155 und https://www.printables.com/model/1041699, Maker.io https://www.digikey.at/en/maker/blogs/2026/10-smart-3d-printing-tips-tolerances-holes-and-slicer-tricks, Ultimaker-Forum https://community.ultimaker.com/topic/31968-help-with-my-snap-lock-design/
- Reddit (r/3Dprinting, r/functionalprint) war für das Recherche-Werkzeug gesperrt. Die Reddit-Hinweise aus früheren Notizen bleiben die Reddit-Basis.

## Offene Fragen

1. Stimmt die Kontaktanalyse Nut-Decke gegen Nasenflanke (wirksam 34°)? Bitte im CAD-Schnitt im montierten Zustand prüfen.
2. Reibwert PLA auf PLA nicht belegt. Er bestimmt, wie stark ein steilerer Rückhaltewinkel wirkt.
3. Steifigkeit der echten Behälterwand ist nur grob geschätzt (Balkenmodell). Wie weit weicht das 25-mm-Segment ab?
4. Slicer-Linienbreite für Wände auf der P1S (0,42 / 0,45 / 0,6?) nicht geprüft. Hinweis „Wandlinien 0,6“: 1,8 = 3 × 0,6 passt, die Restwand hinter der Nut (1,15) dann nicht ganzzahlig.
5. Wie wird der Deckel abgenommen (an der Frontöffnung hebeln)? Das bestimmt die Bruchlast der Lippe mehr als das Einrasten.
6. Ist PETG verfügbar bzw. gewünscht?
