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
