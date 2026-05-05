import yaml, json
from app.db.session import get_db_connection, get_db_cursor
from app.core.config import settings

def main():
    print("Reading YAML...")
    with open(settings.PROFILE_FILE, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f) or {}

    legacy_keys = ['about', 'experience', 'education', 'skills']
    if any(k in yaml_data for k in legacy_keys):
        if 'languages' not in yaml_data:
            yaml_data['languages'] = {}
        if 'pt' not in yaml_data['languages']:
            yaml_data['languages']['pt'] = {}
        for k in legacy_keys:
            if k in yaml_data:
                yaml_data['languages']['pt'][k] = yaml_data.pop(k)

    print("Reading DB...")
    conn = get_db_connection()
    with get_db_cursor(conn) as cur:
        cur.execute('SELECT full_data FROM user_profiles WHERE id = 1')
        db_data = cur.fetchone()['full_data'] or {}

    print("Merging data...")
    merged_data = {**db_data, **yaml_data}
    if 'personal' in db_data and 'personal' in yaml_data:
        merged_data['personal'] = {**db_data['personal'], **yaml_data['personal']}

    print("Saving to DB...")
    with conn.cursor() as cur:
        cur.execute('UPDATE user_profiles SET full_data = %s, updated_at = NOW() WHERE id = 1', (json.dumps(merged_data),))
    conn.commit()
    conn.close()
    print('Merged YAML into DB successfully!')

if __name__ == '__main__':
    main()
