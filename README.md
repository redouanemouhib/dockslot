# DockSlot

DockSlot est un prototype de réservation de créneaux de carénage pour navires industriels, réalisé dans le cadre de l’exercice de recrutement Full Stack & IA de PUREGLIDE (groupe GREENOV-ITES).

## Fonctionnement

- **Exploitant** — recherche des chantiers par port, longueur, largeur et tirant d’eau du navire. Il consulte les créneaux disponibles, dépose une demande et suit son statut.
- **Chantier naval** — consulte ses demandes et peut les accepter ou les refuser.
- **API** — valide les dimensions, enregistre les demandes dans SQLite et bloque deux confirmations pour un même créneau ou pour des périodes qui se chevauchent dans la même cale.

L’interface utilise **React, Vite et Tailwind CSS**. L’API REST utilise **FastAPI et Pydantic** avec une base **SQLite**. Les chantiers et les créneaux sont fictifs, et les rôles sont simulés sans authentification.

## Lancer le projet sous Windows

Prérequis : **Python 3.11 ou supérieur**. L’archive contient le frontend précompilé. Node.js est nécessaire uniquement pour recompiler le frontend après une modification du code.

1. Extraire le ZIP et ouvrir dans VS Code le dossier **DockSlot**, qui contient `backend` et `frontend`.
2. Ouvrir **Terminal → Nouveau terminal**, puis exécuter ces commandes dans PowerShell :

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
   ```

   Si la commande `py` est introuvable, utiliser `python -m venv .venv` pour la première ligne.

3. Ouvrir [DockSlot](http://127.0.0.1:8000) dans le navigateur. La documentation API est disponible sur [Swagger](http://127.0.0.1:8000/docs).

Laisser le terminal ouvert pendant l’utilisation. Pour arrêter le serveur, appuyer sur **Ctrl + C**. Au prochain lancement, seule la commande Uvicorn est nécessaire.

## Démo rapide

Garder les critères préremplis pour **Marseille**, choisir un créneau de **Forme du Cap** et envoyer une demande. Dans **Espace chantier**, accepter cette demande, puis revenir dans **Mes réservations** pour constater le statut **Confirmée**.

## Tests et utilisation de l’IA

Les sept tests d’API et le parcours Chromium sur bureau et mobile simulé ont réussi. Le fichier `RESULTATS_TESTS.md` détaille les vérifications. Le prototype ne fait aucun appel à une IA pendant son exécution.
