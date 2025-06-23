import tabula
import pandas as pd

# Chemin du fichier PDF
file_path = "Extraction pleiades.pdf"

# Lire toutes les tables de toutes les pages (structure tableau attendue)
tables = tabula.read_pdf(file_path, pages='all', multiple_tables=True, lattice=True)

# Liste pour stocker les tableaux pertinents
resultats_intermediaires = []

# Parcourir les tables et filtrer celles qui contiennent les consommations finales
for i, table in enumerate(tables):
    if table.empty:
        continue
    # Convertir en texte brut pour vérifier si le tableau contient notre zone cible
    table_str = table.astype(str).apply(lambda x: ' '.join(x), axis=1).str.cat(sep=' ')
    
    if "Consommation totale électrique" in table_str:
        resultats_intermediaires.append(table)

# Sauvegarder les tableaux extraits
for idx, df in enumerate(resultats_intermediaires, start=1):
    df.to_excel(f"resultat_energie_finale_bloc_{idx}.xlsx", index=False)

# Ou concaténer tous les tableaux si même structure :
if resultats_intermediaires:
    fusionne = pd.concat(resultats_intermediaires, ignore_index=True)
    fusionne.to_excel("resultats_energie_finale_combine.xlsx", index=False)
    print("✅ Extraction terminée avec succès.")
else:
    print("❌ Aucun tableau de consommation trouvé.")