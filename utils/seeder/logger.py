import datetime
import os

class FailureLogger:
    def __init__(self, log_path: str = "seeding_failures.log"):
        self.log_path = log_path

    def log_failure(self, filename: str, path: str, error: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] FILE: {filename} | PATH: {path} | ERROR: {error}\n"
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        print(f"Logged failure for {filename}")

    def clear_log(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
