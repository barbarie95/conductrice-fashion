import os
from datetime import datetime, timedelta, timezone

from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from appwrite.id import ID

DATABASE_ID = "6ad7a426000ad1659f6b"


def reponse(context, donnees, code=200):
    return context.res.json(donnees, code)


def nettoyer(valeur, longueur):
    return str(valeur or "").strip()[:longueur]


def valeur_row(row, cle):
    """
    Récupère une propriété système d'une ligne Appwrite.
    Compatible avec les dictionnaires et les objets du SDK Python.
    """
    correspondances = {
        "$id": "id",
        "$createdAt": "created_at",
        "$updatedAt": "updated_at",
        "$permissions": "permissions"
    }
    attribut = correspondances.get(cle, cle)

    if isinstance(row, dict):
        valeur = row.get(cle)
        if valeur is not None:
            return valeur

        valeur = row.get(attribut)
        if valeur is not None:
            return valeur

    # Lecture directe des attributs du modèle Appwrite.
    for nom in (attribut, cle):
        try:
            valeur = getattr(row, nom, None)
            if valeur is not None:
                return valeur
        except Exception:
            pass

    # Compatibilité avec les modèles Pydantic du SDK récent.
    for nom_methode in ("model_dump", "to_dict"):
        methode = getattr(row, nom_methode, None)
        if callable(methode):
            for options in (
                {"by_alias": True},
                {},
            ):
                try:
                    donnees = methode(**options)
                    if isinstance(donnees, dict):
                        valeur = donnees.get(cle)
                        if valeur is None:
                            valeur = donnees.get(attribut)
                        if valeur is not None:
                            return valeur
                except (TypeError, ValueError, AttributeError):
                    pass
                except Exception:
                    pass

    return None


def date_compatible(valeur):
    """Convertit une date Appwrite en datetime avec fuseau horaire."""
    if isinstance(valeur, datetime):
        date = valeur
    elif valeur:
        texte = str(valeur).strip()
        try:
            date = datetime.fromisoformat(
                texte.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return None
    else:
        return None

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    return date


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
                "message": (
                    "Clé API indisponible. "
                    "Vérifie la configuration du backend."
                )
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

            reservation_id_genere = ID.unique()
            date_avant_creation = datetime.now(timezone.utc)

            row = db.create_row(
                database_id=DATABASE_ID,
                table_id=os.environ["TABLE_RESERVATIONS_ID"],
                row_id=reservation_id_genere,
                data=data
            )

            # Le row_id envoyé à Appwrite sert de solution de repli
            # si le SDK ne restitue pas la propriété système $id.
            reservation_id = (
                valeur_row(row, "$id")
                or reservation_id_genere
            )

            cree_le_brut = valeur_row(row, "$createdAt")
            date_creation = (
                date_compatible(cree_le_brut)
                or date_avant_creation
            )

            expiration = (
                date_creation + timedelta(hours=48)
            )

            return reponse(context, {
                "ok": True,
            "message": "Réservation confirmée ! ❤️",
                "reservation_id": str(reservation_id),
                "cree_le": date_creation.isoformat(),
                "expire_le": expiration.isoformat()
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

            commande_id_genere = ID.unique()

            row = db.create_row(
                database_id=DATABASE_ID,
                table_id=os.environ["TABLE_COMMANDES_ID"],
                row_id=commande_id_genere,
                data=data
            )

            commande_id = (
                valeur_row(row, "$id")
                or commande_id_genere
            )

            return reponse(context, {
                "ok": True,
                "message": "Commande enregistrée.",
                "commande_id": str(commande_id)
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
        
