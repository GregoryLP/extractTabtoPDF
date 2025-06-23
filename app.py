import streamlit as st
import tabula
import pandas as pd
import tempfile
import os
import zipfile
from io import BytesIO
import base64

# Configuration de la page
st.set_page_config(
    page_title="Extracteur de Tableaux PDF",
    page_icon="📊",
    layout="wide"
)

def process_pdf(uploaded_file):
    """Traite le PDF et extrait les tableaux de consommation"""
    
    # Créer un fichier temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name
    
    try:
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 Lecture du PDF...")
        progress_bar.progress(25)
        
        # Lire toutes les tables de toutes les pages
        tables = tabula.read_pdf(
            tmp_file_path, 
            pages='all', 
            multiple_tables=True, 
            lattice=True
        )
        
        status_text.text("📊 Analyse des tableaux...")
        progress_bar.progress(50)
        
        # Liste pour stocker les tableaux pertinents
        resultats_intermediaires = []
        
        # Parcourir les tables et filtrer
        for i, table in enumerate(tables):
            if table.empty:
                continue
            
            # Convertir en texte brut pour vérifier le contenu
            table_str = table.astype(str).apply(lambda x: ' '.join(x), axis=1).str.cat(sep=' ')
            
            if "Consommation totale électrique" in table_str:
                resultats_intermediaires.append((i, table))
        
        status_text.text("💾 Préparation des fichiers...")
        progress_bar.progress(75)
        
        # Créer les fichiers CSV
        csv_files = []
        
        if resultats_intermediaires:
            # Créer un fichier pour chaque tableau trouvé
            for idx, (table_num, df) in enumerate(resultats_intermediaires, start=1):
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8')
                csv_buffer.seek(0)
                
                csv_files.append({
                    'name': f"consommation_tableau_{idx}.csv",
                    'data': csv_buffer.getvalue(),
                    'dataframe': df
                })
            
            # Créer un fichier combiné si plusieurs tableaux
            if len(resultats_intermediaires) > 1:
                try:
                    fusionne = pd.concat([df for _, df in resultats_intermediaires], ignore_index=True)
                    csv_buffer_combined = BytesIO()
                    fusionne.to_csv(csv_buffer_combined, index=False, encoding='utf-8')
                    csv_buffer_combined.seek(0)
                    
                    csv_files.append({
                        'name': "consommation_combine.csv",
                        'data': csv_buffer_combined.getvalue(),
                        'dataframe': fusionne
                    })
                except Exception as e:
                    st.warning(f"Impossible de combiner les tableaux: {e}")
        
        progress_bar.progress(100)
        status_text.text("✅ Traitement terminé!")
        
        return csv_files, len(tables), len(resultats_intermediaires)
        
    except Exception as e:
        st.error(f"Erreur lors du traitement: {e}")
        return [], 0, 0
    
    finally:
        # Nettoyer le fichier temporaire
        try:
            os.unlink(tmp_file_path)
        except:
            pass

def create_download_zip(csv_files):
    """Crée un fichier ZIP contenant tous les CSV"""
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for csv_file in csv_files:
            zip_file.writestr(csv_file['name'], csv_file['data'])
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def main():
    # Titre principal
    st.title("📊 Extracteur de Tableaux de Consommation PDF")
    st.markdown("---")
    
    # Description
    st.markdown("""
    ### 🎯 Fonctionnalité
    Cette application extrait automatiquement les tableaux de consommation énergétique depuis vos fichiers PDF.
    
    ### 📋 Instructions
    1. **Glissez-déposez** votre fichier PDF dans la zone ci-dessous
    2. **Attendez** le traitement automatique
    3. **Téléchargez** les fichiers CSV générés
    """)
    
    # Zone de téléchargement
    st.markdown("### 📁 Téléchargement du fichier PDF")
    uploaded_file = st.file_uploader(
        "Choisissez un fichier PDF",
        type=['pdf'],
        help="Glissez-déposez votre fichier PDF ici ou cliquez pour le sélectionner"
    )
    
    if uploaded_file is not None:
        # Afficher les informations du fichier
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📄 Nom du fichier", uploaded_file.name)
        with col2:
            st.metric("📏 Taille", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("📋 Type", uploaded_file.type)
        
        st.markdown("---")
        
        # Bouton de traitement
        if st.button("🚀 Traiter le PDF", type="primary"):
            with st.spinner("Traitement en cours..."):
                csv_files, total_tables, found_tables = process_pdf(uploaded_file)
            
            # Affichage des résultats
            st.markdown("### 📊 Résultats du traitement")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Tableaux totaux", total_tables)
            with col2:
                st.metric("🎯 Tableaux de consommation", found_tables)
            with col3:
                st.metric("📄 Fichiers CSV générés", len(csv_files))
            
            if csv_files:
                st.success(f"✅ {len(csv_files)} fichier(s) CSV généré(s) avec succès!")
                
                # Aperçu des données
                st.markdown("### 👀 Aperçu des données extraites")
                
                for i, csv_file in enumerate(csv_files):
                    with st.expander(f"📋 {csv_file['name']}", expanded=(i == 0)):
                        st.dataframe(csv_file['dataframe'], use_container_width=True)
                        st.info(f"📏 Dimensions: {csv_file['dataframe'].shape[0]} lignes × {csv_file['dataframe'].shape[1]} colonnes")
                
                # Zone de téléchargement
                st.markdown("### 💾 Téléchargement des fichiers")
                
                # Téléchargements individuels
                st.markdown("#### 📄 Fichiers individuels")
                cols = st.columns(min(len(csv_files), 3))
                
                for i, csv_file in enumerate(csv_files):
                    with cols[i % 3]:
                        st.download_button(
                            label=f"⬇️ {csv_file['name']}",
                            data=csv_file['data'],
                            file_name=csv_file['name'],
                            mime='text/csv',
                            use_container_width=True
                        )
                
                # Téléchargement groupé si plusieurs fichiers
                if len(csv_files) > 1:
                    st.markdown("#### 📦 Téléchargement groupé")
                    zip_data = create_download_zip(csv_files)
                    
                    st.download_button(
                        label="⬇️ Télécharger tous les fichiers (ZIP)",
                        data=zip_data,
                        file_name=f"tableaux_consommation_{uploaded_file.name.replace('.pdf', '')}.zip",
                        mime='application/zip',
                        type="primary",
                        use_container_width=True
                    )
            
            else:
                st.error("❌ Aucun tableau de consommation trouvé dans le PDF")
                st.info("""
                💡 **Conseils de dépannage:**
                - Vérifiez que le PDF contient des tableaux avec "Consommation totale électrique"
                - Assurez-vous que le PDF n'est pas protégé ou crypté
                - Essayez avec un autre fichier PDF pour tester
                """)
    
    # Section d'aide
    with st.sidebar:
        st.markdown("### ℹ️ Aide")
        st.markdown("""
        **Types de tableaux détectés:**
        - Tableaux contenant "Consommation totale électrique"
        - Données énergétiques structurées
        
        **Formats supportés:**
        - PDF avec tableaux structurés
        - PDF générés par ordinateur (pas scannés)
        
        **Problèmes courants:**
        - PDF scannés : non supportés
        - PDF protégés : non supportés
        - Tableaux mal formatés : résultats variables
        """)
        
        st.markdown("### 🔧 Dépendances requises")
        st.code("""
pip install streamlit
pip install tabula-py
pip install pandas
        """)

if __name__ == "__main__":
    main()