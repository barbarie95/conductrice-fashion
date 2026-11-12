/* ==========================================================================
   JUPITER IA - Fonctions communes (connexion Appwrite, appels au backend)
   Chaque page charge d'abord le SDK Appwrite, puis ce fichier.
   Aucune clé secrète ici : seuls l'adresse du serveur et l'ID du projet,
   qui sont publics par nature.
   ========================================================================== */
(function () {
  "use strict";

  var ENDPOINT = "https://fra.cloud.appwrite.io/v1";
  var PROJET = "6ad7761700274f3ae4b1";
  var FONCTION = "jupiter-backend";

  var client = new Appwrite.Client().setEndpoint(ENDPOINT).setProject(PROJET);
  var compte = new Appwrite.Account(client);
  var fonctions = new Appwrite.Functions(client);

  /* ---------- Textes d'erreur lisibles ---------- */
  function traduire(erreur) {
    var type = (erreur && erreur.type) || "";
    var message = (erreur && erreur.message) || "";
    var code = erreur && erreur.code;
    if (type === "user_invalid_credentials") return "E-mail ou mot de passe incorrect.";
    if (type === "user_already_exists") return "Un compte existe déjà avec cet e-mail.";
    if (type === "user_blocked") return "Ce compte est bloqué.";
    if (type === "general_rate_limit_exceeded" || code === 429) return "Trop de tentatives. Réessaie dans un instant.";
    if (/password/i.test(message)) return "Mot de passe invalide (8 caractères minimum).";
    if (/email/i.test(message)) return "Adresse e-mail invalide.";
    if (/network|fetch|failed/i.test(message)) return "Connexion impossible. Vérifie ton Internet.";
    return message || "Une erreur est survenue.";
  }

  /* ---------- Compte utilisateur ---------- */
  async function utilisateur() {
    try { return await compte.get(); } catch (e) { return null; }
  }

  // Redirige vers la connexion si personne n'est connecté
  async function exigerConnexion() {
    var u = await utilisateur();
    if (!u) { window.location.replace("connexion.html"); return null; }
    return u;
  }

  // Redirige vers la discussion si l'utilisateur est déjà connecté
  async function redirigerSiConnecte() {
    var u = await utilisateur();
    if (u) window.location.replace("chat.html");
    return u;
  }

  async function connecter(email, motDePasse) {
    try { await compte.createEmailPasswordSession(email, motDePasse); }
    catch (e) { throw new Error(traduire(e)); }
  }

  async function inscrire(nom, email, motDePasse) {
    try { await compte.create(Appwrite.ID.unique(), email, motDePasse, nom); }
    catch (e) { throw new Error(traduire(e)); }
    await connecter(email, motDePasse);
  }

  async function deconnecter() {
    try { await compte.deleteSession("current"); } catch (e) { /* déjà déconnecté */ }
    window.location.replace("index.html");
  }

  function estAdmin(u) {
    return !!(u && u.labels && u.labels.indexOf("admin") !== -1);
  }

  /* ---------- Appels au backend (fonction jupiter-backend) ---------- */
  async function appeler(action, donnees) {
    var corps = Object.assign({ action: action }, donnees || {});
    var execution;
    try {
      execution = await fonctions.createExecution(
        FONCTION, JSON.stringify(corps), false, "/", "POST",
        { "content-type": "application/json" }
      );
    } catch (e) {
      throw new Error(traduire(e));
    }
    var reponse;
    try { reponse = JSON.parse(execution.responseBody || "{}"); }
    catch (e) { throw new Error("Réponse inattendue du serveur."); }
    if (!reponse.ok) {
      var erreur = new Error(reponse.erreur || "Une erreur est survenue.");
      erreur.code = execution.responseStatusCode;
      throw erreur;
    }
    return reponse;
  }

  /* ---------- Affichage sûr du texte ---------- */
  function echapper(texte) {
    var table = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return String(texte == null ? "" : texte).replace(/[&<>"']/g, function (c) { return table[c]; });
  }

  // Met en forme les réponses de l'IA : titres, gras, italique, code, listes à puces,
  // listes numérotées, blocs de code et liens. Le texte est échappé AVANT toute mise en forme.
  function formater(texte) {
    var html = [];
    var liste = "";        // "ul", "ol" ou "" (aucune liste ouverte)
    var dansCode = false;  // à l'intérieur d'un bloc de code ```
    var STYLE_CODE = "overflow-x:auto;white-space:pre-wrap;background:rgba(7,59,70,.08);padding:10px 12px;border-radius:10px;margin:8px 0";

    function fermerListe() {
      if (liste) { html.push("</" + liste + ">"); liste = ""; }
    }

    function enLigne(t) {
      return t
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
        .replace(/(https?:\/\/[^\s<]+)/g, function (url) {
          var fin = (url.match(/[.,:!?)]+$/) || [""])[0];   // la ponctuation finale reste hors du lien
          var lien = fin ? url.slice(0, -fin.length) : url;
          return '<a href="' + lien + '" target="_blank" rel="noopener noreferrer">' + lien + "</a>" + fin;
        });
    }

    echapper(texte).split("\n").forEach(function (ligne) {
      // Bloc de code : lignes entre deux ```
      if (/^\s*```/.test(ligne)) {
        fermerListe();
        if (dansCode) { html.push("</code></pre>"); dansCode = false; }
        else { html.push('<pre style="' + STYLE_CODE + '"><code>'); dansCode = true; }
        return;
      }
      if (dansCode) { html.push(ligne + "\n"); return; }

      var titre = ligne.match(/^\s*#{1,6}\s+(.*)$/);
      var puce = ligne.match(/^\s*[-*•]\s+(.*)$/);
      var numero = ligne.match(/^\s*(\d+)[.)]\s+(.*)$/);

      if (/^\s*([-*_])\1{2,}\s*$/.test(ligne)) {          // ligne de séparation : ignorée
        fermerListe();
      } else if (titre) {
        fermerListe();
        html.push("<h3>" + enLigne(titre[1]) + "</h3>");
      } else if (puce) {
        if (liste !== "ul") { fermerListe(); html.push("<ul>"); liste = "ul"; }
        html.push("<li>" + enLigne(puce[1]) + "</li>");
      } else if (numero) {
        if (liste !== "ol") { fermerListe(); html.push('<ol start="' + numero[1] + '">'); liste = "ol"; }
        html.push("<li>" + enLigne(numero[2]) + "</li>");
      } else if (ligne.trim() === "") {
        fermerListe();
      } else {
        fermerListe();
        html.push("<p>" + enLigne(ligne) + "</p>");
      }
    });
    fermerListe();
    if (dansCode) html.push("</code></pre>");
    return html.join("");
  }

  /* ---------- Petits outils d'interface ---------- */
  // Affiche un message dans un élément (type : "erreur" ou "ok"), ou le cache si texte vide
  function message(element, texte, type) {
    if (!element) return;
    if (!texte) { element.classList.add("cache"); element.textContent = ""; return; }
    element.className = "alerte " + (type === "ok" ? "alerte-ok" : "alerte-erreur");
    element.textContent = texte;
    element.setAttribute("role", "alert");
  }

  // Désactive un bouton pendant une opération
  function occupe(bouton, actif, texteEnCours) {
    if (!bouton) return;
    if (actif) {
      bouton.dataset.texte = bouton.textContent;
      bouton.disabled = true;
      if (texteEnCours) bouton.textContent = texteEnCours;
    } else {
      bouton.disabled = false;
      if (bouton.dataset.texte) bouton.textContent = bouton.dataset.texte;
    }
  }

  window.JIA = {
    utilisateur: utilisateur,
    exigerConnexion: exigerConnexion,
    redirigerSiConnecte: redirigerSiConnecte,
    connecter: connecter,
    inscrire: inscrire,
    deconnecter: deconnecter,
    estAdmin: estAdmin,
    appeler: appeler,
    echapper: echapper,
    formater: formater,
    message: message,
    occupe: occupe
  };
})();
