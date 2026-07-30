import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Bureau d'Études - Gestion & Validation",
    page_icon="🏢",
    layout="wide"
)

# --- ACTUALISATION AUTOMATIQUE (Toutes les 5 secondes) ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA MÉMOIRE PARTAGÉE GLOBALE ---
if 'global_store' not in str_app.session_state:
    str_app.session_state.global_store = {
        "budget_global": 10000000.0,
        "solde_restant": 10000000.0,
        "demandes": [],
        "cahiers_charges": {}, 
        "messages_coordination": [] 
    }

store = str_app.session_state.global_store

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
    "fondateur": {"nom": "Fondateur / Direction Générale", "mdp": "mboro2026", "type": "fondateur", "dept": "Direction Générale"}
}

# --- GESTION DE LA CONNEXION (SIDEBAR) ---
str_app.sidebar.title("🏢 Bureau d'Études")
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
        store["solde_restant"] = store["budget_global"]
        store["demandes"] = []
        store["cahiers_charges"] = {}
        store["messages_coordination"] = []
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
# ESPACE DE COORDINATION PARTAGÉ (Commun à tous)
# ==========================================
def afficher_espace_coordination(nom_departement):
    with str_app.expander("💬 **Espace de Notes & Réunions de Coordination (Partagé)**"):
        str_app.write("Échangez ici vos mémos, consignes et points de coordination visibles par tous les départements en temps réel.")
        
        with str_app.form(f"form_coord_{nom_departement}"):
            texte_msg = str_app.text_input("Votre message / note de coordination")
            submit_msg = str_app.form_submit_button("Publier le message")
            if submit_msg:
                if texte_msg:
                    store["messages_coordination"].append({
                        "auteur": nom_departement,
                        "texte": texte_msg,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    str_app.success("Message publié !")
                    str_app.rerun()
                else:
                    str_app.error("Le message ne peut pas être vide.")
        
        str_app.markdown("---")
        if store["messages_coordination"]:
            for m in reversed(store["messages_coordination"]):
                str_app.markdown(f"> **[{m['date']}] {m['auteur']}** : {m['texte']}")
        else:
            str_app.info("Aucun message de coordination pour le moment.")


# ==========================================
# FONCTION COMMUNE : LES 3 MODULES DE BASE
# ==========================================
def afficher_trois_modules(nom_departement):
    str_app.info(f"Espace de travail du département **{nom_departement}**")
    
    tab1, tab2, tab3 = str_app.tabs([
        "1. Cahiers des Charges & Projets (Avis & Partage)", 
        "2. Expression des Besoins (Sans Montant)", 
        "3. Suivi & État des Demandes (Suppression)"
    ])
    
    liste_tous_depts = [u["dept"] for u in UTILISATEURS.values()]

    with tab1:
        str_app.subheader("Rédiger et partager un document / projet")
        with str_app.form(f"form_cc_{nom_departement}"):
            titre_doc = str_app.text_input("Intitulé / Titre du document")
            contenu_doc = str_app.text_area("Contenu du cahier des charges ou projet")
            destinataire_avis = str_app.selectbox("Soumettre pour avis / Partager avec :", ["Aucun (Interne au département)"] + liste_tous_depts)
            
            submit_cc = str_app.form_submit_button("Enregistrer le document")
            
            if submit_cc:
                if titre_doc and contenu_doc:
                    if nom_departement not in store["cahiers_charges"]:
                        store["cahiers_charges"][nom_departement] = []
                    
                    doc_id = len(store["cahiers_charges"][nom_departement]) + 1
                    store["cahiers_charges"][nom_departement].append({
                        "id": doc_id,
                        "titre": titre_doc, 
                        "contenu": contenu_doc, 
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "destinataire_avis": destinataire_avis
                    })
                    str_app.success(f"Document '{titre_doc}' enregistré et partagé si demandé !")
                    str_app.rerun()
                else:
                    str_app.error("Veuillez renseigner un intitulé et un contenu.")
        
        str_app.markdown("---")
        str_app.markdown("### 📁 Mes documents enregistrés")
        if nom_departement in store["cahiers_charges"] and store["cahiers_charges"][nom_departement]:
            for idx, doc in enumerate(store["cahiers_charges"][nom_departement]):
                col1, col2 = str_app.columns([5, 1])
                with col1:
                    with str_app.expander(f"Doc #{doc.get('id', idx+1)} : {doc['titre']} (Partagé avec : {doc.get('destinataire_avis', 'Interne')})"):
                        str_app.write(doc['contenu'])
                with col2:
                    if str_app.button(f"Supprimer", key=f"del_cc_{nom_departement}_{idx}"):
                        store["cahiers_charges"][nom_departement].pop(idx)
                        str_app.success("Document supprimé !")
                        str_app.rerun()
        else:
            str_app.info("Aucun document rédigé par votre département pour l'instant.")

        str_app.markdown("---")
        str_app.markdown("### 📥 Documents reçus des autres départements pour avis")
        documents_recus = []
        for d_nom, liste_docs in store["cahiers_charges"].items():
            if d_nom != nom_departement:
                for doc in liste_docs:
                    if doc.get("destinataire_avis") == nom_departement:
                        documents_recus.append((d_nom, doc))
        
        if documents_recus:
            for d_expediteur, doc in documents_recus:
                with str_app.expander(f"📬 De [{d_expediteur}] : {doc['titre']} (Date: {doc['date']})"):
                    str_app.write(doc['contenu'])
        else:
            str_app.info("Aucun document partagé pour avis à votre intention.")

    with tab2:
        str_app.subheader("Exprimer un besoin / Soumettre une demande d'achat")
        with str_app.form(f"form_besoin_{nom_departement}"):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques détaillées")
            fournisseur_suggere = str_app.text_input("Fournisseur pressenti (optionnel)")
            
            submit_besoin = str_app.form_submit_button("Transmettre le besoin aux Achats")
            if submit_besoin:
                if titre_besoin and desc_besoin:
                    nouvelle_demande = {
                        "id": len(store["demandes"]) + 1,
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
                        "contrat_juridique": "",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    store["demandes"].append(nouvelle_demande)
                    str_app.success("Besoin transmis aux Achats avec succès !")
                    str_app.rerun()
                else:
                    str_app.error("Veuillez renseigner le titre et les spécifications.")

    with tab3:
        str_app.subheader("Suivi de vos demandes & Suppression")
        mes_demandes = [d for d in store["demandes"] if d["departement"] == nom_departement]
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
                        store["solde_restant"] += d['montant']
                    store["demandes"] = [item for item in store["demandes"] if item['id'] != d['id']]
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
        if store["demandes"]:
            df_global = pd.DataFrame(store["demandes"])
            str_app.dataframe(df_global[["id", "departement", "titre", "montant", "fournisseur", "etape_actuelle", "statut", "date"]], use_container_width=True)
        else:
            str_app.info("Aucune demande enregistrée.")


# ==========================================
# GESTION DES AFFICHAGES SELON LE PROFIL
# ==========================================
if profil["type"] == "standard":
    afficher_trois_modules(nom_dept)
    str_app.markdown("---")
    afficher_espace_coordination(nom_dept)

elif profil["type"] == "achats":
    str_app.subheader("🛒 Module de Sourcing & Chiffrage - Achats (DEP11)")
    
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{store['budget_global']:,.2f} €")
    col2.metric("Solde Restant", f"{store['solde_restant']:,.2f} €")
    
    str_app.markdown("---")
    demandes_achats = [d for d in store["demandes"] if d["etape_actuelle"] == "achats" and d["avis_achats"] == "En attente"]
    
    if demandes_achats:
        for d in demandes_achats:
            with str_app.expander(f"Besoin #{d['id']} - {d['titre']} (Émis par : {d['departement']})"):
                str_app.write(f"**Spécifications :** {d['cahier_charges']}")
                with str_app.form(f"form_achats_{d['id']}"):
                    fournisseur_choisi = str_app.text_input("Fournisseur / prestataire")
                    montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                    action_achats = str_app.radio("Décision", ["Valider & Transmettre à la Finance", "Refuser & Bloquer"], key=f"a_achats_{d['id']}")
                    motif = str_app.text_area("Motif (si refus/blocage)", key=f"m_achats_{d['id']}")
                    
                    if str_app.form_submit_button("Valider la décision"):
                        if action_achats == "Valider & Transmettre à la Finance":
                            if montant_chiffre > 0 and fournisseur_choisi:
                                d['fournisseur'] = fournisseur_choisi
                                d['montant'] = montant_chiffre
                                d['avis_achats'] = "Validé"
                                d['etape_actuelle'] = "finance"
                                d['statut'] = "En attente Validation Financière"
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
    str_app.markdown("---")
    afficher_espace_coordination(nom_dept)
    str_app.markdown("---")
    with str_app.expander("📂 Mes Cahiers des Charges & Projets (Achats)"):
        afficher_trois_modules(nom_dept)

elif profil["type"] == "finance":
    str_app.subheader("💰 Module de Contrôle - Finance & Comptabilité (DEP12)")
    
    col1, col2 = str_app.columns(2)
    col1.metric("Enveloppe Globale", f"{store['budget_global']:,.2f} €")
    col2.metric("Trésorerie / Solde Actuel", f"{store['solde_restant']:,.2f} €")
    
    str_app.markdown("---")
    demandes_finance = [d for d in store["demandes"] if d["etape_actuelle"] == "finance" and d["avis_finance"] == "En attente"]
    if demandes_finance:
        for d in demandes_finance:
            with str_app.expander(f"Demande #{d['id']} - {d['titre']} | {d['montant']} € (Émis par : {d['departement']})"):
                with str_app.form(f"form_fin_{d['id']}"):
                    avis = str_app.radio("Avis", ["Valider budget & Transmettre au Fondateur", "Refuser"], key=f"a_fin_{d['id']}")
                    motif_fin = str_app.text_area("Motif (si refus)", key=f"m_fin_{d['id']}")
                    if str_app.form_submit_button("Valider la décision"):
                        if avis == "Valider budget & Transmettre au Fondateur":
                            d['avis_finance'] = "Validé"
                            d['etape_actuelle'] = "fondateur"
                            d['statut'] = "Prêt pour Signature Finale"
                            str_app.rerun()
                        else:
                            d['avis_finance'] = "Refusé"
                            d['etape_actuelle'] = "bloque"
                            d['statut'] = f"Refusé par Finance : {motif_fin}"
                            str_app.rerun()
    else:
        str_app.info("Aucune demande en attente financière.")
    
    afficher_suivi_global()
    str_app.markdown("---")
    afficher_espace_coordination(nom_dept)
    str_app.markdown("---")
    with str_app.expander("📂 Mes Cahiers des Charges & Projets (Finance)"):
        afficher_trois_modules(nom_dept)

elif profil["type"] == "fondateur":
    str_app.subheader("⭐ Bureau du Fondateur - Signature Exécutive & Vue Panoramique")
    
    col1, col2 = str_app.columns(2)
    col1.metric("Enveloppe Globale", f"{store['budget_global']:,.2f} €")
    col2.metric("Solde Disponible", f"{store['solde_restant']:,.2f} €")
    
    str_app.markdown("---")
    demandes_fondateur = [d for d in store["demandes"] if d["etape_actuelle"] == "fondateur"]
    if demandes_fondateur:
        for d in demandes_fondateur:
            with str_app.expander(f"Dossier #{d['id']} - {d['titre']} | {d['montant']} € (Département : {d['departement']})"):
                str_app.write(f"🛒 **Fournisseur :** {d['fournisseur']}")
                str_app.write(f"📜 **Spécifications :** {d['cahier_charges']}")
                if str_app.button(f"Signer et Décaisser #{d['id']}", key=f"btn_sign_{d['id']}"):
                    if store['solde_restant'] >= d['montant']:
                        store['solde_restant'] -= d['montant']
                        d['etape_actuelle'] = "termine"
                        d['statut'] = "Signé & Exécuté par le Fondateur"
                        str_app.success("Décaissé avec succès !")
                        str_app.rerun()
                    else:
                        str_app.error("Solde insuffisant.")
    else:
        str_app.info("Aucun dossier en attente de signature.")
    
    afficher_suivi_global()
    
    str_app.markdown("---")
    with str_app.expander("👁️ **Vue Panoramique de TOUS les Cahiers des Charges (Accès Fondateur)**"):
        if store["cahiers_charges"]:
            for d_nom, liste_docs in store["cahiers_charges"].items():
                str_app.markdown(f"#### Département : {d_nom}")
                for doc in liste_docs:
                    str_app.write(f"- **{doc['titre']}** (Date : {doc['date']}) | Partagé avec : {doc.get('destinataire_avis', 'Interne')}")
                    str_app.caption(doc['contenu'])
        else:
            str_app.info("Aucun cahier des charges enregistré pour le moment dans l'entreprise.")

    str_app.markdown("---")
    afficher_espace_coordination(nom_dept)
    str_app.markdown("---")
    with str_app.expander("📂 Mes Cahiers des Charges & Projets (Fondateur)"):
        afficher_trois_modules(nom_dept)
