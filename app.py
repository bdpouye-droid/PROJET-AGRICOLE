import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from io import BytesIO
from fpdf import FPDF
import sqlite3
import json

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Bureau d'Études - Gestion & Validation",
    page_icon="🏢",
    layout="wide"
)

# --- ACTUALISATION AUTOMATIQUE ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA BASE DE DONNÉES SQLITE ---
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Table pour les variables globales (budget, solde)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_store (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Table pour les demandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            cahier_charges TEXT,
            montant REAL,
            fournisseur TEXT,
            statut TEXT,
            etape_actuelle TEXT,
            avis_achats TEXT,
            avis_finance TEXT,
            motif_refus TEXT,
            date TEXT
        )
    ''')
    
    # Table pour les cahiers des charges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cahiers_charges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            contenu TEXT,
            date TEXT,
            destinataires_avis TEXT
        )
    ''')
    
    # Table pour les messages de coordination
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_coordination (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur TEXT,
            texte TEXT,
            date TEXT
        )
    ''')
    
    # Table pour les journaux de bord
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journaux_bord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            texte TEXT,
            auteur TEXT,
            date TEXT
        )
    ''')
    
    # Table pour les logs d'audit
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            acteur TEXT,
            action TEXT,
            details TEXT
        )
    ''')
    
    # Initialiser les valeurs globales par défaut si elles n'existent pas
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))
    
    conn.commit()
    conn.close()

init_db()

# Fonctions d'accès à la base de données
def get_db_connection():
    return sqlite3.connect("database.db", check_same_thread=False)

def get_valeur_globale(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_store WHERE key = ?", (key,))
    val = cursor.fetchone()
    conn.close()
    return float(val[0]) if val else 0.0

def set_valeur_globale(key, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_store (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

def ajouter_log(action, acteur, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs_audit (date, acteur, action, details) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acteur, action, details)
    )
    conn.commit()
    conn.close()

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
    
    # RESTRICTION : Le bouton Reset n'apparaît que pour le Fondateur
    if str_app.session_state.user_connecte == "fondateur":
        if str_app.sidebar.button("🔄 Réinitialiser l'application (Reset)"):
            budget_init = get_valeur_globale("budget_global")
            set_valeur_globale("solde_restant", budget_init)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM demandes")
            cursor.execute("DELETE FROM cahiers_charges")
            cursor.execute("DELETE FROM messages_coordination")
            cursor.execute("DELETE FROM journaux_bord")
            cursor.execute("DELETE FROM logs_audit")
            conn.commit()
            conn.close()
            
            ajouter_log("Réinitialisation", infos_user['nom'], "Base de données remise à zéro")
            str_app.success("Application réinitialisée à zéro !")
            str_app.rerun()
        str_app.sidebar.markdown("---")

    if str_app.sidebar.button("Se déconnecter"):
        ajouter_log("Déconnexion", infos_user['nom'], "Déconnexion de l'utilisateur")
        str_app.session_state.user_connecte = None
        str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")
str_app.markdown("---")


# --- FONCTION PDF ---
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
# ESPACE DE COORDINATION & JOURNAL DE BORD PERSONNEL
# ==========================================
def afficher_espace_coordination_et_journal(nom_departement):
    with str_app.expander("💬 **Espace de Notes & Réunions de Coordination (Partagé)**"):
        with str_app.form(f"form_coord_{nom_departement}", clear_on_submit=True):
            texte_msg = str_app.text_input("Votre message / note de coordination")
            submit_msg = str_app.form_submit_button("Publier le message")
            if submit_msg and texte_msg:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages_coordination (auteur, texte, date) VALUES (?, ?, ?)",
                    (nom_departement, texte_msg, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                conn.close()
                str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auteur, texte, date FROM messages_coordination ORDER BY id DESC")
        messages = cursor.fetchall()
        conn.close()
        
        if messages:
            for m in messages:
                str_app.markdown(f"> **[{m[2]}] {m[0]}** : {m[1]}")

    with str_app.expander(f"📔 **Journal de Bord Quotidien ({nom_departement})**"):
        str_app.write("Consignez ici vos notes, avancements et points quotidiens au jour le jour.")
        with str_app.form(f"form_journal_{nom_departement}", clear_on_submit=True):
            titre_j = str_app.text_input("Titre de l'entrée du jour")
            texte_j = str_app.text_area("Contenu / Notes du journal")
            submit_j = str_app.form_submit_button("Ajouter au journal")
            
            if submit_j and titre_j and texte_j:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO journaux_bord (departement, titre, texte, auteur, date) VALUES (?, ?, ?, ?, ?)",
                    (nom_departement, titre_j, texte_j, nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"))
                )
                conn.commit()
                conn.close()
                str_app.success("Entrée enregistrée dans votre journal de bord !")
                str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, texte, date FROM journaux_bord WHERE departement = ? ORDER BY id DESC", (nom_departement,))
        journaux = cursor.fetchall()
        conn.close()
        
        if journaux:
            str_app.markdown("### Historique de votre journal :")
            for entree in journaux:
                str_app.markdown(f"**[{entree[2]}] {entree[0]}**\n\n{entree[1]}\n\n---")
        else:
            str_app.info("Aucune entrée dans votre journal de bord pour le moment.")


# ==========================================
# VUE GLOBALE ET LISIBLE DES DEMANDES
# ==========================================
def afficher_suivi_global():
    str_app.markdown("---")
    with str_app.expander("📊 **Tableau de Suivi Global de TOUTES les Demandes**"):
        conn = get_db_connection()
        df_global = pd.read_sql_query("SELECT id, departement, titre, montant, fournisseur, statut, date FROM demandes", conn)
        conn.close()
        
        if not df_global.empty:
            str_app.dataframe(
                df_global, 
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
# MODULES : CAHIERS DES CHARGES
# ==========================================
def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("Rédiger et partager un cahier des charges")
    liste_tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with str_app.form(f"form_cc_{nom_departement}", clear_on_submit=True):
        titre_doc = str_app.text_input("Intitulé / Titre du document")
        contenu_doc = str_app.text_area("Contenu détaillé")
        destinataires_avis = str_app.multiselect("Partager avec (plusieurs choix possibles) :", liste_tous_depts)
        
        submit_cc = str_app.form_submit_button("Enregistrer le document")
        
        if submit_cc:
            if titre_doc and contenu_doc:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, ?)",
                    (nom_departement, titre_doc, contenu_doc, datetime.now().strftime("%Y-%m-%d"), json.dumps(destinataires_avis))
                )
                conn.commit()
                conn.close()
                
                ajouter_log("Création Cahier des Charges", nom_departement, f"Titre: {titre_doc}")
                str_app.success(f"Document enregistré et partagé avec {len(destinataires_avis)} département(s) !")
                str_app.rerun()
    
    str_app.markdown("### 📁 Mes documents")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement = ?", (nom_departement,))
    mes_docs = cursor.fetchall()
    conn.close()
    
    if mes_docs:
        for idx, doc in enumerate(mes_docs):
            doc_id, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
            destinataires = json.loads(doc_dest_json) if doc_dest_json else []
            partages = ", ".join(destinataires) if destinataires else "Interne"
            
            with str_app.expander(f"Doc #{doc_id} : {doc_titre} (Partagé avec : {partages})"):
                str_app.write(doc_contenu)
                pdf_io = generer_pdf(f"Cahier des Charges\n{doc_titre}", doc_contenu, f"Département: {nom_departement}\nDate: {doc_date}")
                colA, colB = str_app.columns([1,1])
                colA.download_button("📥 PDF", data=pdf_io, file_name=f"cc_{doc_id}.pdf", mime="application/pdf", key=f"pdf_{nom_departement}_{doc_id}")
                if colB.button("🗑️ Supprimer", key=f"del_cc_{nom_departement}_{doc_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (doc_id,))
                    conn.commit()
                    conn.close()
                    str_app.rerun()

    str_app.markdown("### 📥 Documents reçus pour avis")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement != ?", (nom_departement,))
    autres_docs = cursor.fetchall()
    conn.close()
    
    for doc in autres_docs:
        doc_id, d_nom, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
        destinataires = json.loads(doc_dest_json) if doc_dest_json else []
        if nom_departement in destinataires:
            with str_app.expander(f"📬 De [{d_nom}] : {doc_titre}"):
                str_app.write(doc_contenu)
                pdf_recu = generer_pdf(f"{doc_titre}", doc_contenu, f"Émetteur: {d_nom}")
                str_app.download_button("📥 PDF", data=pdf_recu, file_name=f"recu_{doc_id}.pdf", mime="application/pdf", key=f"recu_{d_nom}_{doc_id}")


# ==========================================
# MODULES : DEPARTEMENTS STANDARDS
# ==========================================
def afficher_trois_modules(nom_departement):
    tab1, tab2, tab3 = str_app.tabs([
        "1. Cahiers des Charges (Avis & Partage)", 
        "2. Expression des Besoins", 
        "3. Suivi & État de mes demandes"
    ])

    with tab1:
        afficher_module_cahiers_charges(nom_departement)

    with tab2:
        str_app.subheader("Exprimer un besoin / Demande d'achat")
        with str_app.form(f"form_besoin_{nom_departement}", clear_on_submit=True):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques")
            fournisseur_suggere = str_app.text_input("Fournisseur pressenti (optionnel)")
            
            submit_besoin = str_app.form_submit_button("Transmettre le besoin aux Achats")
            if submit_besoin:
                if titre_besoin and desc_besoin:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nom_departement, titre_besoin, desc_besoin, 0.0,
                        fournisseur_suggere if fournisseur_suggere else "À sourcer",
                        "En attente Achats", "achats", "En attente", "En attente", "",
                        datetime.now().strftime("%Y-%m-%d %H:%M")
                    ))
                    conn.commit()
                    conn.close()
                    
                    ajouter_log("Nouvelle Demande", nom_departement, f"Demande - {titre_besoin}")
                    str_app.success("Besoin transmis avec succès ! Le formulaire a été réinitialisé.")
                    str_app.rerun()

    with tab3:
        str_app.subheader("Suivi et Modification de vos demandes")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, cahier_charges, fournisseur, statut, motif_refus FROM demandes WHERE departement = ?", (nom_departement,))
        mes_demandes = cursor.fetchall()
        conn.close()
        
        if mes_demandes:
            for d in mes_demandes:
                d_id, d_titre, d_cc, d_fourn, d_statut, d_motif = d
                with str_app.expander(f"Demande #{d_id} : {d_titre} — Statut : {d_statut}"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur :** {d_fourn}")
                    if d_motif:
                        str_app.error(f"❌ **Motif du refus / demande de modification :** {d_motif}")
                    
                    if d_statut == "Refusé avec demande de modification":
                        str_app.info("Vous pouvez modifier votre demande ci-dessous et la soumettre à nouveau.")
                        with str_app.form(f"form_modif_{d_id}"):
                            nouveau_titre = str_app.text_input("Modifier l'intitulé", value=d_titre)
                            nouvelles_specs = str_app.text_area("Modifier les spécifications", value=d_cc)
                            nouveau_fournisseur = str_app.text_input("Modifier le fournisseur", value=d_fourn)
                            
                            if str_app.form_submit_button("Soumettre à nouveau la demande modifiée"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET titre = ?, cahier_charges = ?, fournisseur = ?, etape_actuelle = 'achats', avis_achats = 'En attente', statut = 'En attente Achats (Modifié)', motif_refus = ''
                                    WHERE id = ?
                                ''', (nouveau_titre, nouvelles_specs, nouveau_fournisseur, d_id))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Modification & Resoumission", nom_departement, f"Demande #{d_id} modifiée et relancée")
                                str_app.success("Demande modifiée et transmise de nouveau aux Achats !")
                                str_app.rerun()
        else:
            str_app.info("Aucune demande en cours.")


# ==========================================
# GESTION DES AFFICHAGES SELON LE PROFIL
# ==========================================

budget_global = get_valeur_globale("budget_global")
solde_restant = get_valeur_globale("solde_restant")

if profil["type"] == "standard":
    afficher_trois_modules(nom_dept)
    str_app.markdown("---")
    afficher_espace_coordination_et_journal(nom_dept)

elif profil["type"] == "achats":
    str_app.subheader("🛒 Achats - Sourcing & Chiffrage")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{budget_global:,.2f} €")
    col2.metric("Solde Restant", f"{solde_restant:,.2f} €")
    
    str_app.markdown("---")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
    demandes_achats = cursor.fetchall()
    conn.close()
    
    if demandes_achats:
        for d in demandes_achats:
            d_id, d_dept, d_titre, d_cc, d_fourn = d
            with str_app.expander(f"Besoin #{d_id} - {d_titre} (Par : {d_dept})"):
                str_app.write(f"**Spécifications :** {d_cc}")
                str_app.info(f"💡 **Fournisseur pressenti par le demandeur :** {d_fourn}")
                
                with str_app.form(f"form_achats_{d_id}"):
                    fournisseur_choisi = str_app.text_input("Confirmer ou modifier le fournisseur", value=d_fourn if d_fourn != "À sourcer" else "")
                    montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                    action_achats = str_app.radio("Décision", ["Valider & Transmettre Finance", "Refus définitif (Bloqué)", "Refusé avec demande de modification"], key=f"a_achats_{d_id}")
                    motif = str_app.text_input("Motif obligatoire en cas de refus / blocage")
                    
                    if str_app.form_submit_button("Valider la décision"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        if action_achats == "Valider & Transmettre Finance" and montant_chiffre > 0:
                            cursor.execute('''
                                UPDATE demandes 
                                SET fournisseur = ?, montant = ?, avis_achats = 'Validé', etape_actuelle = 'finance', statut = 'En attente Finance'
                                WHERE id = ?
                            ''', (fournisseur_choisi, montant_chiffre, d_id))
                            conn.commit()
                            conn.close()
                            ajouter_log("Validation Achats", "Achats", f"Demande #{d_id} chiffrée à {montant_chiffre}€")
                            str_app.rerun()
                        elif "Refus" in action_achats:
                            if not motif:
                                str_app.error("Veuillez saisir un motif pour justifier le refus.")
                                conn.close()
                            else:
                                etape_suivante = "bloque" if action_achats == "Refus définitif (Bloqué)" else "modification"
                                statut_suivi = "Refusé définitivement par les Achats" if action_achats == "Refus définitif (Bloqué)" else "Refusé avec demande de modification"
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET avis_achats = 'Refusé', motif_refus = ?, etape_actuelle = ?, statut = ?
                                    WHERE id = ?
                                ''', (motif, etape_suivante, statut_suivi, d_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Refus Achats", "Achats", f"Demande #{d_id} refusée. Motif : {motif}")
                                str_app.rerun()
    else:
        str_app.info("Aucun besoin en attente de chiffrage.")
    
    afficher_suivi_global()
    afficher_espace_coordination_et_journal(nom_dept)

elif profil["type"] == "finance":
    str_app.subheader("💰 Finance - Contrôle Budgétaire & Cahiers des Charges")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{budget_global:,.2f} €")
    col2.metric("Solde Actuel", f"{solde_restant:,.2f} €")
    
    tab_fin1, tab_fin2 = str_app.tabs(["1. Validation Budgétaire", "2. Cahiers des Charges (Finance)"])
    
    with tab_fin1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, montant FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        demandes_finance = cursor.fetchall()
        conn.close()
        
        if demandes_finance:
            for d in demandes_finance:
                d_id, d_dept, d_titre, d_montant = d
                with str_app.expander(f"Demande #{d_id} - {d_titre} | {d_montant} € (Par : {d_dept})"):
                    with str_app.form(f"form_fin_{d_id}"):
                        avis = str_app.radio("Avis Financier", ["Valider & Transmettre Fondateur", "Refus définitif (Bloqué)", "Refusé avec demande de modification"])
                        motif_fin = str_app.text_input("Motif obligatoire en cas de refus")
                        if str_app.form_submit_button("Valider la décision"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if avis == "Valider & Transmettre Fondateur":
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET avis_finance = 'Validé', etape_actuelle = 'fondateur', statut = 'Prêt pour Signature Finale'
                                    WHERE id = ?
                                ''', (d_id,))
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Finance", "Finance", f"Budget validé pour la demande #{d_id}")
                                str_app.rerun()
                            else:
                                if not motif_fin:
                                    str_app.error("Veuillez saisir un motif.")
                                    conn.close()
                                else:
                                    etape_suivante = "bloque" if avis == "Refus définitif (Bloqué)" else "modification"
                                    statut_suivi = "Refusé par la Finance" if avis == "Refus définitif (Bloqué)" else "Refusé avec demande de modification"
                                    cursor.execute('''
                                        UPDATE demandes 
                                        SET avis_finance = 'Refusé', motif_refus = ?, etape_actuelle = ?, statut = ?
                                        WHERE id = ?
                                    ''', (motif_fin, etape_suivante, statut_suivi, d_id))
                                    conn.commit()
                                    conn.close()
                                    ajouter_log("Refus Finance", "Finance", f"Demande #{d_id} refusée. Motif : {motif_fin}")
                                    str_app.rerun()
        else:
            str_app.info("Aucune demande en attente d'avis financier.")
            
    with tab_fin2:
        afficher_module_cahiers_charges(nom_dept)

    afficher_suivi_global()
    afficher_espace_coordination_et_journal(nom_dept)

elif profil["type"] == "fondateur":
    str_app.subheader("⭐ Bureau du Fondateur - Direction Générale")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{budget_global:,.2f} €")
    col2.metric("Solde Disponible", f"{solde_restant:,.2f} €")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, montant, fournisseur, cahier_charges FROM demandes WHERE etape_actuelle = 'fondateur'")
    demandes_fondateur = cursor.fetchall()
    conn.close()
    
    if demandes_fondateur:
        for d in demandes_fondateur:
            d_id, d_dept, d_titre, d_montant, d_fourn, d_cc = d
            with str_app.expander(f"Dossier #{d_id} - {d_titre} | {d_montant} € ({d_dept})"):
                str_app.write(f"🛒 **Fournisseur :** {d_fourn}")
                str_app.write(f"📝 **Spécifications :** {d_cc}")
                
                with str_app.form(f"form_fondateur_{d_id}"):
                    action_fondateur = str_app.radio("Décision de la Direction", [
                        "Signer & Décaisser", 
                        "Refus définitif (Bloqué)", 
                        "Refusé avec demande de modification"
                    ])
                    motif_fondateur = str_app.text_input("Motif obligatoire en cas de refus / blocage")
                    
                    if str_app.form_submit_button("Valider la décision exécutive"):
                        if action_fondateur == "Signer & Décaisser":
                            if solde_restant >= d_montant:
                                nouveau_solde = solde_restant - d_montant
                                set_valeur_globale("solde_restant", nouveau_solde)
                                
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET etape_actuelle = 'termine', statut = 'Signé & Exécuté par le Fondateur'
                                    WHERE id = ?
                                ''', (d_id,))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Signature Fondateur", "Fondateur", f"Décaissement de {d_montant}€ pour la demande #{d_id}")
                                str_app.success("Décaissé avec succès !")
                                str_app.rerun()
                            else:
                                str_app.error("Solde insuffisant pour décaisser ce montant.")
                        else:
                            if not motif_fondateur:
                                str_app.error("Veuillez saisir un motif pour justifier le refus de la direction.")
                            else:
                                etape_suivante = "bloque" if action_fondateur == "Refus définitif (Bloqué)" else "modification"
                                statut_suivi = "Refusé définitivement par le Fondateur" if action_fondateur == "Refus définitif (Bloqué)" else "Refusé avec demande de modification"
                                
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET motif_refus = ?, etape_actuelle = ?, statut = ?
                                    WHERE id = ?
                                ''', (motif_fondateur, etape_suivante, statut_suivi, d_id))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Refus Fondateur", "Fondateur", f"Demande #{d_id} refusée par la Direction. Motif : {motif_fondateur}")
                                str_app.rerun()
    else:
        str_app.info("Aucun dossier en attente de signature.")
    
    afficher_suivi_global()
    
    with str_app.expander("📚 **Vue Panoramique de TOUS les Cahiers des Charges de l'Entreprise**"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT departement, titre, date, destinataires_avis FROM cahiers_charges")
        tous_cc = cursor.fetchall()
        conn.close()
        
        if tous_cc:
            # Regrouper par département
            dict_cc = {}
            for item in tous_cc:
                d_n, t_titre, t_date, t_dest = item
                if d_n not in dict_cc:
                    dict_cc[d_n] = []
                dict_cc[d_n].append({"titre": t_titre, "date": t_date, "dest": json.loads(t_dest) if t_dest else []})
                
            for d_nom, docs in dict_cc.items():
                str_app.markdown(f"### Département : {d_nom}")
                for doc in docs:
                    str_app.markdown(f"- **{doc['titre']}** (Date : {doc['date']}) — Partagé avec : {', '.join(doc['dest'])}")
        else:
            str_app.info("Aucun cahier des charges enregistré pour le moment.")

    with str_app.expander("📖 **Journaux de Bord Quotidiens de TOUS les Départements**"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT departement, titre, texte, date FROM journaux_bord ORDER BY id DESC")
        tous_journaux = cursor.fetchall()
        conn.close()
        
        if tous_journaux:
            dict_j = {}
            for item in tous_journaux:
                d_n, j_titre, j_texte, j_date = item
                if d_n not in dict_j:
                    dict_j[d_n] = []
                dict_j[d_n].append({"titre": j_titre, "texte": j_texte, "date": j_date})
                
            for d_nom, entrees in dict_j.items():
                str_app.markdown(f"### 🏢 {d_nom}")
                for ent in entrees:
                    str_app.markdown(f"> **[{ent['date']}] {ent['titre']}**\n> {ent['texte']}")
                str_app.markdown("---")
        else:
            str_app.info("Aucune entrée dans les journaux de bord pour le moment.")

    with str_app.expander("🔒 **Journal d'Audit & Traçabilité Financière (Accès Réservé Fondateur)**"):
        conn = get_db_connection()
        df_logs = pd.read_sql_query("SELECT date, acteur, action, details FROM logs_audit ORDER BY id DESC", conn)
        conn.close()
        
        if not df_logs.empty:
            str_app.dataframe(df_logs, use_container_width=True)
        else:
            str_app.write("Aucune activité enregistrée.")
    
    afficher_espace_coordination_et_journal(nom_dept)
