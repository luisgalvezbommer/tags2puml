#!/usr/bin/env python3
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

#------------------------------------------------------------------------------
# Name der tags-Datei (muss im selben Ordner wie das Skript liegen)
TAGS_FILE = "tags.txt"
# PUML-Dateien, die wir im jeweiligen Modus erzeugen
PUML_FUNC = "functions.puml"
PUML_CLASS = "classes.puml"
#------------------------------------------------------------------------------

def get_package_name(file: str) -> str:
    """
    Liest aus der Datei das Schlüsselwort 'package X' aus und gibt 'X' zurück.
    Wenn die Datei nicht gefunden wird oder keine Package-Zeile enthält, gibt 'root' zurück.
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("package "):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
                    break
    except Exception:
        pass
    return "root"


def find_enclosing_struct(member_line: int) -> str | None:
    """
    Sucht in der Datei ab Zeile member_line rückwärts nach der nächsten
    Zeile, die einer Struct-Definition entspricht: 'type <Name> struct'.
    Gibt den Struct-Namen oder None zurück, wenn nichts gefunden wurde.
    """

    try:
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            found_member_line = False
            lines = f.readlines()
            for i in range(len(lines) -1, -1, -1):
                line = lines[i].strip()
                if not line:
                    continue
                line_nr = int(re.search(r'^\S+\s+\S+\s+(\d+)', line).group(1))
                if line_nr == member_line:
                    found_member_line = True
                    continue
                pattern = rf'^([A-Za-z0-9_]+)\s+(?:class|struct)'
                m = re.search(pattern, line)
                if found_member_line and m:
                    return m.group(1)
    except FileNotFoundError:
        pass
    return None


def parse_tags():
    """
    Liest die tags-Datei ein und gibt vier Strukturen zurück:
      - packages: { package_name: { "structs": set(), "funcs": [], "vars": [] } }
      - functions: Liste aller Funktionen als Dict {name, file, line, sig}
      - structs:   Liste aller Structs   als Dict {name, file, line}
      - variables: Liste aller globalen Variablen  als Dict {name, file, line}
      - members_by_struct: { struct_name: [member1, member2, ...] }
    """
    if not os.path.exists(TAGS_FILE):
        print(f"Fehler: {TAGS_FILE} nicht gefunden.")
        sys.exit(1)

    packages: dict[str, dict] = defaultdict(lambda: {"structs": set(), "funcs": [], "vars": []})
    functions = []
    structs = []
    variables = []
    members_by_struct: dict[str, list[str]] = defaultdict(list)

    # Cache für Paketnamen je Datei
    pkg_cache: dict[str, str] = {}

    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()
            if not line or line.startswith("!"):  # Kommentar-Zeile überspringen
                continue

            # Splitte in maximal 5 Felder: [Name, Kind, LineNr, Pfad, Rest]
            parts = re.split(r"\s+", line, maxsplit=4)
            if len(parts) < 5:
                continue
            tagname, kind, line_nr_str, path, rest = parts
            try:
                line_nr = int(line_nr_str)
            except ValueError:
                continue

            # Paketnamen ermitteln (einmal pro Datei)
            if path not in pkg_cache:
                pkg_cache[path] = get_package_name(path)
            pkg = pkg_cache[path]

            # Einträge verarbeiten
            if kind == "package":
                _ = packages[pkg]  # legt den Eintrag an
                continue

            if kind in ("struct", "class"):
                packages[pkg]["structs"].add(tagname)
                structs.append({"name": tagname, "file": path, "line": line_nr})
                continue

            if kind in ("func", "function"):
                functions.append({"name": tagname, "file": path, "line": line_nr, "sig": rest})
                packages[pkg]["funcs"].append(tagname)
                continue

            if kind in ("var", "const"):
                # globale Variable oder Konstante
                variables.append({"name": tagname, "file": path, "line": line_nr})
                packages[pkg]["vars"].append(tagname)
                continue

            # Neu: Alle "member" (Felder in Structs) einsammeln
            # ctags kennzeichnet Felder oft mit "member" oder "anonMember"
            if kind.lower().endswith("member"):
                # Finde übergeordnete Struct-Definition in der Datei
                struct_parent = find_enclosing_struct(line_nr)
                if struct_parent:
                    members_by_struct[struct_parent].append(tagname)
                continue

    return packages, functions, structs, variables, members_by_struct


#------------------------------------------------------------------------------
# Hilfsfunktion: Extrahiere aus Methodensignatur den Receiver-Typ
def extract_receiver_type(sig: str) -> str | None:
    """
    Sucht in der Signatur nach "(<name> <Typ>)" direkt nach 'func '.
    Gibt den Struct-Namen (ohne Zeiger-Prefix "*") oder None zurück.
    """
    m = re.match(r"func\s*\(\s*\w+\s+(\*?)([A-Za-z0-9_]+)\s*\)", sig)
    if not m:
        return None
    _, struct_name = m.groups()
    return struct_name


#------------------------------------------------------------------------------
# Modus 1: Funktionsdiagramm
def build_function_puml(functions: list[dict]) -> str:
    names = {f["name"] for f in functions}
    deps: dict[str, set[str]] = defaultdict(set)

    for entry in functions:
        fname = entry["name"]
        filepath = entry["file"]
        start = entry["line"]

        if not os.path.exists(filepath):
            print(f"⚠️ Datei nicht gefunden: {filepath}")
            continue

        with open(filepath, "r", encoding="utf-8") as fd:
            lines = fd.readlines()
            code = "".join(lines[start - 1 :])
            for other in names:
                if other == fname:
                    continue
                if re.search(rf"\b{re.escape(other)}\s*\(", code):
                    deps[fname].add(other)

    lines: list[str] = ["@startuml"]
    for n in sorted(names):
        lines.append(f"entity {n} {{}}\n")
    for src, targets in deps.items():
        for dst in sorted(targets):
            lines.append(f"{src} --> {dst}")
    lines.append("@enduml")
    return "\n".join(lines)


#------------------------------------------------------------------------------
# Modus 2: Klassendiagramm (Package → Struct → Methods, Vars & Members)
def build_class_puml(packages: dict[str, dict],
                     functions: list[dict],
                     structs: list[dict],
                     variables: list[dict],
                     members_by_struct: dict[str, list[str]]) -> str:
    struct_names = {s["name"] for s in structs}

    # Methoden nach Struct gruppieren
    methods_by_struct: dict[str, list[str]] = defaultdict(list)
    # Funktionen ohne Receiver → Package-Level
    pkg_funcs: dict[str, list[str]] = defaultdict(list)

    for f in functions:
        recv = extract_receiver_type(f["sig"])
        if recv and recv in struct_names:
            methods_by_struct[recv].append(f["name"])
        else:
            pkg = get_package_name(f["file"])
            pkg_funcs[pkg].append(f["name"])

    # Package-Level-Variablen (global)
    pkg_vars: dict[str, list[str]] = defaultdict(list)
    for v in variables:
        pkg = get_package_name(v["file"])
        pkg_vars[pkg].append(v["name"])

    # Assoziationen zwischen Structs (falls ein Struct in einer Datei ein anderes erwähnt)
    associations: set[tuple[str, str]] = set()
    for s in structs:
        name = s["name"]
        path = s["file"]
        line_nr = s["line"]
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fd:
            lines = fd.readlines()
            body = "".join(lines[line_nr - 1 :])
            for other in struct_names:
                if other == name:
                    continue
                if re.search(rf"\b{re.escape(other)}\b", body):
                    associations.add((name, other))

    # PlantUML-Text zusammenbauen
    lines: list[str] = ["@startuml", "skinparam classAttributeIconSize 0\n"]

    for pkg, info in packages.items():
        lines.append(f"package {pkg} {{")
        # a) Struct-Klassen
        for s in sorted(info["structs"]):
            lines.append(f"  class {s} {{")
            # a1) Methoden
            for m in sorted(methods_by_struct.get(s, [])):
                lines.append(f"    + {m}()")
            # a2) Member-Felder (Variablen in Struct)
            for mem in sorted(members_by_struct.get(s, [])):
                lines.append(f"    - {mem}")
            lines.append("  }\n")

        # b) Package-Level-Funktionen und -Variablen in Helper-Klasse
        if pkg in pkg_funcs or pkg in pkg_vars:
            lines.append(f"  class {pkg}_globals {{")
            for fn in sorted(pkg_funcs.get(pkg, [])):
                lines.append(f"    + {fn}()")
            for vr in sorted(pkg_vars.get(pkg, [])):
                lines.append(f"    - {vr}")
            lines.append("  }\n")

        lines.append("}\n")

    # c) Assoziationen zeichnen
    for src, dst in sorted(associations):
        lines.append(f"{src} --> {dst}")

    lines.append("@enduml")
    return "\n".join(lines)


#------------------------------------------------------------------------------
# MAIN
if __name__ == "__main__":
    if len(sys.argv) < 2:
        mode = "func"
    else:
        mode = sys.argv[1].lower()

    packages, functions, structs, variables, members_by_struct = parse_tags()

    if mode == "func":
        puml = build_function_puml(functions)
        with open(PUML_FUNC, "w", encoding="utf-8") as f:
            f.write(puml)
        print(f"✅ Funktionsdiagramm erzeugt: {PUML_FUNC}")

    elif mode == "class":
        puml = build_class_puml(packages, functions, structs, variables, members_by_struct)
        with open(PUML_CLASS, "w", encoding="utf-8") as f:
            f.write(puml)
        print(f"✅ Klassendiagramm erzeugt: {PUML_CLASS}")

    else:
        print("Unbekannter Modus. Benutze 'func' oder 'class'.")
        sys.exit(1)
