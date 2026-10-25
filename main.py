import os
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime, timedelta, timezone

from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from appwrite.services.storage import Storage
from appwrite.id import ID
from appwrite.input_file import InputFile
from appwrite.query import Query

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


# =====================================================================
# ESPACE ADMINISTRATEUR
# Le code d'accès est vérifié ICI, côté serveur. Il n'apparaît jamais
# dans le code public : il est lu dans la variable ADMIN_CODE.
# =====================================================================
TABLE_SECURITE = "admin_securite"   # table privée (1 seule ligne)
LIGNE_SECURITE = "main"             # ID de cette ligne
DUREE_JETON = 3600                  # validité de la session : 1 heure
SEUIL_BLOCAGE = 3                   # blocage aux erreurs n° 3, 5, 7, 9...
MAX_VEDETTES = 4                    # produits vedettes de l'accueil

# --- AJOUT : photos des produits (zone de stockage lisible par tous) ---
BUCKET_PHOTOS = "photos-produits"
URL_PUBLIQUE = "https://fra.cloud.appwrite.io/v1"
PHOTO_MAX_OCTETS = 3000000          # 3 Mo, comme la zone de stockage

# --- AJOUT : rubriques de la boutique (valeurs de la colonne « categorie ») ---
CATEGORIES_VALIDES = [
    "ensemble_homme", "ensemble_femme", "robe",
    "accessoires_homme", "accessoires_femme"
]

# Statuts acceptés pour le suivi (à adapter si besoin)
STATUTS_VALIDES = {
    "commandes": [
        "en_attente", "confirmee", "expediee", "livree", "annulee"
    ],
    "reservations": [
        "en_attente", "confirmee", "annulee", "expiree"
    ],
}


def id_table(nom):
    """Retourne l'ID réel d'une table (variables de la fonction si présentes)."""
    if nom == "produits":
        return os.environ.get("TABLE_PRODUITS_ID", "produits")
    if nom == "reservations":
        return os.environ.get("TABLE_RESERVATIONS_ID", "reservations")
    if nom == "commandes":
        return os.environ.get("TABLE_COMMANDES_ID", "commandes")
    return None


def en_bool(valeur):
    """Convertit proprement une valeur reçue en booléen."""
    if isinstance(valeur, bool):
        return valeur
    return str(valeur).strip().lower() in ("1", "true", "oui", "vrai")


def encoder_b64(octets):
    return base64.urlsafe_b64encode(octets).decode("ascii").rstrip("=")


def creer_jeton(secret):
    """Crée un jeton signé (HMAC-SHA256) qui expire après DUREE_JETON."""
    charge = encoder_b64(
        json.dumps({"exp": int(time.time()) + DUREE_JETON}).encode("utf-8")
    )
    signature = hmac.new(
        secret.encode("utf-8"), charge.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return charge + "." + signature


def jeton_valide(jeton, secret):
    """Vérifie la signature et la date d'expiration du jeton."""
    try:
        charge, signature = str(jeton or "").split(".", 1)
        attendu = hmac.new(
            secret.encode("utf-8"), charge.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, attendu):
            return False
        remplissage = "=" * (-len(charge) % 4)
        donnees = json.loads(
            base64.urlsafe_b64decode(charge + remplissage)
        )
        return int(donnees.get("exp", 0)) > int(time.time())
    except Exception:
        return False


def row_en_dict(row):
    """Convertit une ligne Appwrite (dict ou objet SDK) en dictionnaire simple."""
    brut = None

    if isinstance(row, dict):
        brut = dict(row)
    else:
        for nom_methode in ("model_dump", "to_dict"):
            methode = getattr(row, nom_methode, None)
            if callable(methode):
                for options in ({"by_alias": True}, {}):
                    try:
                        resultat = methode(**options)
                        if isinstance(resultat, dict):
                            brut = resultat
                            break
                    except Exception:
                        pass
            if brut is not None:
                break

    if brut is None:
        brut = {}

    # Certains SDK rangent les colonnes dans une clé « data ».
    if isinstance(brut.get("data"), dict):
        for cle, valeur in brut["data"].items():
            brut.setdefault(cle, valeur)

    ignorees = (
        "data", "id", "sequence", "permissions", "database_id",
        "table_id", "databaseId", "tableId", "created_at",
        "updated_at", "createdAt", "updatedAt"
    )
    propre = {}
    for cle, valeur in brut.items():
        if str(cle).startswith("$") or cle in ignorees:
            continue
        if isinstance(valeur, datetime):
            valeur = valeur.isoformat()
        propre[cle] = valeur

    propre["id"] = str(
        valeur_row(row, "$id") or brut.get("$id") or brut.get("id") or ""
    )

    date = date_compatible(valeur_row(row, "$createdAt"))
    propre["cree_le"] = date.isoformat() if date else ""

    return propre


def lister_lignes(db, table):
    """Retourne les lignes d'une table (500 max), les plus récentes d'abord."""
    resultat = db.list_rows(
        database_id=DATABASE_ID,
        table_id=table,
        queries=[Query.limit(500)]
    )

    lignes = None
    if isinstance(resultat, dict):
        lignes = resultat.get("rows")
    else:
        lignes = getattr(resultat, "rows", None)
        if lignes is None:
            for nom_methode in ("model_dump", "to_dict"):
                methode = getattr(resultat, nom_methode, None)
                if callable(methode):
                    try:
                        donnees = methode()
                        if isinstance(donnees, dict):
                            lignes = donnees.get("rows")
                            break
                    except Exception:
                        pass

    liste = [row_en_dict(ligne) for ligne in (lignes or [])]
    liste.sort(key=lambda r: r.get("cree_le") or "", reverse=True)
    return liste


def lire_securite(db):
    """Lit (tentatives, fin_du_blocage). Une ligne absente = (0, 0)."""
    try:
        row = db.get_row(
            database_id=DATABASE_ID,
            table_id=TABLE_SECURITE,
            row_id=LIGNE_SECURITE
        )
    except Exception as erreur:
        if getattr(erreur, "code", None) == 404:
            return 0, 0
        raise

    donnees = row_en_dict(row)
    return (
        int(donnees.get("tentatives") or 0),
        int(donnees.get("verrou_jusqua") or 0)
    )


def sauver_securite(db, tentatives, verrou):
    """Enregistre le compteur d'erreurs (crée la ligne au besoin)."""
    data = {"tentatives": int(tentatives), "verrou_jusqua": int(verrou)}
    try:
        db.update_row(
            database_id=DATABASE_ID,
            table_id=TABLE_SECURITE,
            row_id=LIGNE_SECURITE,
            data=data
        )
    except Exception as erreur:
        if getattr(erreur, "code", None) == 404:
            db.create_row(
                database_id=DATABASE_ID,
                table_id=TABLE_SECURITE,
                row_id=LIGNE_SECURITE,
                data=data
            )
        else:
            raise


def connexion_admin(context, db, corps):
    """Vérifie le code, applique le blocage et renvoie un jeton."""
    code_attendu = os.environ.get("ADMIN_CODE", "")
    secret = os.environ.get("TOKEN_SECRET", "")

    if not code_attendu or not secret:
        context.error("ADMIN_CODE ou TOKEN_SECRET manquant.")
        return reponse(context, {
            "ok": False,
            "message": "Accès administrateur non configuré."
        }, 500)

    maintenant = int(time.time())
    tentatives, verrou = lire_securite(db)

    # Accès bloqué : on ne compare même pas le code.
    if verrou > maintenant:
        return reponse(context, {
            "ok": False,
            "bloque": True,
            "restant": verrou - maintenant,
            "message": "Accès bloqué."
        }, 429)

    # L'essai est compté AVANT la comparaison du code.
    # Si l'enregistrement échoue, l'accès est refusé (erreur 500).
    tentatives += 1
    nouveau_verrou = 0
    if tentatives >= SEUIL_BLOCAGE and tentatives % 2 == 1:
        # 3 erreurs → 2 h, 5 → 4 h, 7 → 6 h, 9 → 8 h...
        nouveau_verrou = maintenant + (tentatives - 1) * 3600
    sauver_securite(db, tentatives, nouveau_verrou)

    saisi = str(corps.get("code") or "")[:200]
    if hmac.compare_digest(
        saisi.encode("utf-8"), code_attendu.encode("utf-8")
    ):
        sauver_securite(db, 0, 0)
        return reponse(context, {
            "ok": True,
            "jeton": creer_jeton(secret),
            "duree": DUREE_JETON
        })

    if nouveau_verrou:
        return reponse(context, {
            "ok": False,
            "bloque": True,
            "restant": nouveau_verrou - maintenant,
            "message": "Code incorrect. Accès bloqué."
        }, 429)

    seuil = SEUIL_BLOCAGE if tentatives < SEUIL_BLOCAGE else tentatives + 1
    return reponse(context, {
        "ok": False,
        "bloque": False,
        "essais_restants": seuil - tentatives,
        "message": "Code incorrect."
    }, 401)


def preparer_produit(corps, creation):
    """Valide les champs d'un produit. Lève ValueError si invalide."""
    data = {}

    if creation or "nom" in corps:
        nom = nettoyer(corps.get("nom"), 200)
        if not nom:
            raise ValueError("Le nom du produit est obligatoire.")
        data["nom"] = nom

    if creation or "description" in corps:
        data["description"] = nettoyer(corps.get("description"), 2000)

    if creation or "prix" in corps:
        try:
            prix = float(corps.get("prix"))
        except (ValueError, TypeError):
            raise ValueError("Prix invalide.")
        if prix < 0:
            raise ValueError("Prix invalide.")
        data["prix"] = int(prix) if prix == int(prix) else prix

    if creation or "stock" in corps:
        try:
            stock = int(corps.get("stock", 0))
        except (ValueError, TypeError):
            raise ValueError("Stock invalide.")
        if stock < 0:
            raise ValueError("Stock invalide.")
        data["stock"] = stock

    if creation or "photo_url" in corps:
        data["photo_url"] = nettoyer(corps.get("photo_url"), 1000)

    if creation or "actif" in corps:
        data["actif"] = en_bool(corps.get("actif", True))

    if creation or "vedette" in corps:
        data["vedette"] = en_bool(corps.get("vedette", False))

    # --- AJOUT : rubrique de la boutique et case « Inspiration africaine » ---
    if "categorie" in corps:
        categorie = nettoyer(corps.get("categorie"), 30)
        if categorie not in CATEGORIES_VALIDES:
            raise ValueError("Choisis une rubrique pour ce produit.")
        data["categorie"] = categorie

    if "africaine" in corps:
        data["africaine"] = en_bool(corps.get("africaine"))

    return data


# --- AJOUT : envoi d'une photo de produit ---
def detecter_image(octets):
    """Reconnaît le vrai format à partir du contenu (pas du nom du fichier)."""
    if octets[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if octets[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", ".png"
    if octets[:4] == b"RIFF" and octets[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None, None


def envoyer_photo(context, client, corps):
    """Reçoit une photo (en base64), la vérifie, la range dans la zone
    publique et renvoie son lien. Lève ValueError si la photo est refusée."""
    if client is None:
        raise ValueError("Envoi de photo indisponible.")

    contenu = str(corps.get("contenu") or "")
    # Retire l'éventuel préfixe « data:image/jpeg;base64, »
    if "," in contenu[:100]:
        contenu = contenu.split(",", 1)[1]

    try:
        octets = base64.b64decode(contenu, validate=True)
    except Exception:
        raise ValueError("Photo illisible.")

    if not octets:
        raise ValueError("Photo vide.")
    if len(octets) > PHOTO_MAX_OCTETS:
        raise ValueError("Photo trop lourde (3 Mo maximum).")

    type_mime, extension = detecter_image(octets)
    if not type_mime:
        raise ValueError("Format non accepté. Utilise une photo JPEG, PNG ou WebP.")

    fichier_id = ID.unique()
    storage = Storage(client)
    storage.create_file(
        bucket_id=BUCKET_PHOTOS,
        file_id=fichier_id,
        file=InputFile.from_bytes(
            octets, "produit-" + str(fichier_id) + extension, type_mime
        )
    )

    url = (
        URL_PUBLIQUE + "/storage/buckets/" + BUCKET_PHOTOS
        + "/files/" + str(fichier_id) + "/view?project="
        + os.environ["APPWRITE_FUNCTION_PROJECT_ID"]
    )
    return reponse(context, {
        "ok": True,
        "message": "Photo envoyée.",
        "url": url
    })


def traiter_admin(context, db, action, corps, client=None):
    """Point d'entrée de toutes les actions « admin_* »."""
    if action == "admin_login":
        return connexion_admin(context, db, corps)

    # Toutes les autres actions exigent un jeton valide.
    secret = os.environ.get("TOKEN_SECRET", "")
    if not secret or not jeton_valide(corps.get("jeton"), secret):
        return reponse(context, {
            "ok": False,
            "expire": True,
            "message": "Session expirée. Reconnecte-toi."
        }, 401)

    try:
        # ---------- Tableau de bord ----------
        if action == "admin_stats":
            produits = lister_lignes(db, id_table("produits"))
            reservations = lister_lignes(db, id_table("reservations"))
            commandes = lister_lignes(db, id_table("commandes"))

            return reponse(context, {
                "ok": True,
                "stats": {
                    "produits_total": len(produits),
                    "produits_actifs": sum(
                        1 for p in produits if p.get("actif") is True
                    ),
                    "vedettes": sum(
                        1 for p in produits if p.get("vedette") is True
                    ),
                    "reservations_total": len(reservations),
                    "reservations_en_attente": sum(
                        1 for r in reservations
                        if r.get("statut") == "en_attente"
                    ),
                    "commandes_total": len(commandes),
                    "commandes_en_attente": sum(
                        1 for c in commandes
                        if c.get("statut") == "en_attente"
                    )
                }
            })

        # ---------- Listes (produits, réservations, commandes) ----------
        if action == "admin_liste":
            nom_table = str(corps.get("table") or "")
            table = id_table(nom_table)
            if not table:
                raise ValueError("Table inconnue.")
            return reponse(context, {
                "ok": True,
                "lignes": lister_lignes(db, table)
            })

        # ---------- Ajouter / modifier un produit ----------
        if action == "admin_produit":
            produit_id = nettoyer(corps.get("id"), 100)
            data = preparer_produit(corps, creation=not produit_id)

            # Maximum 4 produits vedettes.
            if data.get("vedette") is True:
                autres = [
                    p for p in lister_lignes(db, id_table("produits"))
                    if p.get("vedette") is True
                    and p.get("id") != produit_id
                ]
                if len(autres) >= MAX_VEDETTES:
                    return reponse(context, {
                        "ok": False,
                        "message": (
                            "Maximum " + str(MAX_VEDETTES)
                            + " produits vedettes. "
                            "Retire d'abord une étoile."
                        )
                    }, 409)

            if produit_id:
                db.update_row(
                    database_id=DATABASE_ID,
                    table_id=id_table("produits"),
                    row_id=produit_id,
                    data=data
                )
                return reponse(context, {
                    "ok": True,
                    "message": "Produit modifié.",
                    "id": produit_id
                })

            nouvel_id = ID.unique()
            db.create_row(
                database_id=DATABASE_ID,
                table_id=id_table("produits"),
                row_id=nouvel_id,
                data=data
            )
            return reponse(context, {
                "ok": True,
                "message": "Produit ajouté.",
                "id": str(nouvel_id)
            }, 201)

        # ---------- Supprimer un produit ----------
        if action == "admin_produit_supprimer":
            produit_id = nettoyer(corps.get("id"), 100)
            if not produit_id:
                raise ValueError("Produit introuvable.")
            db.delete_row(
                database_id=DATABASE_ID,
                table_id=id_table("produits"),
                row_id=produit_id
            )
            return reponse(context, {
                "ok": True,
                "message": "Produit supprimé."
            })

        # ---------- AJOUT : envoyer une photo de produit ----------
        if action == "admin_photo":
            return envoyer_photo(context, client, corps)
            
# ---------- Changer le statut d'une commande / réservation ----------
        if action == "admin_statut":
            nom_table = str(corps.get("table") or "")
            statut = nettoyer(corps.get("statut"), 50)
            ligne_id = nettoyer(corps.get("id"), 100)

            if nom_table not in STATUTS_VALIDES:
                raise ValueError("Table inconnue.")
            if statut not in STATUTS_VALIDES[nom_table]:
                raise ValueError("Statut invalide.")
            if not ligne_id:
                raise ValueError("Ligne introuvable.")

            db.update_row(
                database_id=DATABASE_ID,
                table_id=id_table(nom_table),
                row_id=ligne_id,
                data={"statut": statut}
            )
            return reponse(context, {
                "ok": True,
                "message": "Statut mis à jour."
            })

    except ValueError as erreur:
        return reponse(context, {
            "ok": False,
            "message": str(erreur)
        }, 400)

    return reponse(context, {
        "ok": False,
        "message": "Action inconnue."
    }, 400)


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

        # ---------------- ESPACE ADMINISTRATEUR ----------------
        if isinstance(action, str) and action.startswith("admin_"):
            return traiter_admin(context, db, action, corps, client)

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
