import os
from datetime import datetime, timedelta

from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from appwrite.id import ID

DATABASE_ID = "6ad7a426000ad1659f6b"


def reponse(context, donnees, code=200):
    return context.res.json(donnees, code)


def nettoyer(valeur, longueur):
    return str(valeur or "").strip()[:longueur]


def valeur_row(row, cle):
    """Lit une propriété d'un objet Row ou d'un dictionnaire."""
    if isinstance(row, dict):
        return row.get(cle)
    return getattr(row, cle, None)


def main(context):
    try:
        req = context.req
        methode = (req.method or "GET").upper()

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

        corps = req.body_json
        if not isinstance(corps, dict):
            return reponse(context, {
                "ok": False,
                "message": "Corps JSON invalide."
            }, 400)

        endpoint = os.environ["APPWRITE_FUNCTION_API_ENDPOINT"]
        project = os.environ["APPWRITE_FUNCTION_PROJECT_ID"]

        en_tetes = req.headers or {}
        api_key = (
            en_tetes.get("x-appwrite-key")
            or en_tetes.get("X-Appwrite-Key")
            or os.environ.get("APPWRITE_FUNCTION_API_KEY")
        )

        if not api_key:
            context.error("Clé API indisponible.")
            return reponse(context, {
                "ok": False,
                "message": "Clé API indisponible. Vérifie la configuration du backend."
            }, 500)

        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project)
        client.set_key(api_key)

        db = TablesDB(client)
        action = corps.get("action")

        # ---------------- RESERVATION ----------------
        if action == "reservation":
            obligatoires = [
                "produit_id",
                "produit_nom",
                "taille",
                "couleur",
                "quantite",
                "nom_client",
                "telephone"
            ]

            if any(
                not nettoyer(corps.get(k), 200)
                for k in obligatoires
            ):
                return reponse(context, {
                    "ok": False,
                    "message": "Complète tous les champs obligatoires."
                }, 400)

            try:
                quantite = int(corps["quantite"])
            except (ValueError, TypeError):
                quantite = 0

            if not 1 <= quantite <= 50:
                return reponse(context, {
                    "ok": False,
                    "message": "Quantité invalide."
                }, 400)

            data = {
                "produit_id": nettoyer(corps["produit_id"], 100),
                "produit_nom": nettoyer(corps["produit_nom"], 200),
                "taille": nettoyer(corps["taille"], 30),
                "couleur": nettoyer(corps["couleur"], 50),
                "quantite": quantite,
                "nom_client": nettoyer(corps["nom_client"], 150),
                "telephone": nettoyer(corps["telephone"], 30),
                "notes": nettoyer(corps.get("notes"), 1000),
                "statut": "en_attente"
            }

            row = db.create_row(
                database_id=DATABASE_ID,
                table_id=os.environ["TABLE_RESERVATIONS_ID"],
                row_id=ID.unique(),
                data=data
            )

            reservation_id = valeur_row(row, "$id")
            cree_le = valeur_row(row, "$createdAt")

            expiration = None
            if cree_le:
                date_creation = datetime.fromisoformat(
                    cree_le.replace("Z", "+00:00")
                )
                expiration = (
                    date_creation + timedelta(hours=48)
                ).isoformat()

            return reponse(context, {
                "ok": True,
                "message": "Réservation enregistrée.",
                "reservation_id": reservation_id,
                "cree_le": cree_le,
                "expire_le": expiration
            }, 201)

        # ---------------- COMMANDE ----------------
        if action == "commande":
            obligatoires = [
                "reference",
                "nom_client",
                "telephone",
                "articles"
            ]

            if any(
                not nettoyer(corps.get(k), 5000)
                for k in obligatoires
            ):
                return reponse(context, {
                    "ok": False,
                    "message": "Informations de commande manquantes."
                }, 400)

            try:
                montant = float(corps.get("montant_total", -1))
            except (ValueError, TypeError):
                montant = -1

            if montant < 0:
                return reponse(context, {
                    "ok": False,
                    "message": "Montant invalide."
                }, 400)

            data = {
                "reference": nettoyer(corps["reference"], 100),
                "nom_client": nettoyer(corps["nom_client"], 150),
                "telephone": nettoyer(corps["telephone"], 30),
                "adresse": nettoyer(corps.get("adresse"), 500),
                "montant_total": montant,
                "statut": "en_attente",
                "mode_paiement": nettoyer(
                    corps.get("mode_paiement"), 100
                ),
                "articles": nettoyer(corps["articles"], 5000),
                "notes": nettoyer(corps.get("notes"), 1000)
            }

            row = db.create_row(
                database_id=DATABASE_ID,
                table_id=os.environ["TABLE_COMMANDES_ID"],
                row_id=ID.unique(),
                data=data
            )

            commande_id = valeur_row(row, "$id")

            return reponse(context, {
                "ok": True,
                "message": "Commande enregistrée.",
                "commande_id": commande_id
            }, 201)

        return reponse(context, {
            "ok": False,
            "message": "Action inconnue."
        }, 400)

    except Exception as erreur:
        context.error(str(erreur))
        return reponse(context, {
            "ok": False,
            "message": "Erreur interne du backend."
        }, 500)
