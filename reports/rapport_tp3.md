# Contexte

Suite à la mise en place du pipeline d'ingestion (TP2), nous disposons désormais de données validées par Great Expectations et historisées sous forme de snapshots mensuels (pour janvier et février 2024) dans PostgreSQL. 
Ces données couvrent l'ensemble du cycle de vie client StreamFlow : profils utilisateurs, abonnements, usage, paiements et support.

L'objectif de ce TP3 est d'intégrer le Feature Store Feast pour centraliser et standardiser la définition des features. 
Nous allons connecter Feast à nos snapshots PostgreSQL pour générer un dataset d'entraînement cohérent (mode offline) et exposer ces mêmes features en temps réel via une API FastAPI (mode online). 
Cette étape sert a garantir la reproductibilité et éviter le training-serving skew dans notre futur système de prédiction de churn.
---

# Mise en place de Feast

## Commande de démarrage

Pour construire l'image et démarrer les services en arrière-plan, j'ai utilisé la commande suivante :

```bash
docker compose up -d --build
```

## Rôle du conteneur Feast

Le conteneur feast fournit l'environnement d'exécution isolé nécessaire pour utiliser la CLI Feast.

- Configuration : Les fichiers de définition du Feature Store (feature_store.yaml, entities.py, etc.) sont situés dans le dossier /repo à l'intérieur du conteneur (monté depuis le dossier ./services/feast_repo/repo de la machine hôte). 
- Utilisation : Ce conteneur servira à exécuter les commandes d'administration du Feature Store, notamment `feast apply` (pour enregistrer les définitions dans registry.db) et `feast materialize` (pour transférer les données vers le store en ligne), via la commande `docker compose exec feast ...`.

---

# Définition du Feature Store

### Entity
Une **Entity** dans Feast représente l'objet métier principal auquel sont rattachées les features. C'est la clé de jointure utilisée lors de la récupération des données.
Nous avons choisi `user_id` comme clé de jointure car c'est l'identifiant unique et stable de nos utilisateurs dans toutes les tables PostgreSQL (`users`, `subscriptions`, etc.) du projet StreamFlow.

### Data Sources
Les Data Sources pointent vers nos tables de snapshots. Par exemple, la source `usage_agg_30d_source` pointe vers la table `usage_agg_30d_snapshots` et expose des features comme :
* `watch_hours_30d`
* `unique_devices_30d`
* `rebuffer_events_7d`

### Rôle de `feast apply`
La commande `feast apply` parcourt les fichiers de définition Python (`entities.py`, `feature_views.py`, etc.), valide la configuration, et met à jour le registre central (`registry.db`). C'est l'équivalent d'un "commit" de l'infrastructure de features : elle rend les nouvelles définitions disponibles pour la récupération offline et la matérialisation online.

---
# Récupération offline & online


## Récuparation offline

Commande utilisée :
```bash
docker compose exec prefect python build_training_dataset.py
```
Aperçu du fichier data/processed/training_df.csv :

```csv
user_id,event_timestamp,months_active,monthly_fee,paperless_billing,watch_hours_30d,avg_session_mins_7d,failed_payments_90d,churn_label
3413-BMNZE,2024-01-31,1,45.25,False,32.0919931169304,29.141044640845102,0,False
6234-RAAPL,2024-01-31,72,99.9,False,30.9473266233405,29.141044640845102,0,False
6047-YHPVI,2024-01-31,5,69.7,True,30.2923914752724,29.141044640845102,1,False
6572-ADKRS,2024-01-31,46,74.8,True,35.6419493369159,29.141044640845102,0,False
```

**Garantie de la "Temporal Correctness" :** 

Feast assure l'absence de fuite de données (data leakage) grâce à la configuration timestamp_field="as_of" dans les DataSources. Lors de la récupération offline, pour chaque couple (user_id, event_timestamp) demandé, Feast parcourt l'historique et sélectionne uniquement les valeurs valides à cet instant précis (valeurs connues avant ou à la date de l'événement). Cela empêche strictement le modèle d'apprendre en utilisant des informations du futur.


## Récupération Online

J'ai testé la récupération des features depuis le Online Store pour l'utilisateur 7590-VHVEG via un script Python interne.

Résultat :
JSON

{
  "user_id": ["7590-VHVEG"], 
  "paperless_billing": [true], 
  "monthly_fee": [29.850000381469727], 
  "months_active": [1]
}

Cas d'un utilisateur manquant : Si l'on interroge un utilisateur qui n'existe pas ou qui n'a pas été matérialisé (hors fenêtre temporelle), Feast retourne des valeurs None (ou null) pour les champs demandés, sans lever d'erreur technique. 

## Intégration API

L'API expose désormais un endpoint qui interroge Feast en temps réel.

Requête de test :
```bash
curl http://localhost:8000/features/7590-VHVEG
```

Réponse JSON :
```json
{
  "user_id": "7590-VHVEG",
  "features": {
    "user_id": "7590-VHVEG",
    "months_active": 1,
    "monthly_fee": 29.850000381469727,
    "paperless_billing": true
  }
}
```

# Réflexion

**Réduction du Training-Serving Skew :** 

L'intégration de Feast via l'endpoint /features/{user_id} est déterminante pour réduire le training-serving skew. Le problème classique en production est la divergence entre le code qui prépare les données d'entraînement (souvent des scripts batch SQL/Python complexes) et le code qui prépare les données pour l'inférence temps réel. Ici, nous définissons la logique une seule fois via les FeatureViews. C'est Feast qui gère la complexité sous-jacente : il sert les données historiques pour l'entraînement et les données fraîches pour l'API, garantissant que le modèle reçoit exactement les mêmes inputs (même sémantique, même type) dans les deux mondes.

Le dépôt a été tagué avec l'étiquette tp3.