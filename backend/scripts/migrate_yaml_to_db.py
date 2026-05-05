import yaml
import json
import os
import sys

# Add app to path to import db session
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import get_db_connection

def migrate():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/profile.yml'))
    
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return

    print(f"Reading legacy data from {config_path}...")
    with open(config_path, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f) or {}

    # Extract structured components
    personal = yaml_data.get('personal', {})
    languages = yaml_data.get('languages', {})
    preferences = yaml_data.get('preferences', {})
    
    # Handle legacy root keys if languages is empty but root has data
    legacy_keys = ["about", "experience", "education", "skills"]
    if not languages and any(k in yaml_data for k in legacy_keys):
        print("Detected legacy root keys, moving to 'pt' language...")
        languages["pt"] = {}
        for k in legacy_keys:
            if k in yaml_data:
                languages["pt"][k] = yaml_data[k]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if profile with ID 1 exists
            cur.execute("SELECT full_data FROM public.user_profiles WHERE id = 1")
            row = cur.fetchone()
            
            if row:
                db_data = row[0]
                print("Found existing DB profile. Merging...")
                
                # Merge logic: DB data usually wins for personal/preferences if it exists, 
                # but YAML wins for languages if DB languages is empty.
                # Actually, let's merge deep.
                
                db_data['personal'] = {**personal, **db_data.get('personal', {})}
                db_data['preferences'] = {**preferences, **db_data.get('preferences', {})}
                
                if 'languages' not in db_data:
                    db_data['languages'] = {}
                
                for lang, lang_data in languages.items():
                    if lang not in db_data['languages']:
                        db_data['languages'][lang] = lang_data
                    else:
                        # Merge nested fields
                        for field in ["about", "experience", "skills", "education"]:
                            if lang_data.get(field) and not db_data['languages'][lang].get(field):
                                db_data['languages'][lang][field] = lang_data[field]
                
                cur.execute("UPDATE public.user_profiles SET full_data = %s WHERE id = 1", (json.dumps(db_data),))
                print("Update successful.")
            else:
                print("No DB profile found. Creating new one from YAML...")
                # Prepare clean structure
                new_data = {
                    "personal": personal,
                    "languages": languages,
                    "preferences": preferences
                }
                cur.execute("INSERT INTO public.user_profiles (id, full_data) VALUES (1, %s)", (json.dumps(new_data),))
                print("Insertion successful.")
        
        conn.commit()
        print("Migration committed to database.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
