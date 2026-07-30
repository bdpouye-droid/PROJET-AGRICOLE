import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Projet Agricole - Gestion & Validation",
    page_icon="🌾",
    layout="wide"
)

# --- ACTUALISATION AUTOMATIQUE (Toutes les 5 secondes = 5000 millisecondes) ---
# Cela permet à tous les écrans connectés de se mettre à jour en quasi-simultané
count = st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA BASE DE DONNÉES EN MÉMOIRE (SESSION STATE) ---
if 'budget_global' not in str_app.session_state:
    str_app.session_state.budget_global = 10000000.0  # 10 Millions

if 'solde_restant' not in str_app.session_state:
    str_app.session_state.solde_restant = 10000000.0

if 'demandes' not in str_app.session_state:
    str_app.session_state.demandes = []

if 'cahiers_charges' not in str_app.session_state:
    str_app.session_state.cahiers_charges = {}

if 'stocks_agricole' not in str_app.session_state:
    str_app.session_state.stocks_agricole = pd.DataFrame([
        {"Article": "Sacs d'engrais NPK (50kg)", "Quantité": 120, "Seuil Alerte": 30, "Emplacement": "Hangar Principal"},
        {"Article": "Semences maraîchères (kg)", "Quantité": 450, "Seuil Alerte": 100, "Emplacement": "Chambre froide"}
    ])

# --- DICTIONNAIRE DES UTILISATEURS & RÔLES ---
UTILISATEURS = {
    "DEP1": {"nom": "Agriculture", "mdp": "DEP123", "type": "standard", "dept": "Agriculture"},
    "DEP2": {"nom": "Élevage & Halieutique", "mdp": "DEP123", "type": "standard", "dept": "Élevage & Halieutique"},
    "DEP3": {"nom": "Industrie & Transformation", "mdp": "DEP123", "type": "standard", "dept": "Industrie & Transformation"},
    "DEP4": {"nom": "Ressources Hydriques", "mdp": "DEP123", "type": "standard", "dept": "Ressources Hydriques"},
    "DEP5": {"nom": "Énergie & Maintenance", "mdp": "DEP123", "type": "standard", "dept": "Énergie & Maintenance"},
    "DEP6": {"nom": "Recherche & Développement", "mdp": "DEP123", "type": "standard", "dept": "Recherche & Développement"},
    "DEP7": {"nom": "Sécurité & HSE", "mdp": "DEP123", "type": "standard", "dept": "Sécurité & HSE"},
    "DEP8": {"nom": "Ressources Humaines & RSE", "mdp": "DEP123", "type": "standard", "dept": "Ressources Humaines & RSE"},
    "DEP9": {"nom": "Commercial & Marketing", "mdp": "DEP123", "type": "standard", "dept": "Commercial & Marketing"},
    "DEP10": {"nom": "IT & Data", "mdp": "DEP123", "type": "standard", "dept": "IT & Data"},
    
    "DEP11": {"nom": "Achats & Approvisionnements", "mdp": "DEP123", "type": "achats", "dept": "Achats & Approvisionnements"},
    "DEP12": {"nom": "Finance & Comptabilité", "mdp": "DEP123", "type": "finance", "dept": "Finance & Comptabilité"},
    "DEP13": {"nom": "Logistique & Stocks", "mdp": "DEP123", "type": "logistique", "dept": "Logistique & Stocks"},
    "DEP14": {"nom": "Juridique & Conformité", "mdp": "DEP123", "type": "juridique", "dept": "Juridique & Conformité"},
    
    "fondateur": {"nom": "Fondateur / Direction Générale", "mdp": "mboro2026", "type": "fondateur", "dept": "Direction Générale"}
}

# --- GESTION DE LA CONNEXION (SIDEBAR) ---
str_app.sidebar.title("🌾 Projet Agricole")
str_app.sidebar.markdown("---")

if 'user_connecte' not in str_app.session_state:
    str_app.session_state.user_connecte = None

if str_app.session_state.user_connecte is None:
    str_app.sidebar.subheader("Connexion Collaborateur")
    username = str_app.sidebar.text_input("Identifiant (ex: DEP1, DEP11, fondateur)")
    password = str_app.sidebar.text_input("Mot de passe", type="password")
    
    if str_app.sidebar.button("Se connecter"):
        if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
            str_app.session_state.user_connecte = username
            str_app.rerun()
        else:
            str_app.sidebar.error("Identifiant ou mot de passe incorrect.")
    str_app.stop()
else:
    infos_user = UTILISATEURS[str_app.session_state.user_connecte]
    str_app.sidebar.success(f"Connecté en tant que :\n**{infos_user['nom']}** ({str_app.session_state.user_connecte})")
    
    str_app.sidebar.markdown("---")
    if str_app.sidebar.button("🔄 Réinitialiser l'application (Reset)"):
        str_app.session_state.solde_restant = str_app.session_state.budget_global
        str_app.session_state.demandes = []
        str_app.session_state.cahiers_charges = {}
        str_app.success("Application réinitialisée à zéro !")
        str_app.rerun()

    if str_app.sidebar.button("Se déconnecter"):
        str_app.session_state.user_connecte = None
        str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")
str_app.markdown("---")

# ==========================================
# FONCTION COMMUNE : LES 3 MODULES DE BASE
# ==========================================
def afficher_trois_modules(nom_departement):
    str_app.info(f"Espace de travail du département **{nom_departement}**")
    
    tab1, tab2, tab3 = str_app.tabs([
        "1. Cahier des Charges & Projets", 
        "2. Expression des Besoins (Sans Montant)", 
        "3. Suivi & État des Demandes (Modifier ou Supprimer)"
    ])
    
    with tab1:
        str_app.subheader("Cahiers des charges et projets du département")
        with str_app.form(f"form_cc_{nom_departement}"):
            titre_doc = str_app.text_input("Intitulé / Titre du document")
            contenu_doc = str_app.text_area("Contenu du cahier des charges ou projet")
            submit_cc = str_app.form_submit_button("Enregistrer le document")
            
            if submit_cc:
                if titre_doc and contenu_doc:
                    if nom_departement not in str_app.session_state.cahiers_charges:
                        str_app.session_state.cahiers_charges[nom_departement] = []
                    str_app.session_state.cahiers_charges[nom_departement].append({"titre": titre_doc, "contenu": contenu_doc, "date": datetime.now().strftime("%Y-%m-%d")})
                    str_app.success(f"Document '{titre_doc}' enregistré !")
                else:
                    str_app.error("Veuillez renseigner un intitulé et un contenu.")
        
        str_app.markdown("---")
        if nom_departement in str_app.session_state.cahiers_charges and str_app.session_state.cahiers_charges[nom_departement]:
            for idx, doc in enumerate(str_app.session_state.cahiers_charges[nom_departement], 1):
                with str_app.expander(f"📁 Doc {idx} : {doc['titre']} (Date: {doc['date']})"):
                    str_app.write(doc['contenu'])
        else:
            str_app.info("Aucun cahier des charges rédigé pour l'instant.")

    with tab2:
        str_app.subheader("Exprimer un besoin / Soumettre une demande")
        with str_app.form(f"form_besoin_{nom_departement}"):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques détaillées")
            fournisseur_suggere = str_app.text_input("Fournisseur pressenti (optionnel)")
            
            submit_besoin = str_app.form_submit_button("Transmettre le besoin aux Achats")
            if submit_besoin:
                if titre_besoin and desc_besoin:
                    nouvelle_demande = {
                        "id": len(str_app.session_state.demandes) + 1,
                        "departement": nom_departement,
                        "titre": titre_besoin,
                        "cahier_charges": desc_besoin,
                        "montant": 0.0,
                        "fournisseur": fournisseur_suggere if fournisseur_suggere else "À sourcer",
                        "statut": "En attente Chiffrage & Sourcing Achats",
                        "etape_actuelle": "achats",
                        "avis_achats": "En attente",
                        "motif_achats": "",
                        "avis_finance": "En attente",
                        "motif_finance": "",
                        "avis_logistique": "En attente",
                        "motif_logistique": "",
                        "avis_juridique": "En attente",
                        "motif_juridique": "",
                        "contrat_juridique": "",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    str_app.session_state.demandes.append(nouvelle_demande)
                    str_app.success("Besoin transmis aux Achats avec succès !")
                    str_app.rerun()
                else:
                    str_app.error("Veuillez renseigner le titre et les spécifications.")

    with tab3:
        str_app.subheader("Suivi de vos demandes & Suppression / Modification")
        mes_demandes = [d for d in str_app.session_state.demandes if d["departement"] == nom_departement]
        if mes_demandes:
            df_mes_demandes = pd.DataFrame(mes_demandes)
            str_app.dataframe(df_mes_demandes[["id", "titre", "montant", "fournisseur", "statut", "date"]], use_container_width=True)
            
            str_app.markdown("---")
            str_app.markdown("### 🗑️ Supprimer une demande")
            for d in mes_demandes:
                col_a, col_b = str_app.columns([4, 1])
                col_a.write(f"**Demande #{d['id']}** : {d['titre']} (*{d['statut']}*)")
                if col_b.button(f"Supprimer #{d['id']}", key=f"del_{d['id']}"):
                    if d['etape_actuelle'] == "termine" and d['montant'] > 0:
                        str_app.session_state.solde_restant += d['montant']
                    str_app.session_state.demandes = [item for item in str_app.session_state.demandes if item['id'] != d['id']]
                    str_app.success(f"Demande #{d['id']} supprimée !")
                    str_app.rerun()
        else:
            str_app.info("Aucune demande enregistrée pour le moment.")


# ==========================================
# VUE GLOBALE DE SUIVI DES DEMANDES
# ==========================================
def afficher_suivi_global():
    str_app.markdown("---")
    with str_app.expander("📊 **Tableau de Suivi Global de TOUTES les Demandes**"):
        if str_app.session_state.demandes:
            df_global = pd.DataFrame(str_app.session_state.demandes)
            str_app.dataframe(df_global[["id", "departement", "titre", "montant", "fournisseur", "etape_actuelle", "statut", "date"]], use_container_width=True)
        else:
            str_app.info("Aucune demande enregistrée.")


# ==========================================
# GESTION DES AFFICHAGES SELON LE PROFIL
# ==========================================
if profil["type"] == "standard":
    afficher_trois_modules(nom_dept)

elif profil["type"] == "achats":
    str_app.subheader("🛒 Module de Sourcing & Chiffrage - Achats (DEP11)")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{str_app.session_state.budget_global:,.2f} €")
    col2.metric("Solde Restant", f"{str_app.session_state.solde_restant:,.2f} €")
    
    str_app.markdown("---")
    demandes_achats = [d for d in str_app.session_state.demandes if d["etape_actuelle"] == "achats" and d["avis_achats"] == "En attente"]
    
    if demandes_achats:
        for d in demandes_achats:
            with str_app.expander(f"Besoin #{d['id']} - {d['titre']} (Émis par : {d['departement']})"):
                str_app.write(f"**Spécifications :** {d['cahier_charges']}")
                with str_app.form(f"form_achats_{d['id']}"):
                    fournisseur_choisi = str_app.text_input("Fournisseur / prestataire")
                    montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                    action_achats = str_app.radio("Décision", ["Valider & Transmettre aux Contrôles", "Refuser & Bloquer", "Refuser & Demander Modification"], key=f"a_achats_{d['id']}")
                    motif = str_app.text_area("Motif (si refus/blocage)", key=f"m_achats_{d['id']}")
                    
                    if str_app.form_submit_button("Valider la décision"):
                        if action_achats == "Valider & Transmettre aux Contrôles":
                            if montant_chiffre > 0 and fournisseur_choisi:
                                d['fournisseur'] = fournisseur_choisi
                                d['montant'] = montant_chiffre
                                d['avis_achats'] = "Validé"
                                d['etape_actuelle'] = "controles"
                                d['statut'] = "En attente Contrôles Croisés"
                                str_app.rerun()
                            else:
                                str_app.error("Renseignez un fournisseur et un montant > 0.")
                        else:
                            d['avis_achats'] = "Refusé"
                            d['etape_actuelle'] = "bloque"
                            d['statut'] = f"Bloqué : {motif}"
                            str_app.rerun()
    else:
        str_app.info("Aucun besoin en attente aux Achats.")
    
    afficher_suivi_global()
    with str_app.expander("📂 Mes Cahiers des Charges (Achats)"):
        afficher_trois_modules(nom_dept)

elif profil["type"] == "finance":
    str_app.subheader("💰 Module de Contrôle - Finance & Comptabilité (DEP12)")
    col1, col2 = str_app.columns(2)
    col1.metric("Enveloppe Globale", f"{str_app.session_state.budget_global:,.2f} €")
    col2.metric("Trésorerie / Solde Actuel", f"{str_app.session_state.solde_restant:,.2f} €")
    
    str_app.markdown("---")
    demandes_finance = [d for d in str_app.session_state.demandes if d["etape_actuelle"] == "controles" and d["avis_finance"] == "En attente"]
    if demandes_finance:
        for d in demandes_finance:
            with str_app.expander(f"Demande #{d['id']} - {d['titre']} | {d['montant']} €"):
                with str_app.form(f"form_fin_{d['id']}"):
                    avis = str_app.radio("Avis", ["Valider budget", "Refuser"], key=f"a_fin_{d['id']}")
                    if str_app.form_submit_button("Valider"):
                        d['avis_finance'] = "Validé" if avis == "Valider budget" else "Refusé"
                        str_app.rerun()
    else:
        str_app.info("Aucune demande en attente financière.")
    afficher_suivi_global()

elif profil["type"] == "logistique":
    str_app.subheader("🚛 Logistique & Stocks (DEP13)")
    demandes_log = [d for d in str_app.session_state.demandes if d["etape_actuelle"] == "controles" and d["avis_logistique"] == "En attente"]
    if demandes_log:
        for d in demandes_log:
            with str_app.expander(f"Demande #{d['id']} - {d['titre']}"):
                with str_app.form(f"form_log_{d['id']}"):
                    avis = str_app.radio("Faisabilité", ["Valider", "Refuser"], key=f"a_log_{d['id']}")
                    if str_app.form_submit_button("Valider"):
                        d['avis_logistique'] = "Validé" if avis == "Valider" else "Refusé"
                        str_app.rerun()
    else:
        str_app.info("Aucune demande logistique en attente.")
    afficher_suivi_global()

elif profil["type"] == "juridique":
    str_app.subheader("⚖️ Juridique & Conformité (DEP14)")
    demandes_jur = [d for d in str_app.session_state.demandes if d["etape_actuelle"] == "controles" and d["avis_juridique"] == "En attente"]
    if demandes_jur:
        for d in demandes_jur:
            with str_app.expander(f"Demande #{d['id']} - {d['titre']}"):
                with str_app.form(f"form_jur_{d['id']}"):
                    termes = str_app.text_area("Termes du contrat", value=d['contrat_juridique'])
                    if str_app.form_submit_button("Valider contrat & Transmettre au Fondateur"):
                        d['contrat_juridique'] = termes
                        d['avis_juridique'] = "Validé"
                        if d['avis_finance'] == "Validé" and d['avis_logistique'] == "Validé":
                            d['etape_actuelle'] = "fondateur"
                            d['statut'] = "Prêt pour Signature Finale"
                        str_app.rerun()
    else:
        str_app.info("Aucune demande juridique en attente.")
    afficher_suivi_global()

elif profil["type"] == "fondateur":
    str_app.subheader("⭐ Bureau du Fondateur - Signature Exécutive")
    col1, col2 = str_app.columns(2)
    col1.metric("Enveloppe Globale", f"{str_app.session_state.budget_global:,.2f} €")
    col2.metric("Solde Disponible", f"{str_app.session_state.solde_restant:,.2f} €")
    
    str_app.markdown("---")
    demandes_fondateur = [d for d in str_app.session_state.demandes if d["etape_actuelle"] == "fondateur"]
    if demandes_fondateur:
        for d in demandes_fondateur:
            with str_app.expander(f"Dossier #{d['id']} - {d['titre']} | {d['montant']} €"):
                str_app.write(f"📜 **Contrat :** {d['contrat_juridique']}")
                if str_app.button(f"Signer et Décaisser #{d['id']}", key=f"btn_sign_{d['id']}"):
                    if str_app.session_state.solde_restant >= d['montant']:
                        str_app.session_state.solde_restant -= d['montant']
                        d['etape_actuelle'] = "termine"
                        d['statut'] = "Signé & Exécuté par le Fondateur"
                        str_app.success("Décaissé avec succès !")
                        str_app.rerun()
                    else:
                        str_app.error("Solde insuffisant.")
    else:
        str_app.info("Aucun dossier en attente de signature.")
    afficher_suivi_global()
