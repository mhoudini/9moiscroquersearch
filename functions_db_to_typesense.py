import mysql.connector
import json
from dotenv import load_dotenv
import os
from datetime import date, datetime
import requests

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration de Typesense
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST")

def json_serial(obj):
    """Fonction d'aide pour sérialiser les objets date et datetime en JSON."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def export_table_to_jsonl(table_name):
    # Connexion à la base de données MySQL
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=os.getenv("DB_PORT")  # Ajout du port ici
    )
    cursor = conn.cursor()

    # Obtenir les noms des colonnes de la table
    cursor.execute(f"DESCRIBE {table_name}")
    columns = [column[0] for column in cursor.fetchall()]

    # Exécuter la requête pour extraire les données
    cursor.execute(f"SELECT * FROM {table_name}")

    # Créer et ouvrir le fichier JSONL
    with open(f"jsonl_files/{table_name}.jsonl", "w") as file:
        for row in cursor:
            # Structurer la ligne en utilisant les noms des colonnes
            data = dict(zip(columns, row))

            # Renommer les champs
            if 'id' in data:
                data['el_id'] = data.pop('id')
            if 'question' in data:
                data['title'] = data.pop('question')
            if 'name' in data:
                data['title'] = data.pop('name')
            if 'answer' in data:
                data['content'] = data.pop('answer')
            if 'review' in data:
                data['content'] = data.pop('review')

            # Écrire la ligne JSON dans le fichier, en utilisant json_serial pour les dates
            file.write(json.dumps(data, default=json_serial) + "\n")

    # Fermer la connexion
    cursor.close()
    conn.close()

def infer_types_from_jsonl_line(line):
    data = json.loads(line)
    schema = []

    for key, value in data.items():
        if isinstance(value, int):
            field_type = "int32"  # ou "int64" si nécessaire
        elif isinstance(value, float):
            field_type = "float"
        elif isinstance(value, bool):
            field_type = "bool"
        else:
            field_type = "string"  # Par défaut

        schema.append({"name": key, "type": field_type})

    return schema

def create_collection_and_import_data(jsonl_file_path):
    # Déterminer le nom de la collection à partir du nom du fichier
    collection_name = os.path.basename(jsonl_file_path).split('.')[0]

    # Lire les premières lignes du fichier pour déterminer les fields
    with open(jsonl_file_path, 'r') as file:
        first_line = file.readline()
        fields = infer_types_from_jsonl_line(first_line)

    # Supprimer la collection si elle existe déjà
    requests.delete(f"{TYPESENSE_HOST}/collections/{collection_name}",
                    headers={"X-TYPESENSE-API-KEY": TYPESENSE_API_KEY})

    # Créer une nouvelle collection avec le schéma déterminé
    schema = {"name": collection_name, "fields": fields}
    requests.post(
        f"{TYPESENSE_HOST}/collections",
        headers={"X-TYPESENSE-API-KEY": TYPESENSE_API_KEY, "Content-Type": "application/json"},
        json=schema
    )

    # Importer les données dans la collection
    with open(jsonl_file_path, 'r') as file:
        documents = file.read()
    

    response = requests.post(
        f"{TYPESENSE_HOST}/collections/{collection_name}/documents/import",
        headers={"X-TYPESENSE-API-KEY": TYPESENSE_API_KEY, "Content-Type": "text/plain"},
        data=documents
    )
    print(f"Importé dans {collection_name}: {response.status_code}")