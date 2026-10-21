# PARTIE 1/3 — Configuration et réponses
import os
from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from appwrite.id import ID


DATABASE_ID = "6ad7a426000ad1659f6b"


def reponse(context, donnees, code=200):
    return context.res.json(donnees, code)


# PARTIE 2/3 — Connexion à Appwrite
def main(context):
    try:
        client = Client()
        client.set_endpoint(
            os.environ["APPWRITE_FUNCTION_API_ENDPOINT"]
        )
        client.set_project(
            os.environ["APPWRITE_FUNCTION_PROJECT_ID"]
        )
        client.set_key(
            os.environ["APPWRITE_FUNCTION_API_KEY"]
        )

        db = TablesDB(client)
        req = context.req
        methode = req.method.upper()

        if methode == "GET":
            return reponse(context, {
                "ok": True,
                "message": "ConductriceFashion Backend actif."
            })

        if methode != "POST":
            return reponse(context, {
                "ok": False,
                "message": "Méthode non autorisée."
            }, 405)

        corps = req.bodyJson
        if not isinstance(corps, dict):
            return reponse(context, {
                "ok": False,
                "message": "Données JSON invalides."
            }, 400)

        # PARTIE 3/3 — Réservations et commandes
        action = corps.get("action")

        if action == "reservation":
            champs = [
                "produit_id", "produit_nom", "taille",
                "couleur", "quantite", "nom_client",
                "telephone"
            ]

            if any(not corps.get(c) for c in champs):
                return reponse(context, {
                    "ok": False,
                    "message": "Des champs obligatoires manquent."
                }, 400)

            try:
                quantite = int(corps["quantite"])
            except (ValueError, TypeError):
                quantite = 0

            if quantite < 1 or quantite > 50:
                return reponse(context, {
                    "ok": False,
                    "message": "Quantité invalide."
                }, 400)

            table_id = os.environ["TABLE_RESERVATIONS_ID"]

            donnees = {
                "produit_id": str(corps["produit_id"])[:100],
                "produit_nom": str(corps["produit_nom"])[:200],
                "taille": str(corps["taille"])[:30],
                "couleur": str(corps["couleur"])[:50],
                "quantite": quantite,
                "nom_client": str(corps["nom_client"])[:150],
                "telephone": str(corps["telephone"])[:30],
                "notes": str(corps.get("notes", ""))[:1000],
                "statut": "en_attente"
            }

            resultat = db.create_row(
                database_id=DATABASE_ID,
                table_id=table_id,
                row_id=ID.unique(),
                data=donnees
            )

            return reponse(context, {
                "ok": True,
                "message": "Réservation enregistrée.",
                "reservation_id": resultat["$id"],
                "cree_le": resultat["$createdAt"]
            }, 201)

        if action == "commande":
            champs = [
                "reference", "nom_client", "telephone",
                "montant_total", "articles", "statut"
            ]

            if any(corps.get(c) is None for c in champs):
                return reponse(context, {
                    "ok": False,
                    "message": "Des champs obligatoires manquent."
                }, 400)

            table_id = os.environ["TABLE_COMMANDES_ID"]

            donnees = {
                "reference": str(corps["reference"])[:100],
                "nom_client": str(corps["nom_client"])[:150],
                "telephone": str(corps["telephone"])[:30],
                "adresse": str(corps.get("adresse", ""))[:500],
                "montant_total": float(corps["montant_total"]),
                "statut": str(corps["statut"])[:50],
                "mode_paiement": str(
                    corps.get("mode_paiement", "")
                )[:100],
                "articles": str(corps["articles"])[:5000],
                "notes": str(corps.get("notes", ""))[:1000]
            }

            if donnees["montant_total"] < 0:
                return reponse(context, {
                    "ok": False,
                    "message": "Montant invalide."
                }, 400)

            resultat = db.create_row(
                database_id=DATABASE_ID,
                table_id=table_id,
                row_id=ID.unique(),
                data=donnees
            )

            return reponse(context, {
                "ok": True,
                "message": "Commande enregistrée.",
                "commande_id": resultat["$id"]
            }, 201)

        return reponse(context, {
            "ok": False,
            "message": "Action inconnue."
        }, 400)

    except Exception as erreur:
        context.error(str(erreur))
        return reponse(context, {
            "ok": False,
            "message": "Erreur du backend. Vérifiez sa configuration."
        }, 500)
