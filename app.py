import streamlit as st
import pandas as pd
import tempfile
import os
import zipfile
from io import BytesIO
import base64

# Essayer d'importer les différentes librairies
try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# Configuration de la page
st.set_page_config(
    page_title="Extracteur de Tableaux PDF",
    page_icon="📊",
    layout="wide"
)

def process_pdf_with_pymupdf(tmp_file_path):
    """Extrait les tableaux avec PyMuPDF (sans Java)"""
    try:
        doc = fitz.open(tmp_file_path)
        resultats_intermediaires = []
        total_tables = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            tables = page.find_tables()
            total_tables += len(tables)
            
            for table in tables:
                try:
                    df = table.to_pandas()
                    if not df.empty:
                        table_str = df.astype(str).apply(lambda x: ' '.join(x), axis=1).str.cat(sep=' ')
                        if "Consommation totale électrique" in table_str:
                            resultats_intermediaires.append((page_num, df))
                except Exception as e:
                    continue
        
        doc.close()
        return resultats_intermediaires, total_tables
    except Exception as e:
        raise Exception(f"Erreur PyMuPDF: {e}")

def process_pdf_with_pdfplumber(tmp_file_path):
    """Extrait les tableaux avec pdfplumber (sans Java)"""
    try:
        import pdfplumber
        
        resultats_intermediaires = []
        total_tables = 0
        
        with pdfplumber.open(tmp_file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                total_tables += len(tables)
                
                for table in tables:
                    if table and len(table) > 1:
                        try:
                            # Convertir en DataFrame
                            df = pd.DataFrame(table[1:], columns=table[0])
                            table_str = df.astype(str).apply(lambda x: ' '.join(x), axis=1).str.cat(sep=' ')
                            
                            if "Consommation totale électrique" in table_str:
                                resultats_intermediaires.append((page_num, df))
                        except Exception as e:
                            continue
        
        return resultats_intermediaires, total_tables
    except Exception as e:
        raise Exception(f"Erreur pdfplumber: {e}")

def process_pdf_with_tabula(tmp_file_path):
    """Extrait les tableaux avec tabula (nécessite Java)"""
    try:
        tables = tabula.read_pdf(
            tmp_file_path, 
            pages='all', 
            multiple_tables=True, 
            lattice=True
        )
        
        resultats_intermediaires = []
        
        for i, table in enumerate(tables):
            if table.empty:
                continue
            
            table_str = table.astype(str).apply(lambda x: ' '.join(x), axis=1).str.cat(sep=' ')
            
            if "Consommation totale électrique" in table_str:
                resultats_intermediaires.append((i, table))
        
        return resultats_intermediaires, len(tables)
    except Exception as e:
        raise Exception(f"Erreur tabula: {e}")

def sanitize_columns(df):
    """Nettoie les colonnes pour éviter les doublons ou noms vides"""
    cols = []
    seen = {}
    for i, col in enumerate(df.columns):
        if not col or pd.isna(col):
            col = f"col_{i}"
        if col in seen:
            seen[col] += 1
            col = f"{col}_{seen[col]}"
        else:
            seen[col] = 0
        cols.append(col)
    df.columns = cols
    return df


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
        
        # Essayer différentes méthodes d'extraction
        resultats_intermediaires = []
        total_tables = 0
        method_used = ""
        
        # Méthode 1: PyMuPDF (sans Java)
        if PYMUPDF_AVAILABLE:
            try:
                status_text.text("🔍 Extraction avec PyMuPDF...")
                resultats_intermediaires, total_tables = process_pdf_with_pymupdf(tmp_file_path)
                method_used = "PyMuPDF"
                if resultats_intermediaires:
                    st.info(f"✅ Extraction réussie avec {method_used}")
            except Exception as e:
                st.warning(f"PyMuPDF a échoué: {e}")
        
        # Méthode 2: pdfplumber (sans Java) si PyMuPDF n'a pas fonctionné
        if not resultats_intermediaires and PDFPLUMBER_AVAILABLE:
            try:
                status_text.text("🔍 Extraction avec pdfplumber...")
                resultats_intermediaires, total_tables = process_pdf_with_pdfplumber(tmp_file_path)
                method_used = "pdfplumber"
                if resultats_intermediaires:
                    st.info(f"✅ Extraction réussie avec {method_used}")
            except Exception as e:
                st.warning(f"pdfplumber a échoué: {e}")
        
        # Méthode 3: tabula (nécessite Java) en dernier recours
        if not resultats_intermediaires and TABULA_AVAILABLE:
            try:
                status_text.text("🔍 Extraction avec tabula...")
                resultats_intermediaires, total_tables = process_pdf_with_tabula(tmp_file_path)
                method_used = "tabula"
                if resultats_intermediaires:
                    st.info(f"✅ Extraction réussie avec {method_used}")
            except Exception as e:
                st.error(f"Tabula a échoué (Java requis): {e}")
        
        if not resultats_intermediaires:
            # Afficher les options d'installation
            st.error("❌ Aucune méthode d'extraction n'a fonctionné")
            show_installation_help()
            return [], total_tables, 0
        
        status_text.text("📊 Analyse des tableaux...")
        progress_bar.progress(50)
        
        status_text.text("💾 Préparation des fichiers...")
        progress_bar.progress(75)
        
        # Créer les fichiers CSV
        csv_files = []
        
        if resultats_intermediaires:
            # Créer un fichier pour chaque tableau trouvé
            for idx, (table_num, df) in enumerate(resultats_intermediaires, start=1):
                csv_buffer = BytesIO()
                df = sanitize_columns(df)
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
        status_text.text(f"✅ Traitement terminé avec {method_used}!")
        
        return csv_files, total_tables, len(resultats_intermediaires)
        
    except Exception as e:
        st.error(f"Erreur lors du traitement: {e}")
        show_installation_help()
        return [], 0, 0
    
    finally:
        # Nettoyer le fichier temporaire
        try:
            os.unlink(tmp_file_path)
        except:
            pass

def show_installation_help():
    """Affiche l'aide pour l'installation des dépendances"""
    st.markdown("### 🔧 Installation des dépendances")
    
    st.markdown("**Option 1 - Sans Java (Recommandé) :**")
    st.code("pip install PyMuPDF pdfplumber pandas")
    
    st.markdown("**Option 2 - Avec Java :**")
    st.code("pip install tabula-py pandas")
    st.markdown("Puis installer Java depuis https://adoptium.net/")
    
    available_methods = []
    if PYMUPDF_AVAILABLE:
        available_methods.append("✅ PyMuPDF")
    else:
        available_methods.append("❌ PyMuPDF")
    
    if PDFPLUMBER_AVAILABLE:
        available_methods.append("✅ pdfplumber")
    else:
        available_methods.append("❌ pdfplumber")
    
    if TABULA_AVAILABLE:
        available_methods.append("✅ tabula")
    else:
        available_methods.append("❌ tabula")
    
    st.markdown("**Méthodes disponibles :**")
    for method in available_methods:
        st.markdown(f"- {method}")

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
        
        if not PYMUPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            st.error("❌ Aucune librairie d'extraction PDF installée!")
            st.code("pip install PyMuPDF pdfplumber")
        else:
            st.success("✅ Au moins une librairie d'extraction disponible")
        
        st.markdown("**Méthodes d'extraction :**")
        methods_status = [
            ("PyMuPDF", PYMUPDF_AVAILABLE, "Sans Java, rapide"),
            ("pdfplumber", PDFPLUMBER_AVAILABLE, "Sans Java, précis"),
            ("tabula", TABULA_AVAILABLE, "Nécessite Java")
        ]
        
        for name, available, description in methods_status:
            status = "✅" if available else "❌"
            st.markdown(f"- {status} **{name}** : {description}")
        
        if not any([PYMUPDF_AVAILABLE, PDFPLUMBER_AVAILABLE, TABULA_AVAILABLE]):
            st.warning("🚨 Installez au moins une librairie pour continuer")
            st.code("""
# Installation recommandée (sans Java)
pip install PyMuPDF pdfplumber pandas

# Ou avec Java
pip install tabula-py pandas
            """)

if __name__ == "__main__":
    main()