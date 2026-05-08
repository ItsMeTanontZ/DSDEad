import os
import sys
sys.path.append(os.getcwd())
from dotenv import load_dotenv

load_dotenv(".env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
DB_URL = os.getenv("DB_URL")
DATA_DIR = os.getenv("DATA_DIR")
DATAPIC_DIR = os.getenv("DATAPIC_DIR")