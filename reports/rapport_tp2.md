# Rapport TP2 : Ingestion mensuelle, validation et snapshots

---

---

## Exercice 1
### Question 1.a

**Etat initial du depot**

```terminaloutput
(base) aramsis@mac csc8613-tp1 % git status
Sur la branche main
Votre branche est à jour avec 'origin/main'.

rien à valider, la copie de travail est propre
```
---
### Question 1.b

Voici la structure des dossiers créée à la racine du projet :

```terminaloutput
(base) aramsis@mac csc8613-tp1 % ls -R
CSC8613-TP1.iml         api                     data                    db                      docker-compose.yml      img.png                 reports                 services

./api:
Dockerfile      app.py

./data:
seeds

./data/seeds:
month_000       month_001

./data/seeds/month_000:

./data/seeds/month_001:

./db:
init

./db/init:
month_000.zip   month_001.zip

./reports:
rapport.md      rapport_tp2.md

./services:
prefect

./services/prefect:

```
---

### Question 1.c 

Les archives ont été extraites. Voici le contenu des répertoires de données :

```terminaloutput
(base) aramsis@mac csc8613-tp1 % ls data/seeds/month_000
labels.csv              payments_agg_90d.csv    subscriptions.csv       support_agg_90d.csv     usage_agg_30d.csv       users.csv
(base) aramsis@mac csc8613-tp1 % ls data/seeds/month_001/
labels.csv              payments_agg_90d.csv    subscriptions.csv       support_agg_90d.csv     usage_agg_30d.csv       users.csv
```
---

## Exercice 2 

### Question 2.a 

Le fichier `db/init/001_schema.sql` a été créé avec les instructions `CREATE TABLE` pour les tables suivantes :
- users
- subscriptions
- usage_agg_30d
- payments_agg_90d
- support_agg_90d
- labels
---

### Question 2.b 

Le fichier `.env` permet de définir des variables d'environnement (comme les identifiants de base de données) qui seront automatiquement injectées dans les conteneurs par Docker Compose. Cela permet d'isoler la configuration sensible du code source et de l'image Docker.

---

### Question 2.c 

Contenu du fichier docker-compose.yml :

```yaml
services:
  postgres:
    image: postgres:16
    env_file: ../.env          # Utiliser les variables définies dans .env
    volumes:
      - ./db/init:/docker-entrypoint-initdb.d   # Monter les scripts d'init
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  prefect:
    build: ./services/prefect
    depends_on:
      - postgres
    env_file: ../.env          # Réutiliser les mêmes identifiants Postgres
    environment:
      PREFECT_API_URL: http://0.0.0.0:4200/api
      PREFECT_UI_URL: http://0.0.0.0:4200
      PREFECT_LOGGING_LEVEL: INFO
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - ./services/prefect:/opt/prefect/flows
      - ./data:/data:ro     # Rendre les CSV accessibles au conteneur Prefect

volumes:
  pgdata:
```
---

### Question 2.d 

Le service Postgres a été démarré et le schéma initialisé. Voici la liste des tables présentes :

```text
               List of relations
 Schema |       Name       | Type  |   Owner    
--------+------------------+-------+------------
 public | labels           | table | streamflow
 public | payments_agg_90d | table | streamflow
 public | subscriptions    | table | streamflow
 public | support_agg_90d  | table | streamflow
 public | usage_agg_30d    | table | streamflow
 public | users            | table | streamflow
(6 rows)
```

Description des tables :

- users : Contient les informations démographiques et statiques sur les utilisateurs (age, genre, etc...). 
- subscriptions : Détaille les informations contractuelles, les prix, les options souscrites et l'ancienneté. 
- usage_agg_30d : Agrège les données d'utilisation du service de streaming sur les 30 derniers jours. 
- payments_agg_90d : Recense les incidents de paiement sur les 3 derniers mois. 
- support_agg_90d : Résume les interactions avec le support client sur les 3 derniers mois. 
- labels : Contient la cible à prédire pour chaque utilisateur.

---

## Exercice 3 

### Question 3.a 

Le conteneur Prefect joue le rôle d'orchestrateur. Il gère l'exécution des flux de données, s'assure que les tâches s'exécutent dans l'ordre (ingestion, validation, snapshot) et gère les reprises en cas de retries.

---

### Question 3.b 

La fonction `upsert_csv` implémente une stratégie d'ingestion idempotente. Elle charge d'abord les données du CSV dans une table temporaire. Ensuite, elle effectue une requête SQL `INSERT ... ON CONFLICT DO UPDATE`. Cela signifie que si une ligne existe déjà (basé sur la clé primaire), ses valeurs sont mises à jour avec les nouvelles données (`EXCLUDED`), sinon la ligne est insérée normalement. Cela évite les doublons et permet de rejouer le script sans erreur.

---

### Question 3.c : Exécution de l'ingestion month_000

L'ingestion s'est déroulée avec succès. Voici les comptages en base de données :

```sql
streamflow=# SELECT COUNT(*) FROM users;
 count 
-------
  7043
(1 row)

streamflow=# SELECT COUNT(*) FROM subscriptions;
 count 
-------
  7043
(1 row)
```
Conclusion : Nous avons **7043** clients enregistrés après l'ingestion du mois 0.

---
## Exercice 4 

### Question 4.a 

La fonction `validate_with_ge` s'insère dans le pipeline après l'ingestion (upsert) et avant la création des snapshots. Son rôle est de servir de garde-fou : elle vérifie que les données respectent des règles prédéfinies (schéma, types, domaines de valeurs...). Si une règle est violée, le pipeline s'arrête immédiatement, ce qui empêche des données corrompues de polluer les snapshots historiques et garantit que le modèle futur sera entraîné sur des données fiables.

### Question 4.b 

L'ingestion pour le mois `month_000` a été relancée avec l'étape de validation activée. Le flow s'est terminé avec succès, confirmant que les données initiales respectent les règles implémentées.

```terminaloutput
(.venv) (base) aramsis@mac csc8613-tp1 % docker compose exec \
  -e SEED_DIR=/data/seeds/month_000 \
  -e AS_OF=2024-01-31 \
  prefect python ingest_flow.py
14:10:14.599 | INFO    | Flow run 'screeching-newt' - Beginning flow run 'screeching-newt' for flow 'ingest_month'
14:10:14.601 | INFO    | Flow run 'screeching-newt' - View at http://0.0.0.0:4200/runs/flow-run/1d949639-df30-437a-8eee-c97ac9137259
14:10:14.793 | INFO    | Task run 'upsert_csv-d8e' - Finished in state Completed()
14:10:14.990 | INFO    | Task run 'upsert_csv-afd' - Finished in state Completed()
14:10:15.168 | INFO    | Task run 'upsert_csv-f29' - Finished in state Completed()
14:10:15.258 | INFO    | Task run 'upsert_csv-68e' - Finished in state Completed()
14:10:15.381 | INFO    | Task run 'upsert_csv-a72' - Finished in state Completed()
14:10:15.478 | INFO    | Task run 'upsert_csv-433' - Finished in state Completed()
14:10:15.516 | INFO    | Task run 'validate_with_ge-b93' - Finished in state Completed()
14:10:15.564 | INFO    | Task run 'validate_with_ge-bc4' - Finished in state Completed()
14:10:15.678 | INFO    | Task run 'validate_with_ge-78c' - Finished in state Completed()
14:10:15.688 | INFO    | Flow run 'screeching-newt' - Finished in state Completed()

```
### Question 4.c

Voici les expectations ajoutées pour la table `usage_agg_30d` :

```python
# Vérification que toutes les colonnes attendues sont présentes
gdf.expect_table_columns_to_match_set([
    "user_id", "watch_hours_30d", "avg_session_mins_7d",
    "unique_devices_30d", "skips_7d", "rebuffer_events_7d"
])

# Vérification que les durées sont positives
gdf.expect_column_values_to_be_between("watch_hours_30d", min_value=0)
gdf.expect_column_values_to_be_between("avg_session_mins_7d", min_value=0)
```
**Justification des bornes** : 

J'ai choisi min_value=0 pour watch_hours_30d et avg_session_mins_7d car ce sont des durées. 
Une valeur négative serait physiquement impossible et indiquerait une corruption des données à la source ou un bug dans le calcul des agrégats.

**Protection du modèle :**

Ces règles empêchent le modèle d'apprendre sur des données aberrantes, ce qui pourrait dégrader sa performance ou mener à des prédictions absurdes. 
De plus, expect_table_columns_to_match_set garantit qu'il n'y a pas eu de schéma drift, par exemple une colonne renommée ou manquante, qui ferait planter le code d'entrainement.

---

## Exercice 5 

### Question 5.a 

J'ai implémenté la fonction `snapshot_month` qui prend en paramètre une date `as_of`. Elle permet de copier l'état actuel des tables "live" (qui sont constamment mises à jour) vers des tables d'historique (snapshots).
Le champ `as_of` sert d'étiquette temporelle : il permet de savoir exactement quel était l'état d'un utilisateur à la fin d'un mois donné. C'est la clé composite `(user_id, as_of)` qui garantit l'unicité dans ces tables.

### Question 5.b 

J'ai exécuté l'ingestion pour les deux mois successifs. Voici le nombre de lignes dans la table de snapshots :

```sql
streamflow=# SELECT COUNT(*) FROM subscriptions_profile_snapshots WHERE as_of = '2024-01-31';
 count 
-------
  7043
(1 row)

streamflow=# SELECT COUNT(*) FROM subscriptions_profile_snapshots WHERE as_of = '2024-02-29';
 count 
-------
  7043
(1 row)
```

**Observation :** 

Nous avons exactement le même nombre de lignes (7043) pour les deux mois. Cela indique que l'ingestion du mois de février consistait principalement en des mises à jour des profils existants (via la logique d'Upsert) sans création de nouveaux comptes clients dans ce jeu de données spécifique. Le système a bien créé deux partitions temporelles distinctes pour la même base d'utilisateurs.


### Question 5.c 

**Schema de la pipeline**

```text
[ CSV ] --> [ Lecture & Parsing ] --> [ Upsert (PostgreSQL Live Tables) ]
                                              |
                                              v
                                     [ Validation (Great Expectations) ]
                                              |
                                       (Si Succès)
                                              |
                                              v
                                [ Création Snapshot (as_of) ]
```

**Pourquoi des snapshots ?**

- Pourquoi ne pas travailler directement sur les tables live ? Les tables live représentent l'état "maintenant". Si on entraîne un modèle sur ces tables, l'expérience n'est pas reproductible : si on relance l'entraînement demain, les données auront changé. De plus, on perdrait l'historique des valeurs passées nécessaire pour comprendre l'évolution du comportement client. 
- Importance pour la Data Leakage : cela se produit si le modèle utilise des informations du futur pour prédire le passé. Par exemple, utiliser une consommation de données du mois de mars pour prédire un désabonnement en février. Les snapshots figent les données à une date précise (as_of), garantissant que le modèle n'a accès qu'aux informations disponibles à ce moment-là.


**Difficultés rencontrées :**

- La compréhension de la logique SQL ON CONFLICT combinée à la création dynamique de la chaîne de mise à jour (SET col = EXCLUDED.col) dans Python a demandé de l'attention. 
- Configurer correctement la connexion entre le conteneur Prefect et Postgres via les variables d'environnement Docker.

**Erreurs et corrections :**
- J'ai dû m'assurer que les tables de snapshots étaient bien créées avant de tenter l'insertion. 
- J'ai vérifié que le champ as_of était bien propagé depuis le flow jusqu'à la requête SQL pour éviter de mélanger les mois.
- J'ai rencontré des erreurs de connexion SQL au début, corrigées en vérifiant les variables dans le .env. 
- Une erreur de validation Great Expectations est survenue sur les bornes négatives, que j'ai corrigée en ajustant la configuration.