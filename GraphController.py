import os
import pandas as pd
from neo4j import GraphDatabase
from config import URI, AUTH, DATABASE

# อำเภอ_ตำบล_หน่วย_แบบบัญชีรายชื่อ_check.csv
# อำเภอ_ตำบล_หน่วย_แบบบัญชีรายชื่อ_ผลคะแนน.csv
# อำเภอ_ตำบล_หน่วย_แบบแบ่งเขต_check.csv
# อำเภอ_ตำบล_หน่วย_แบบแบ่งเขต_ผลคะแนน.csv

class GraphController:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.setup_hierarchy()

    def close(self):
        self.driver.close()

    # --- ฟังก์ชันหลักในการรัน Cypher ---
    def execute_query(self, query, params=None):
        with self.driver.session(database=DATABASE) as session:
            session.run(query, params)

    # --- 1. สร้างโครงสร้างพื้นที่ (Hierarchy) ---
    def setup_hierarchy(self):
        query = """
        MERGE (prov:Province {name: 'เชียงใหม่'})
        MERGE (dist:District {name: 'เขตเลือกตั้งที่10', province: 'เชียงใหม่'})
        MERGE (dist)-[:IN_PROVINCE]->(prov)
        """
        self.execute_query(query)

    def add_station(self, amphoe, tambon, unit, station_id):
        query = """
        MATCH (dist:District {name: 'เขตเลือกตั้งที่10'})
        MERGE (amp:อำเภอ {name: $amphoe})
        MERGE (tam:ตำบล {name: $tambon, amphoe: $amphoe})
        MERGE (p:หน่วย {id: $station_id, unit: $unit})

        MERGE (amp)-[:IN_DISTRICT]->(dist)
        MERGE (tam)-[:IN_AMPHOE]->(amp)
        MERGE (p)-[:IN_TAMBON]->(tam)
        """
        self.execute_query(query, {'amphoe': amphoe, 'tambon': tambon, 'unit': unit, 'station_id': station_id})

    def extract_info(self, file_path):
        filename = os.path.basename(file_path)
        parts = filename.split('_')
        if len(parts) < 5:
            return None, None, None, None, None, None, None
        
        amphoe, tambon, unit, election_type, category_part = parts[0], parts[1], parts[2], parts[3], parts[4]
        category = category_part.split('.')[0]
        station_id = f"เชียงใหม่_เขต10_{amphoe}_{tambon}_{unit}"
        return parts, amphoe, tambon, unit, station_id, election_type, category

    def load_check_data(self, file_path, election_type, station_info):
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return

        if 'รายการ' not in df.columns:
            print(f"Skipping {file_path}: 'รายการ' column not found")
            return
            
        # แปลงแนวตั้งเป็นแนวนอน
        df_wide = df.set_index('รายการ').T.reset_index(drop=True)
        if df_wide.empty:
            return
            
        row_data = df_wide.to_dict('records')[0]
        
        # Mapping parameters to safe names
        params = {
            'station_id': station_info['station_id'],
            'type': election_type,
            'total_voters': row_data.get('จำนวนผู้มีสิทธิเลือกตั้งตามบัญชีรายชื่อผู้มีสิทธิเลือกตั้ง', 0),
            'present_voters': row_data.get('จำนวนผู้มาแสดงตน', 0),
            'cards_used': row_data.get('บัตรที่ใช้', 0),
            'good_cards': row_data.get('บัตรดี', 0),
            'bad_cards': row_data.get('บัตรเสีย', 0),
            'no_vote_cards': row_data.get('บัตรที่ไม่เลือก', 0),
            'remaining_cards': row_data.get('บัตรเลือกตั้งที่เหลือ', 0)
        }

        query = """
        MATCH (p:หน่วย {id: $station_id})
        MERGE (s:ข้อมูลการเลือกตั้ง {รูปแบบ: $type, station_id: $station_id})
        SET s.จำนวนผู้มีสิทธิเลือกตั้ง = toInteger($total_voters),
            s.จำนวนผู้มาแสดงตน = toInteger($present_voters),
            s.บัตรที่ใช้ = toInteger($cards_used),
            s.บัตรดี = toInteger($good_cards),
            s.บัตรเสีย = toInteger($bad_cards),
            s.บัตรที่ไม่เลือก = toInteger($no_vote_cards),
            s.บัตรเลือกตั้งที่เหลือ = toInteger($remaining_cards)
        MERGE (p)-[:HAS_STATS]->(s)
        """
        self.execute_query(query, params)

    # --- 3. นำเข้าผลคะแนน (Score Files) ---
    def load_score_data(self, file_path, election_type, station_id):
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
        
        for _, row in df.iterrows():
            params = {
                'station_id': station_id, 
                'votes': int(row.get('คะแนน', 0)),
                'ชื่อพรรค': row.get('ชื่อพรรค', row.get('พรรค', 'ไม่ระบุ')),
                'ชื่อผู้สมัคร': row.get('ชื่อผู้สมัคร', row.get('ผู้สมัคร', 'ไม่ระบุ')),
                'หมายเลข': str(row.get('หมายเลข', '0'))
            }
            
            if election_type == 'แบบแบ่งเขต':
                query = """
                MATCH (p:หน่วย {id: $station_id})
                MERGE (py:พรรค {ชื่อพรรค: $ชื่อพรรค})
                MERGE (c:ผู้สมัคร {ชื่อผู้สมัคร: $ชื่อผู้สมัคร, หมายเลข: $หมายเลข})
                MERGE (c)-[:PERTAINS_TO]->(py)
                MERGE (p)-[r:VOTED_CANDIDATE]->(c)
                SET r.votes = $votes
                """
            else: # แบบบัญชีรายชื่อ
                query = """
                MATCH (p:หน่วย {id: $station_id})
                MERGE (py:พรรค {ชื่อพรรค: $ชื่อพรรค})
                MERGE (p)-[r:VOTED_PARTY]->(py)
                SET r.votes = $votes
                """
            self.execute_query(query, params)

def run_pipeline(input_folder, FIRST=False):
    pipeline = GraphController(URI, AUTH)
    
    # Walk through subdirectories as well
    files_to_process = []
    if not os.path.exists(input_folder):
        print(f"Folder not found: {input_folder}")
        return

    for root, _, files in os.walk(input_folder):
        for f in files:
            if f.endswith('.csv'):
                files_to_process.append(os.path.join(root, f))
    
    print(f"Found {len(files_to_process)} CSV files.")
    
    for path in files_to_process:
        filename = os.path.basename(path)
        print(f"Processing: {filename}")
        
        parts, amphoe, tambon, unit, station_id, election_type, category = pipeline.extract_info(path)
        if not parts:
            print(f"Could not extract info from filename: {filename}")
            continue
            
        station_info = {
            'amphoe': amphoe, 'tambon': tambon, 
            'unit': unit, 'station_id': station_id
        }

        # 2. สร้างโครงสร้างพื้นฐานก่อน (เรียกทุกครั้งเพื่อให้แน่ใจว่า node ปลายทางมีอยู่)
        pipeline.add_station(amphoe, tambon, unit, station_id)

        # 3. แยกตามประเภทไฟล์
        if category == 'check':
            pipeline.load_check_data(path, election_type, station_info)
        elif category == 'ผลคะแนน':
            pipeline.load_score_data(path, election_type, station_id)

    pipeline.close()
    print("--- All Data Loaded Successfully ---")


if __name__ == "__main__":
    # ใส่ชื่อโฟลเดอร์ที่เก็บไฟล์ CSV ของคุณ
    folder_path = input("Enter the folder path containing the CSV files: ").strip()
    if not folder_path:
        folder_path = "res" # Default
    run_pipeline(folder_path, FIRST=True)
