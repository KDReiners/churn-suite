### Git-Quickstart (für dieses Repository)

Letzte Aktualisierung: 2025-09-23

#### Kürzester Weg: Commit → Push → PR nach main (Auto‑Merge)
- Assistenten-Befehl (Copy & Paste):
  - "Bitte alle lokalen Änderungen inkl. Submodule committen, aktuellen Branch pushen, PR gegen main erstellen und Auto‑Merge (Squash) aktivieren. Commit-Message: '<git instructions added>'."

#### Was passiert dabei (automatisiert durch den Assistenten)
- Submodule prüfen: lokale Änderungen in Submodulen werden auf Branches committet und gepusht
- Super-Repo: alle Änderungen (`git add -A`) committen und pushen
- PR gegen `main` erstellen und Auto‑Merge (Squash) aktivieren

#### Manuelle CLI (falls ohne Assistent)
```bash
# 1) Submodule initialisieren und lokale Änderungen (falls vorhanden) committen/pushen
git submodule update --init --recursive
git submodule foreach --recursive '
  st=$(git status --porcelain); 
  if [ -n "$st" ]; then 
    cb=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD); 
    if [ "$cb" = "HEAD" ] || [ "$cb" = "(no branch)" ]; then 
      nb="chore/sync-submodule-$(date +%F)-$(git rev-parse --short HEAD)"; 
      git switch -c "$nb"; 
    fi; 
    git add -A; 
    git commit -m "chore: sync submodule changes" || true; 
    git push -u origin HEAD; 
  else 
    echo "no changes in $name"; 
  fi'

# 2) Super-Repo commit & push
git add -A
git commit -m "<git instructions added>" || true
git push -u origin HEAD

# 3) PR erstellen (GitHub CLI) und Auto‑Merge aktivieren
gh pr create -B main -H "$(git rev-parse --abbrev-ref HEAD)" -t "docs: add GIT.md" -b "Auto PR" -f
gh pr merge "$(git rev-parse --abbrev-ref HEAD)" --squash --auto -d
```

#### Hinweise
- Große Artefakte (>50MB) gehören nicht in Git-Historie. Nutzung: `.gitignore`, JSON‑DB/DAL oder Release Assets.
- Branch-Namen gemäß Projektregeln: `feature/<slug>`, `fix/<ticket>`, `chore/<task>`.


