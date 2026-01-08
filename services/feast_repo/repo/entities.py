from feast import Entity

# Définition de l'entité principale "user"
user = Entity(
    name="user",
    join_keys=["user_id"],
    description="Identifiant unique de l'utilisateur StreamFlow"
)