import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from .db_manager import DatabaseManager
from .file_parser import FileParser
from .data_processor import DataProcessor
from .logger import FailureLogger
from config import DB_URL, DATA_DIR

class ElectionSeeder:
    def __init__(self, max_workers: int = 4):
        self.db = DatabaseManager(DB_URL)
        self.processor = DataProcessor(self.db)
        self.parser = FileParser()
        self.logger = FailureLogger()
        self.max_workers = max_workers

    def run(self):
        if not os.path.exists(DATA_DIR):
            print(f"Error: DATA_DIR {DATA_DIR} does not exist.")
            return

        files_to_process = []
        for root, _, files in os.walk(DATA_DIR):
            for filename in files:
                if filename.endswith(".csv"):
                    files_to_process.append((root, filename))

        # Sort files to prioritize party list score files so Party table is populated first
        # files with "แบบบัญชีรายชื่อ_ผลคะแนน" should come before "แบบแบ่งเขต_ผลคะแนน"
        def sort_key(file_info):
            root, filename = file_info
            if "แบบบัญชีรายชื่อ_ผลคะแนน" in filename:
                return 0
            if "แบบบัญชีรายชื่อ" in filename:
                return 1
            return 2

        files_to_process.sort(key=sort_key)

        print(f"Found {len(files_to_process)} CSV files. Starting parallel processing...")
        
        # We use a ThreadPoolExecutor for parallel processing
        # Note: Since each task handles its own DB session and commit, 
        # it is thread-safe as long as the DB engine supports it.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_file_task, root, filename): filename 
                for root, filename in files_to_process
            }
            
            for future in as_completed(future_to_file):
                filename = future_to_file[future]
                try:
                    future.result()
                except Exception as exc:
                    print(f'{filename} generated an unexpected exception: {exc}')

    def _process_file_task(self, root, filename):
        # Create a new session for each thread to ensure thread safety
        session = self.db.get_session()
        try:
            if self.db.is_file_processed(session, filename):
                print(f"Skipping {filename}, already processed.")
                return

            meta = self.parser.parse_file_info(root, filename, DATA_DIR)
            if not meta:
                print(f"Could not parse filename: {filename}")
                return

            file_path = os.path.join(root, filename)
            self.processor.process(session, file_path, meta, filename)
            self.db.mark_file_processed(session, filename)
            session.commit()
            print(f"Successfully processed {filename}")
        except Exception as e:
            session.rollback()
            self.logger.log_failure(filename, root, str(e))
        finally:
            session.close()

    def fix_candidate_parties(self):
        """Scan all processed score files to fix null party_numbers for existing candidates."""
        import pandas as pd
        from models import Candidate, Party
        print("Starting candidate-party relinking process...")
        session = self.db.get_session()
        try:
            # Find candidates with missing party_number
            candidates = session.query(Candidate).filter(Candidate.party_number == None).all()
            if not candidates:
                print("No candidates with missing party numbers found.")
                return

            print(f"Found {len(candidates)} candidates with missing party numbers.")
            
            # Map candidate name+number to their objects for quick lookup
            cand_map = {f"{c.name}_{c.candidate_number}": c for c in candidates}
            print(cand_map.keys())
            # Scan all CSV files in DATA_DIR
            for root_dir, _, files in os.walk(DATA_DIR):
                for filename in files:
                    if filename.endswith(".csv") and "ผลคะแนน" in filename:
                        # We only care about score files that might contain party info
                        file_path = os.path.join(root_dir, filename)
                        df = pd.read_csv(file_path, encoding='utf-8-sig')
                        
                        # We need both 'ชื่อผู้สมัคร' and 'พรรค' columns (แบบแบ่งเขต format)
                        if 'ชื่อผู้สมัคร' in df.columns and 'พรรค' in df.columns:
                            for _, row in df.iterrows():
                                name = str(row['ชื่อผู้สมัคร']).strip()
                                num_str = str(row['หมายเลข']).replace(",", "").strip()
                                try:
                                    num = int(float(num_str))
                                except:
                                    continue
                                    
                                party_name = str(row['พรรค']).strip()
                                
                                key = f"{name}_{num}"
                                print(f"Checking candidate: {key} with party '{party_name}'")
                                if key in cand_map:
                                    print(True)
                                    # Found a candidate that needs a fix!
                                    clean_party = party_name.replace("พรรค", "").strip()
                                    print(f"Looking for party: {clean_party}")
                                    party = session.query(Party).filter(Party.name.like(f"%{clean_party}%")).first()
                                    
                                    if party:
                                        print(True)
                                        cand_map[key].party_number = party.pid
                                        print(f"Fixed: {name} ({num}) -> {party.name}")
            
            session.commit()
            print("Relinking complete.")
        except Exception as e:
            session.rollback()
            print(f"Error during relinking: {e}")
        finally:
            session.close()
