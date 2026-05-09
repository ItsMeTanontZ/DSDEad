# Data Setup

1. Download the data from this Google Drive folder:
	https://drive.google.com/drive/folders/1koDp6abqLT2f-DARW--qWqO2onlTCWIy

2. Extract the downloaded files so the directory structure looks something like this:

```text
res/
└─ เขตเลือกตั้งที่ 9/
└─ เขตเลือกตั้งที่ 10/
```

3. Here are the files that were processed by OCR and physical checking: https://drive.google.com/drive/u/1/folders/1IULVfLQ8wRmJnx-fI3V9O9B4Yyvjiymm

เขตนี้มีทั้งหมด 470 ไฟล์

Usage Instructions

  create python venv using "python -m venv .venv" then make sure it run on your .venv

  using this command ".venv/Scripts/activate"

  run "docker compose up -d --build"
  
  run "pip install -r requirements.txt"
  
  then
  
  Initialize the database:

  This will create all the necessary tables in your PostgreSQL instance.
  
   1 python seed.py --init

  Seed new data:

  First check your .env to have correct path lead to data file it should be a folder before /provinces/
  
  Run this whenever you add new CSV files to your directory. It will only process the new ones.
  
   1 python seed.py --workers 1

  !!!only use --workers 1 if you put more than that it will freeze idk why I'm so sorry TT!!! 

  Delete data by filename:

  If you need to remove the data from a specific file (e.g., to re-import it after a correction):

   1 python seed.py --delete "อำเภออมก๋อย_ตำบลนาเกียน_หน่วยที่1_แบบบัญชีรายชื่อ_ผลคะแนน.csv"

  Configuration
  
  The script automatically reads your settings from config.py and .env. Ensure your .env contains:
  
   * DB_URL: Your PostgreSQL connection string.
  
   * DATA_DIR: The path to your res/csv folder.

  Your database is now ready to handle large-scale imports with built-in protection against duplicates and an easy way to manage specific
  files.
