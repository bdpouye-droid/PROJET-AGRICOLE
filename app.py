import streamlit as st
import json
import os
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="Plateforme de Pilotage - Projet Agricole (86 ha)",
    page_layout="wide",
    initial_sidebar_state="expanded"
)

# Dossier de stockage local pour les fichiers téléversés
DOSSIER_ETUDES = "donnees_etudes"
if not os.path.exists(DOSSIER_ETUDES):
    os.makedirs(DOSSIER_ETUDES)

# Fichier de persistance simple (JSON) pour stocker les études et partages
FICHIER_BDD = "projet_agricole_db.json"

def charger_donnees():
    if os.path.exists(FICHIER_BDD):
        with open(FICHIER_BDD, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"etudes": [], "messages": []}
    return {"etudes": [], "messages": []}

def sauvegarder_donnees(data):
    with open(FICHIER_BDD, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = charger_donnees()

# Liste des départements impliqués dans le projet
tous_les_depts = [
    "Agriculture & Agro-pédologie",
    "Élevage & Pastoralisme",
    "Ressources Hydriques & Irrigation",
    "Infrastructures & Industrie",
    "Économie & Dimensionnement",
    "Recherche & Développement"
]

st.title("🌱 Plateforme Collaborative - Projet Agricole (86 ha)")
st.markdown("Outil centralisé de coordination technique, de dimensionnement et de partage documentaire entre départements.")

# Barre latérale pour la navigation
st.sidebar.image("https://img.icons8.com/color/96/agriculture.png", width=80)
st.sidebar.header("Navigation")
menu = st.sidebar.radio(
    "Aller vers :",
    ["Tableau de bord", "Nouvelle Étude / Fichier", "Module Agro-pédologie", "Messagerie & Échanges Inter-départements"]
)

# ---------------------------------------------------------
# 1. TABLEAU DE BORD
# ---------------------------------------------------------
if menu == "Tableau de bord":
    st.header("📊 Vue d'ensemble du projet")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Superficie totale", "86 ha")
    col2.metric("Études enregistrées", len(db["etudes"]))
    col3.metric("Départements actifs", len(tous_les_depts))
    
    st.markdown("---")
    st.subheader("📁 Études et documents récents")
    
    if not db["etudes"]:
        st.info("Aucune étude enregistrée pour le moment. Utilisez l'onglet 'Nouvelle Étude / Fichier' pour en ajouter.")
    else:
        for idx, etude in enumerate(reversed(db["etudes"])):
            with st.expander(f"📌 [{etude['departement'
]}] {etude['titre']} (Créé le {etude['date']})"):
                st.write(f"**Auteur / Service :** {etude['departement']}")
                st.write(f"**Destinataires partagés :** {', '.join(etude.get('destinataires', [])) if etude.get('destinataires') else 'Aucun'}")
                
                # Affichage des champs spécifiques
                st.markdown("**Spécifications techniques :**")
                for k, v in etude.get('champs_specifiques', {}).items():
                    st.text(f"- {k.capitalize()} : {v}")
                
                if etude.get('fichier'):
                    st.success(f"Fichier joint : {etude['fichier']}")

# ---------------------------------------------------------
# 2. NOUVELLE ÉTUDE / FICHIER
# ---------------------------------------------------------
elif menu == "Nouvelle Étude / Fichier":
    st.header("📝 Création et Partage d'une Étude Technique")
    
    with st.form("form_nouvelle_etude"):
        titre = st.text_input("Titre de l'étude ou du livrable")
        nom_departement = st.selectbox("Département émetteur", tous_les_depts)
        
        st.markdown("### Paramètres spécifiques au département")
        champs_specifiques = {}
        
        if nom_departement == "Agriculture & Agro-pédologie":
            champs_specifiques["type_sol"] = st.text_input("Caractéristique du sol / Analyse pédologique")
            champs_specifiques["culture_visee"] = st.text_input("Culture / Assolement prévu")
            champs_specifiques["surface_concernee"] = st.number_input("Surface concernée (ha)", min_value=0.0, max_value=86.0, value=10.0)
        elif nom_departement == "Ressources Hydriques & Irrigation":
            champs_specifiques["besoin_eau"] = st.text_input("Besoin estimé (m³/ha/jour)")
            champs_specifiques["source_approvisionnement"] = st.selectbox("Source", ["Forage", "Retenue colliniaire", "Pompage rivière", "Autre"])
        elif nom_departement == "Élevage & Pastoralisme":
            champs_specifiques["type_cheptel"] = st.text_input("Type d'animaux / Charge pastorale")
            champs_specifiques["infrastructures"] = st.text_area("Bâtiments ou parcs nécessaires")
        elif nom_departement == "Infrastructures & Industrie":
            champs_specifiques["type_ouvrage"] = st.text_input("Type d'infrastructure (stockage, transformation, pistes)")
        elif nom_departement == "Économie & Dimensionnement":
            champs_specifiques["budget_estime"] = st.number_input("Budget prévisionnel (€)", min_value=0.0, step=1000.0)
        elif nom_departement == "Recherche & Développement":
            champs_specifiques["projet"] = st.text_input("Nom du prototype / Projet R&D")
            champs_specifiques["trl"] = st.slider("Niveau de Maturité Technologique (TRL)", 1, 9, 3)
            champs_specifiques["details"] = st.text_area("Protocole expérimental et livrables")
        else:
            champs_specifiques["details"] = st.text_area("Notes et spécifications techniques générales")

        fichier_televerse = st.file_uploader("Joindre un fichier technique (PDF, Excel, DWG, CSV)", type=["pdf", "xlsx", "csv", "docx", "txt"])
        
        st.markdown("### 🤝 Partager cette étude avec les départements")
        destinataires_choisis = st.multiselect("Sélectionnez les départements destinataires", tous_les_depts)
        
        submit_etude = st.form_submit_button("Créer et diffuser l'étude")
        
        if submit_etude:
            if not titre.strip():
                st.error("Veuillez renseigner un titre pour l'étude.")
            else:
                nom_fichier_sauvegarde = None
                if fichier_televerse is not None:
                    nom_fichier_sauvegarde = os.path.join(DOSSIER_ETUDES, fichier_televerse.name)
                    with open(nom_fichier_sauvegarde, "wb") as f:
                        f.write(fichier_televerse.getbuffer())
                
                nouvelle_entree = {
                    "titre": titre,
                    "departement": nom_departement,
                    "champs_specifiques": champs_specifiques,
                    "fichier": fichier_televerse.name if fichier_televerse else None,
                    "destinataires": destinataires_choisis,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                db["etudes"].append(nouvelle_entree)
                sauvegarder_donnees(db)
                st.success("Étude enregistrée et partagée avec succès !")

# ---------------------------------------------------------
# 3. MODULE AGRO-PÉDOLOGIE
# ---------------------------------------------------------
elif menu == "Module Agro-pédologie":
    st.header("🧪 Module Spécifique : Agro-pédologie & Sols (86 ha)")
    st.markdown("Importation de fichiers d'analyse de sols et centralisation des données agronomiques.")
    
    # Affichage des études filtrées sur l'agriculture
    etudes_agro = [e for e in db["etudes"] if e["departement"] == "Agriculture & Agro-pédologie"]
    
    if not etudes_agro:
        st.info("Aucune donnée agropédologique enregistrée pour le moment.")
    else:
        for etude in etudes_agro:
            st.subheader(f"📄 {etude['titre']}")
            st.write(f"**Date :** {etude['date']}")
            for k, v in etude.get('champs_specifiques', {}).items():
                st.write(f"- **{k.capitalize()}** : {v}")
            st.markdown("---")

# ---------------------------------------------------------
# 4. MESSAGERIE & ÉCHANGES
# ---------------------------------------------------------
elif menu == "Messagerie & Échanges Inter-départements":
    st.header("💬 Fil de discussion collaboratif")
    
    with st.form("form_message"):
        expediteur = st.selectbox("Votre département", tous_les_depts)
        texte_message = st.text_area("Message / Remarque / Coordination technique")
        submit_msg = st.form_submit_button("Envoyer le message")
        
        if submit_msg and texte_message.strip():
            db["messages"].append({
                "expediteur": expediteur,
                "texte": texte_message,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            sauvegarder_donnees(db)
            st.success("Message publié.")
            
    st.markdown("### Historique des échanges")
    if not db["messages"]:
        st.write("Aucun message pour l'instant.")
    else:
        for msg in reversed(db["messages"]):
            st.markdown(f"**[{msg['date']}] {msg['expediteur']}** :")
            st.write(msg['texte'])
            st.markdown("---")
