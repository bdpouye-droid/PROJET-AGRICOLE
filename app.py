import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from io import BytesIO
from fpdf import FPDF

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Bureau d'Études - Gestion & Validation",
    page_icon="🏢",
    layout="wide"
)

# --- ACTUALISATION AUTOMATIQUE ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA MÉMOIRE PARTAGÉE GLOBALE ---
if 'global_store' not in str_app.session_state:
    str_app.session_state.global_store = {
        "budget_global": 10000000.0,
        "solde_restant": 10000000.0,
        "demandes": [],
        "cahiers_charges": {}, 
        "messages_coordination": [],
        "logs_audit": []
    }

store = str_app.session_state.global_store

def ajouter_log(action, acteur, details):
    store["logs_audit"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "acteur": acteur,
        "action": action,
        "details": details
    })

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
try:
    str_app.sidebar.image("logo.png", use_container_width=True)
except Exception:
    pass

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
            ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
            str_app.rerun()
        else:
            str_app.sidebar.error("Identifiant ou mot de passe incorrect.")
    str_app.stop()
else:
    infos_user = UTILISATEURS[str_app.session_state.user_connecte]
    str_app.sidebar.success(f"Connecté en tant que :\n**{infos_user['nom']}**")
    str_app.sidebar.markdown("---")
    
    if str_app.sidebar.button("🔄 Réinitialiser l'application (Reset)"):
        store["solde_restant"] = store["budget_global"]
        store["demandes"] = []
        store["cahiers_charges"] = {}
        store["messages_coordination"] = []
        store["logs_audit"] = []
        ajouter_log("Réinitialisation", infos_user['nom'], "Base de données remise à zéro")
        str_app.success("Application réinitialisée à zéro !")
        str_app.rerun()

    if str_app.sidebar.button("Se déconnecter"):
        ajouter_log("Déconnexion", infos_user['nom'], "Déconnexion de l'utilisateur")
        str_app.session_state.user_connecte = None
        str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")
str_app.markdown("---")


# --- FONCTION PDF CORRIGÉE ---
def generer_pdf(titre, texte_contenu, infos_complementaires=""):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 14)
    pdf.multi_cell(0, 8, txt=titre, align="C")
    pdf.ln(5)
    
    if infos_complementaires:
        pdf.set_font("Arial", "I", 11)
        pdf.multi_cell(0, 6, txt=infos_complementaires)
        pdf.ln(8)
        
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, txt=texte_contenu)
    
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin1', 'replace')
        
    return BytesIO(pdf_bytes)


# ==========================================
# ESPACE DE COORDINATION PARTAGÉ
# ==========================================
def afficher_espace_coordination(nom_departement):
    with str_app.expander("💬 **Espace de Notes & Réunions de Coordination (Partagé)**"):
        with str_app.form(f"form_coord_{nom_departement}", clear_on_submit=True):
            texte_msg = str_app.text_input("Votre message / note de coordination")
            submit_msg = str_app.form_submit_button("Publier le message")
            if submit_msg and texte_msg:
                store["messages_coordination"].append({
                    "auteur": nom_departement,
                    "texte": texte_msg,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                str_app.rerun()
        
        if store["messages_coordination"]:
            for m in reversed(store["messages_coordination"]):
                str_app.markdown(f"> **[{m['date']}] {m['auteur']}** : {m['texte']}")


# ==========================================
# VUE GLOBALE ET LISIBLE DES DEMANDES
# ==========================================
def afficher_suivi_global():
    str_app.markdown("---")
    with str_app.expander("📊 **Tableau de Suivi Global de TOUTES les Demandes**"):
        if store["demandes"]:
            df_global = pd.DataFrame(store["demandes"])
            str_app.dataframe(
                df_global[["id", "departement", "titre", "montant", "fournisseur", "statut", "date"]], 
                use_container_width=True,
                column_config={
                    "statut": str_app.column_config.TextColumn("Statut Actuel", width="large"),
                    "titre": str_app.column_config.TextColumn("Titre de la demande", width="medium"),
                    "fournisseur": str_app.column_config.TextColumn("Fournisseur", width="medium")
                }
            )
        else:
            str_app.info("Aucune demande enregistrée.")


# ==========================================
# MODULES : DEPARTEMENTS STANDARDS
# ==========================================
def afficher_trois_modules(nom_departement):
    tab1, tab2, tab3 = str_app.tabs([
        "1. Cahiers des Charges (Avis & Partage)", 
        "2. Expression des Besoins", 
        "3. Suivi & État de mes demandes"
    ])
    
    liste_tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with tab1:
        str_app.subheader("Rédiger et partager un cahier des charges")
        with str_app.form(f"form_cc_{nom_departement}", clear_on_submit=True):
            titre_doc = str_app.text_input("Intitulé / Titre du document")
            contenu_doc = str_app.text_area("Contenu détaillé")
            destinataires_avis = str_app.multiselect("Partager avec (plusieurs choix possibles) :", liste_tous_depts)
            
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
                        "destinataires_avis": destinataires_avis
                    })
                    ajouter_log("Création Cahier des Charges", nom_departement, f"Titre: {titre_doc}")
                    str_app.success(f"Document enregistré et partagé avec {len(destinataires_avis)} département(s) !")
                    str_app.rerun()
        
        str_app.markdown("### 📁 Mes documents")
        if nom_departement in store["cahiers_charges"] and store["cahiers_charges"][nom_departement]:
            for idx, doc in enumerate(store["cahiers_charges"][nom_departement]):
                partages = ", ".join(doc.get('destinataires_avis', [])) if doc.get('destinataires_avis') else "Interne"
                with str_app.expander(f"Doc #{doc.get('id', idx+1)} : {doc['titre']} (Partagé avec : {partages})"):
                    str_app.write(doc['contenu'])
                    pdf_io = generer_pdf(f"Cahier des Charges\n{doc['titre']}", doc['contenu'], f"Département: {nom_departement}\nDate: {doc['date']}")
                    colA, colB = str_app.columns([1,1])
                    colA.download_button("📥 PDF", data=pdf_io, file_name=f"cc_{doc['id']}.pdf", mime="application/pdf", key=f"pdf_{nom_departement}_{idx}")
                    if colB.button("🗑️ Supprimer", key=f"del_cc_{nom_departement}_{idx}"):
                        store["cahiers_charges"][nom_departement].pop(idx)
                        str_app.rerun()

        str_app.markdown("### 📥 Documents reçus pour avis")
        for d_nom, liste_docs in store["cahiers_charges"].items():
            if d_nom != nom_departement:
                for doc in liste_docs:
                    if nom_departement in doc.get("destinataires_avis", []):
                        with str_app.expander(f"📬 De [{d_nom}] : {doc['titre']}"):
                            str_app.write(doc['contenu'])
                            pdf_recu = generer_pdf(f"{doc['titre']}", doc['contenu'], f"Émetteur: {d_nom}")
                            str_app.download_button("📥 PDF", data=pdf_recu, file_name=f"recu_{doc['id']}.pdf", mime="application/pdf", key=f"recu_{d_nom}_{doc['id']}")

    with tab2:
        str_app.subheader("Exprimer un besoin / Demande d'achat")
        with str_app.form(f"form_besoin_{nom_departement}", clear_on_submit=True):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques")
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
                        "statut": "En attente Achats",
                        "etape_actuelle": "achats",
                        "avis_achats": "En attente",
                        "avis_finance": "En attente",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    store["demandes"].append(nouvelle_demande)
                    ajouter_log("Nouvelle Demande", nom_departement, f"ID {nouvelle_demande['id']} - {titre_besoin}")
                    str_app.success("Besoin transmis avec succès ! Le formulaire a été réinitialisé.")
                    str_app.rerun()

    with tab3:
        str_app.subheader("Suivi de vos demandes")
        mes_demandes = [d for d in store["demandes"] if d["departement"] == nom_departement]
        if mes_demandes:
            df_mes_demandes = pd.DataFrame(mes_demandes)
            str_app.dataframe(df_mes_demandes[["id", "titre", "statut", "date"]], use_container_width=True)
        else:
            str_app.info("Aucune demande en cours.")

# ==========================================
# GESTION DES AFFICHAGES SELON LE PROFIL
# ==========================================

if profil["type"] == "standard":
    afficher_trois_modules(nom_dept)
    str_app.markdown("---")
    afficher_espace_coordination(nom_dept)

elif profil["type"] == "achats":
    str_app.subheader("🛒 Achats - Sourcing & Chiffrage")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{store['budget_global']:,.2f} €")
    col2.metric("Solde Restant", f"{store['solde_restant']:,.2f} €")
    
    str_app.markdown("---")
    demandes_achats = [d for d in store["demandes"] if d["etape_actuelle"] == "achats" and d["avis_achats"] == "En attente"]
    
    if demandes_achats:
        for d in demandes_achats:
            with str_app.expander(f"Besoin #{d['id']} - {d['titre']} (Par : {d['departement']})"):
                str_app.write(f"**Spécifications :** {d['cahier_charges']}")
                str_app.info(f"💡 **Fournisseur pressenti par le demandeur :** {d['fournisseur']}")
                
                with str_app.form(f"form_achats_{d['id']}"):
                    fournisseur_choisi = str_app.text_input("Confirmer ou modifier le fournisseur", value=d['fournisseur'] if d['fournisseur'] != "À sourcer" else "")
                    montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                    action_achats = str_app.radio("Décision", ["Valider & Transmettre Finance", "Refuser"], key=f"a_achats_{d['id']}")
                    
                    if str_app.form_submit_button("Valider la décision"):
                        if action_achats == "Valider & Transmettre Finance" and montant_chiffre > 0:
                            d['fournisseur'] = fournisseur_choisi
                            d['montant'] = montant_chiffre
                            d['avis_achats'] = "Validé"
                            d['etape_actuelle'] = "finance"
                            d['statut'] = "En attente Finance"
                            ajouter_log("Validation Achats", "Achats", f"Demande #{d['id']} chiffrée à {montant_chiffre}€ chez {fournisseur_choisi}")
                            str_app.rerun()
                        elif action_achats == "Refuser":
                            d['avis_achats'] = "Refusé"
                            d['etape_actuelle'] = "bloque"
                            d['statut'] = "Refusé par les Achats"
                            ajouter_log("Refus Achats", "Achats", f"Demande #{d['id']} refusée.")
                            str_app.rerun()
    else:
        str_app.info("Aucun besoin en attente de chiffrage.")
    
    afficher_suivi_global()
    afficher_espace_coordination(nom_dept)

elif profil["type"] == "finance":
    str_app.subheader("💰 Finance - Contrôle Budgétaire")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{store['budget_global']:,.2f} €")
    col2.metric("Solde Actuel", f"{store['solde_restant']:,.2f} €")
    
    demandes_finance = [d for d in store["demandes"] if d["etape_actuelle"] == "finance" and d["avis_finance"] == "En attente"]
    if demandes_finance:
        for d in demandes_finance:
            with str_app.expander(f"Demande #{d['id']} - {d['titre']} | {d['montant']} € (Par : {d['departement']})"):
                with str_app.form(f"form_fin_{d['id']}"):
                    avis = str_app.radio("Avis Financier", ["Valider & Transmettre Fondateur", "Refuser"])
                    if str_app.form_submit_button("Valider la décision"):
                        if avis == "Valider & Transmettre Fondateur":
                            d['avis_finance'] = "Validé"
                            d['etape_actuelle'] = "fondateur"
                            d['statut'] = "Prêt pour Signature Finale"
                            ajouter_log("Validation Finance", "Finance", f"Budget validé pour la demande #{d['id']}")
                            str_app.rerun()
                        else:
                            d['avis_finance'] = "Refusé"
                            d['etape_actuelle'] = "bloque"
                            d['statut'] = "Refusé par la Finance"
                            ajouter_log("Refus Finance", "Finance", f"Demande #{d['id']} refusée.")
                            str_app.rerun()
    afficher_suivi_global()
    afficher_espace_coordination(nom_dept)
    
    with str_app.expander("📖 Journal d'Audit & Traçabilité (Logs)"):
        str_app.dataframe(pd.DataFrame(store["logs_audit"]), use_container_width=True)

elif profil["type"] == "fondateur":
    str_app.subheader("⭐ Bureau du Fondateur - Signature Exécutive")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{store['budget_global']:,.2f} €")
    col2.metric("Solde Disponible", f"{store['solde_restant']:,.2f} €")
    
    demandes_fondateur = [d for d in store["demandes"] if d["etape_actuelle"] == "fondateur"]
    if demandes_fondateur:
        for d in demandes_fondateur:
            with str_app.expander(f"Dossier #{d['id']} - {d['titre']} | {d['montant']} € ({d['departement']})"):
                str_app.write(f"🛒 **Fournisseur :** {d['fournisseur']}")
                if str_app.button(f"Signer et Décaisser #{d['id']}", key=f"btn_sign_{d['id']}"):
                    if store['solde_restant'] >= d['montant']:
                        store['solde_restant'] -= d['montant']
                        d['etape_actuelle'] = "termine"
                        d['statut'] = "Signé & Exécuté par le Fondateur"
                        ajouter_log("Signature Fondateur", "Fondateur", f"Décaissement de {d['montant']}€ pour la demande #{d['id']}")
                        str_app.success("Décaissé avec succès !")
                        str_app.rerun()
    else:
        str_app.info("Aucun dossier en attente de signature.")
    
    afficher_suivi_global()
    
    with str_app.expander("📖 Journal d'Audit & Traçabilité Financière (Logs)"):
        if store["logs_audit"]:
            str_app.dataframe(pd.DataFrame(store["logs_audit"]), use_container_width=True)
        else:
            str_app.write("Aucune activité enregistrée.")
    
    afficher_espace_coordination(nom_dept)
