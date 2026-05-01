# Data Setup

1. Download the data from this Google Drive folder:
	https://drive.google.com/drive/folders/1koDp6abqLT2f-DARW--qWqO2onlTCWIy

2. Extract the downloaded files so the directory structure looks like this:

```text
res/
└─ เขตเลือกตั้งที่ 10/
```
เขตนี้มีทั้งหมด 470 ไฟล์

ขั้นตอนการใช้

1. pip install -r requirements.txt

2. docker compose up -d --build (to stop use "docker compose down" or "docker compose stop")