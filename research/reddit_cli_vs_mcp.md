# Reddit-Recherche: CLI + Skill statt MCP für Agenten (Claude Code), Blender-MCP, CAD-Setups

Erstellt 13.11.2026 mit `reddit-cli` (Suche über r/ClaudeAI, r/ClaudeCode, r/mcp, r/LocalLLaMA, r/blender, r/FreeCAD, r/cadquery, r/openscad, r/3Dprinting u. a.). **Beleg** = was im Thread belegt/gemessen oder als Fakt berichtet wird; **Meinung** = Einschätzung der Poster. Votes/Kommentare Stand der Abfrage. Eigenwerbung (eigenes Produkt des Posters) ist markiert. Nichts davon haben wir selbst nachgemessen. Keine Notiz (schreibt ddde3441).

**Kurzfazit**
- Die Masse der Threads sieht CLI + Skill als Standard für lokale Coding-Agenten (billig im Kontext, Bash ist die Heimat der Modelle), MCP wird für Fremddienste mit Auth, Remote/Cloud-Clients ohne Shell und strukturierte, zustandsbehaftete Zugriffe verteidigt.
- Der Haupteinwand gegen MCP ist die Schema-Last (Tool-Definitionen stehen von Anfang an im Kontext); die Gegenposition: das ist ein Server-Designfehler (Tool-Search, Gateway, wenige gute Tools), kein Protokollproblem.
- Für Blender/CAD sagen viele: Python-Skripte plus Headless-Aufruf plus Render/Screenshot genügt; der MCP lohnt, wenn man live in einer offenen Szene arbeitet.


## 1. CLI/Skill statt MCP — Token, Kontext, Debugging, Auth

### [r/mcp: I generated CLIs from MCP servers and cut token usage by 94%](https://www.reddit.com/r/mcp/comments/1rembfo/i_generated_clis_from_mcp_servers_and_cut_token/) · 2026-02-25 · 173 Votes · 40 Komm. · **Eigenwerbung**
- **Beleg:** Poster beziffert: MCP lädt alle Tool-Schemas vorab (~185 Tokens × 84 Tools = 15 540 Tokens), eine Liste der Befehle als CLI spart laut Poster 94 %. Konverter „CLIHub“ von ihm selbst.
- **Meinung:** Kommentar (8 Votes): die Schema-Ladung am Kontextanfang verschwendet die wertvollsten Plätze; Kommentar (6): Erkundungsschleifen und Fehlversuche der CLI müssten in die Tokenbilanz.

### [r/ClaudeAI: MCP Is Costing You 37% More Tokens Than Necessary](https://www.reddit.com/r/ClaudeAI/comments/1rzz784/mcp_is_costing_you_37_more_tokens_than_necessary/) · 2026-03-21 · 89 Votes · 56 Komm.
- **Beleg:** Poster: MCP-Tools kosten 37 % mehr Tokens. Kommentar (30 Votes): nach Notion-, Sentry-, Shortcut-MCPs begannen Sessions mit 40 % belegtem Kontext; Wechsel auf CLI + Skills war „much better“.
- **Meinung:** Kritik (11 Votes): der Benchmark teste die CLI-Ausführung nicht und ignoriere Tool-Search/progressive Discovery.

### [r/AI_Agents: The Truth About MCP vs CLI](https://www.reddit.com/r/AI_Agents/comments/1rjtp3q/the_truth_about_mcp_vs_cli/) · 2026-03-03 · 86 Votes · 49 Komm.
- **Beleg:** Poster: GitHub-MCP mit 93 Tools ≈ 55 000 Tokens vor der ersten Frage.
- **Meinung:** Kommentar: Skills für Struktur, MCP für Enterprise-Zugriff, CLI für Entwickler, alle drei je nach Aufgabe.

### [r/LocalLLaMA: Please explain: why bothering with MCPs if I can call almost anything via CLI?](https://www.reddit.com/r/LocalLLaMA/comments/1s41ltp/please_explain_why_bothering_with_mcps_if_i_can/) · 2026-03-26 · 103 Votes · 98 Komm.
- **Beleg:** Kommentar (27 Votes): MCP-Tool-Aufrufe werden per Schema/Grammatik erzwungen, damit keine JSON-Syntaxfehler; ein MCP-Server kann Tools an jeden Client veröffentlichen.
- **Meinung:** Kommentar (69 Votes): ein guter MCP-Server bildet keine API-Endpunkte 1:1 ab, sondern liefert aufbereitete, verdichtete Antworten; nicht alles lässt sich gut als CLI ausdrücken (komplexe Schemas, Listen).

### [r/mcp: CLI > MCP?](https://www.reddit.com/r/mcp/comments/1o8w5wq/cli_mcp/) · 2025-10-17 · 174 Votes · 70 Komm.
- **Beleg:** Zitat Simon Willison: sein Interesse an MCP sei gesunken, fast alles gehe per CLI.
- **Meinung:** Kommentar (10 Votes): nur wahr, wenn der Client lokal läuft und Shell hat; MCP kann Notifications/Resources/Subscriptions, die kaum ein Client nutzt.

### [r/mcp: I measured MCP vs CLI token costs - the "MCP is dead" take is wrong (with data)](https://www.reddit.com/r/mcp/comments/1rv6jyj/i_measured_mcp_vs_cli_token_costs_the_mcp_is_dead/) · 2026-03-16 · 46 Votes · 51 Komm. · **Eigenwerbung**
- **Beleg:** Poster misst seinen MCP-Server mit 21 Tools: ~1 300 Tokens Vorabkosten, CLI 0 (Details in der Tabelle im Thread).
- **Meinung:** Titel: „MCP is dead“ sei falsch. Poster betreibt selbst einen MCP-Server.

### [r/mcp: MCPs, CLIs, and skills: when to use what?](https://www.reddit.com/r/mcp/comments/1rtsl9z/mcps_clis_and_skills_when_to_use_what/) · 2026-03-14 · 26 Votes · 9 Komm.
- **Beleg:** Kommentar: das `update-issue`-Tool des Jira-MCP verbrauchte ~20 000 Tokens, weil sich die Antwort nicht filtern lässt; CLI sei ausgereifter.
- **Meinung:** Blogpost-Poster: CLI für deterministische Operationen, MCP für Daten hinter Auth, Skills als Kleber.

### [r/ClaudeCode: To everyone touting the benefits of CLI tooling over MCP, how are you managing unrelenting](https://www.reddit.com/r/ClaudeCode/comments/1rwz2km/to_everyone_touting_the_benefits_of_cli_tooling/) · 2026-03-18 · 15 Votes · 24 Komm.
- **Beleg:** Poster fragt nach Dauer-Berechtigungsfragen bei Shell-Aufrufen. Kommentare: einzelne Bash-Befehle lassen sich freigeben, PreToolUse-Hooks, vorab freigegebene Wrapper-Skripte; MCP-Logins müssen teils mehrfach täglich wiederholt werden (7 Votes).
- **Meinung:** CLI-Reibung = Berechtigungsprompts (lösbar), MCP-Reibung = Auth/Verbindungsabbrüche.

### [r/mcp: Anyone else’s agent get dumber the more MCP servers you connect?](https://www.reddit.com/r/mcp/comments/1xsn62w/anyone_elses_agent_get_dumber_the_more_mcp/) · 2026-11-10 · 13 Votes · 26 Komm.
- **Beleg:** Kommentare: bei 15+ MCP-Servern wählt das Modell Tools falsch; ein „smart routing“ mit nur zwei Tools (search_tools, execute) senke den Footprint laut Kommentator von >300k auf ~1k Tokens.
- **Meinung:** Kommentar: doppelte Suchtools mit ähnlichen Beschreibungen wählt das Modell etwa zur Hälfte falsch; ein Router verschiebe das Problem nur.

### [r/ClaudeCode: Scripts vs MCP](https://www.reddit.com/r/ClaudeCode/comments/1xdyqwx/scripts_vs_mcp/) · 2026-10-24 · 3 Votes · 26 Komm.
- **Beleg:** Kommentar: GitHub-MCP ≈ 48 Tools à ~1k Tokens = 48k Kontext. Cloud-Agenten (z. B. Slack Claude Tag) haben nur MCP-Konnektoren, keine Shell.
- **Meinung:** Kommentar: Standard ist CLI/Skript, MCP „nur wenn der traditionelle Weg scheitert“.

## 2. Wann MCP doch besser

### [r/mcp: MCP vs. CLI for AI agents: When to Use Each](https://www.reddit.com/r/mcp/comments/1roc96a/mcp_vs_cli_for_ai_agents_when_to_use_each/) · 2026-03-08 · 78 Votes · 15 Komm.
- **Beleg:** Kommentar: CLI ist kein Transport, über ein Netz braucht man eine Transportschicht; MCP unterstützt lazy loading/hierarchische Tool-Listen, nur macht der einfache Server es selten.
- **Meinung:** Argument: das Problem sind die heutigen Server-Implementierungen, nicht das Protokoll.

### [r/ClaudeAI: Benefits to using MCPs for programs like Godot or Blender](https://www.reddit.com/r/ClaudeAI/comments/1vyiyy8/benefits_to_using_mcps_for_programs_like_godot_or/) · 2026-08-26 · 17 Votes · 22 Komm.
- **Beleg:** Kommentar (7 Votes): bei Godot/Blender liegt der Wert im Rückkopplungskreis: Szene/Objektgraph abfragen, eine Aktion, echtes Ergebnis sehen, korrigieren.
- **Meinung:** Gegenkommentare (6, 4): Godot läuft headless mit Screenshots, Blender per Kommandozeile und Python; MCP sei nur eine weitere Abstraktionsschicht.

### [r/ClaudeCode: What gives better results between using blender with mcp and just headless with python.](https://www.reddit.com/r/ClaudeCode/comments/1xopsir/what_gives_better_results_between_using_blender/) · 2026-11-05 · 0 Votes · 8 Komm.
- **Beleg:** Kommentare: Wer aktiv in einer offenen Szene arbeitet, will den MCP; für Batch/Server reicht Headless. Python-Skripte lassen sich ins Repo einchecken und vom Modell besser lesen als eine Blender-Szene.
- **Meinung:** Ein Kommentar: kein Unterschied mehr zwischen MCP und Skript.

## 3. Blender-MCP (ahujasid „blender-mcp“ und offizieller Connector)

### [r/ClaudeAI: Opus 5.5 medium with blender mcp is insane with the right prompting](https://www.reddit.com/r/ClaudeAI/comments/1xmcwbt/opus_55_medium_with_blender_mcp_is_insane_with/) · 2026-11-03 · 792 Votes · 81 Komm.
- **Beleg:** Poster: kein manuelles Modellieren, Claude schreibt Python-Skripte, die alles bauen; Vorgehen in kleinen Aufgaben (Materialien → Bausatzteile → ein Haus nach dem anderen), jedes Objekt eine eigene Datei. Ein Kommentar: 40 h und 30 % eines 200-$-Plans für einen Helm.
- **Meinung:** Poster: „insane with the right prompting“; Kommentar: Ergebnisse super, dauert ewig.

### [r/codex: If you're using blender, please use the MCP server. It saves TOKENS](https://www.reddit.com/r/codex/comments/1wceqea/if_youre_using_blender_please_use_the_mcp_server/) · 2026-09-10 · 6 Votes · 9 Komm.
- **Beleg:** Poster (6 Votes): mit dem offiziellen MCP weniger Tokens; ohne ihn lief der Agent als Python-Skript → prüfen → wiederholen, schlechte Effizienz.
- **Meinung:** Einzelerfahrung.

### [r/ChatGPT: You can now use your ChatGPT subscriptions directly in Blender. No need for the Blender-MC](https://www.reddit.com/r/ChatGPT/comments/1xcvhwc/you_can_now_use_your_chatgpt_subscriptions/) · 2026-10-22 · 132 Votes · 32 Komm. · **Eigenwerbung**
- **Beleg:** Thread zu einem Blender-Plugin, das ChatGPT-Abos direkt in Blender nutzt („no need for the Blender-MCP“); Kommentar: Blender headless mit MCP laufe gut.
- **Meinung:** Eigenwerbung des Plugin-Autors und eines Kommentators (Render/Animation-MCP gegen Geld).

### [r/ClaudeAI: Might have cracked blender mcp for claude](https://www.reddit.com/r/ClaudeAI/comments/1vuccmd/might_have_cracked_blender_mcp_for_claude/) · 2026-08-21 · 12 Votes · 19 Komm.
- **Beleg:** Poster: Modelle werden von Claude zu leicht als „in Ordnung“ durchgewunken; Abhilfe: Audit-Skripte pro Netz-Aspekt, Farben je Nachbarfläche, Lücken/Fugen prüfen. Kommentar: Claude nutzte unaufgefordert die Blender-CLI.
- **Meinung:** Kommentar: „LLMs bridge nicht die 3D-Lücke“; Architekt (Kommentar): nutzt Blender- und Rhino-MCP täglich ohne Probleme.

### [r/OpenAI: Blender MCP is impressive but not that useable (yet)](https://www.reddit.com/r/OpenAI/comments/1we95z2/blender_mcp_is_impressive_but_not_that_useable_yet/) · 2026-09-12 · 25 Votes · 22 Komm.
- **Beleg:** Poster: Blender-MCP beeindruckend, aber (noch) kaum nutzbar; einfache Szenen gehen, komplexe (spielbares Auto) nicht.
- **Meinung:** Meinung; Thread ohne Messwerte.

### [r/aigamedev: Fable 5.2 + Blender MCP just surprised the hell out of me](https://www.reddit.com/r/aigamedev/comments/1xtgir8/fable_52_blender_mcp_just_surprised_the_hell_out/) · 2026-11-11 · 130 Votes · 62 Komm.
- **Beleg:** Poster: Animation eines Rigs mit Fable 5.2 + Blender-MCP aus einem Einzeiler; Kommentar: ~110 000 Tokens.
- **Meinung:** Kommentar rät, wie ein Regisseur zu beschreiben statt „Rotation fixen“.

> **Lücke:** Ich habe keinen Thread gefunden, der die Tool-Auslegung der beiden Blender-MCPs selbst (execute_code, get_viewport_screenshot, Asset-Bibliotheken, Doku-Suche) im Detail lobt oder kritisiert. Die Threads handeln von Ergebnissen und Aufwand, nicht von Tool-Design. Aussagen zu Tool-Details bräuchten einen Blick in die GitHub-READMEs bzw. den Blender-Doku-Beitrag, nicht Reddit.

## 4. CAD/FreeCAD/CadQuery/OpenSCAD — CLI/Skript statt MCP

### [r/ClaudeCode: A mechanical engineer's take on 3D CAD with Claude](https://www.reddit.com/r/ClaudeCode/comments/1xpmsfy/a_mechanical_engineers_take_on_3d_cad_with_claude/) · 2026-11-06 · 62 Votes · 22 Komm.
- **Beleg:** Kommentar (4 Votes): statt MCP für eine CAD-Software lieber Claude per CLI Zugriff auf eine Python-Bibliothek zum Definieren von 3D-Teilen geben; Teile mit „many more pieces“ so gebaut. Weitere Kommentare: build123d + Render, OpenSCAD, STEP statt STL für Bearbeitbarkeit.
- **Meinung:** Meinung des Kommentators; kein Messwert.

### [r/openscad: Designing in OpenSCAD with AI agents (without writing code)](https://www.reddit.com/r/openscad/comments/1vfiuwt/designing_in_openscad_with_ai_agents_without/) · 2026-08-04 · 0 Votes · 10 Komm.
- **Beleg:** Kommentar: Wechsel von OpenSCAD zu build123d, weil der OpenCascade-Kern mehr Rückmeldung liefere; Kommentar des Autors: eigene Werkzeuge für Feedback (Kollisionen, Lücken, Schnitte), keine MCPs, „funktionieren gut“.
- **Meinung:** Der Autor beschreibt einen Workflow aus Claude Code + OpenSCAD per CLI.

### [r/FreeCAD: Claude Code + FreeCAD MCP integration - surprisingly good results](https://www.reddit.com/r/FreeCAD/comments/1mp7itt/claude_code_freecad_mcp_integration_surprisingly/) · 2025-08-13 · 268 Votes · 35 Komm. · **Eigenwerbung**
- **Beleg:** Poster: FreeCAD-MCP mit Claude Code „surprisingly good“. Kommentare: große Teile der FreeCAD-API seien undokumentiert, Copilot/Gemini scheiterten daran; Frage nach Maßgenauigkeit.
- **Meinung:** Kritik (4–6 Votes): Ohne zusätzlichen Kontext sei der AI-Code „mostly useless“.

### [r/cadquery: AI agents are surprisingly good at CadQuery, if you can show them what you mean. So I buil](https://www.reddit.com/r/cadquery/comments/1x6dacm/ai_agents_are_surprisingly_good_at_cadquery_if/) · 2026-10-15 · 16 Votes · 5 Komm. · **Eigenwerbung**
- **Beleg:** Poster baut SOMA: Claude Code schreibt CadQuery-Code, die App baut jedes Mal neu, rendert 3D und erlaubt Zeigen/Messen/Skizzieren für den Agenten.
- **Meinung:** Kommentar: Vergleich mit FluidCAD (GUI + MCP, KI nur sekundär).

### [r/ClaudeCode: Made an app where an AI agent does the CAD for me, first time open sourcing something](https://www.reddit.com/r/ClaudeCode/comments/1x6bdwa/made_an_app_where_an_ai_agent_does_the_cad_for_me/) · 2026-10-15 · 20 Votes · 15 Komm. · **Eigenwerbung**
- **Beleg:** Wie oben (r/ClaudeCode-Variante): Claude Code schreibt CadQuery-Code, die App rendert; Kommentar: für viele Programme gebe es schon MCP-Konnektoren (FreeCAD, Fusion).
- **Meinung:** Eigenwerbung.

### [r/ClaudeAI: Can both 2D and 3D CAD models be generated entirely through code written by AI, without th](https://www.reddit.com/r/ClaudeAI/comments/1wwufyf/can_both_2d_and_3d_cad_models_be_generated/) · 2026-10-03 · 16 Votes · 13 Komm. · **Eigenwerbung**
- **Beleg:** Kommentar eines Maschinenbauers: Claude erzeugt jetzt halbwegs editierbare STEP-Dateien, ein Prompt erledigt ~70 % der Arbeit, die schweren Teile macht er von Hand; einmal interferierten zwei Teile.
- **Meinung:** Eigenwerbung eines Kommentators (somacad.app).

### [r/openscad: Can we have an OpenSCAD LLM ban?](https://www.reddit.com/r/openscad/comments/1shai33/can_we_have_an_openscad_llm_ban/) · 2026-04-10 · 85 Votes · 89 Komm.
- **Beleg:** Thread im r/openscad: Kommentar (31 Votes): OpenSCAD passt zu KI wegen Textformat, Versionskontrolle, Kommandozeile, Parametrisierung.
- **Meinung:** Poster wollte ein Verbot LLM-bezogener Beiträge; viele Kommentare gelöscht.

## Was sich daraus für uns ableiten lässt (nur Anregung, nicht belegt)
- Unser Aufbau (FreeCAD per `freecad -c`, build123d, OpenSCAD, `p1s`/`orca` als CLI mit Skill) entspricht dem, was die meisten Reddit-Stimmen als günstig für lokale Agenten beschreiben.
- Kommentare nennen als Vorteil von Skript/CLI: Skripte im Repo, headless, wenig Kontext; als Vorteil des MCP: Live-Szene, Auth, Cloud-Clients ohne Shell.
- Für den Rückkopplungskreis nennen mehrere: Render/Screenshot plus Prüfskripte (Kollision, Lücken, Schnitte, Audit pro Netz-Aspekt).
