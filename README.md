# tags2puml

Ein Python-Skript zur automatischen Erzeugung von PlantUML-Diagrammen aus einer ctags-basierten `tags.txt`-Datei.

## Funktionsweise
Das Skript liest eine `tags.txt`-Datei (z. B. erzeugt mit Universal Ctags) und generiert daraus zwei verschiedene PlantUML-Diagramme:

- **Funktionsdiagramm** (`functions.puml`): Zeigt die Abhängigkeiten zwischen Funktionen.
- **Klassendiagramm** (`classes.puml`): Zeigt Packages, Structs/Klassen, Methoden, globale Variablen und deren Beziehungen.

## Voraussetzungen
- Python 3
- Eine `tags.txt`-Datei im selben Verzeichnis (z. B. mit Universal Ctags erzeugt)

## Nutzung

```sh
python3 tags2puml.py func   # Erzeugt functions.puml (Funktionsdiagramm)
python3 tags2puml.py class  # Erzeugt classes.puml (Klassendiagramm)
```

Ohne Argument wird das Funktionsdiagramm erzeugt.

## Hinweise
- Die `tags.txt`-Datei muss im selben Verzeichnis wie das Skript liegen.
- Die erzeugten `.puml`-Dateien können mit PlantUML weiterverarbeitet werden.
- Unterstützt werden u. a. Go, C, C++ und andere Sprachen, die von ctags erkannt werden.

## Lizenz
MIT License
