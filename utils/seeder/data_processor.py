import pandas as pd
import uuid
from models import Party, Candidate, ElectionStatistic, Voted
from .models import ElectionMetadata
from .db_manager import DatabaseManager

class DataProcessor:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def _safe_int(self, value):
        """Safely convert OCR value to integer, handling commas and errors."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0
        try:
            # Remove commas and whitespace
            clean_val = str(value).replace(",", "").strip()
            if not clean_val:
                return 0
            return int(float(clean_val)) # Handle "1.0" or "10"
        except (ValueError, TypeError):
            return 0

    def process(self, session, file_path: str, meta: ElectionMetadata, filename: str):
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        location, location_type = self.db.get_or_create_location(session, meta)
        
        if meta.file_type == "check":
            self._process_check(session, df, meta, location, filename, location_type)
        elif meta.file_type == "ผลคะแนน":
            self._process_scores(session, df, meta, location, filename)

    def _process_check(self, session, df, meta, location, filename, location_type):
        data = dict(zip(df['รายการ'], df['ตัวเลข']))
        if location_type:
            voter_turnout = self._safe_int(data.get('บัตรดี', 0)) + self._safe_int(data.get('บัตรเสีย', 0)) + self._safe_int(data.get('บัตรที่ไม่เลือกบัญชีรายชื่อของพรรคการเมืองใด', 
                             data.get('บัตรที่ไม่เลือกผู้สมัครผู้ใด', 
                             data.get('บัตรไม่เลือกใคร', 0))))
            total_voters = voter_turnout
        else:
            voter_turnout = self._safe_int(data.get('จำนวนผู้มีสิทธิเลือกตั้งที่มาแสดงตน', data.get('จำนวนผู้มาแสดงตน', 0))),
            total_voters = self._safe_int(data.get('จำนวนผู้มีสิทธิเลือกตั้งตามบัญชีรายชื่อผู้มีสิทธิเลือกตั้ง', data.get('จำนวนผู้มีสิทธิเลือกตั้ง', 0)))
        stat = ElectionStatistic(
            location_key=location.lid,
            type=meta.election_type,
            total_voters=total_voters,
            voters_turnout=voter_turnout,
            valid_ballots=self._safe_int(data.get('บัตรดี', 0)),
            invalid_ballots=self._safe_int(data.get('บัตรเสีย', 0)),
            blank_ballots=self._safe_int(data.get('บัตรที่ไม่เลือกบัญชีรายชื่อของพรรคการเมืองใด', 
                             data.get('บัตรที่ไม่เลือกผู้สมัครผู้ใด', 
                             data.get('บัตรไม่เลือกใคร', 0)))),
            remaining_ballots=self._safe_int(data.get('บัตรเลือกตั้งที่เหลือ', data.get('บัตรเหลือ', 0))),
            source_file=filename
        )
        session.add(stat)

    def _process_scores(self, session, df, meta, location, filename):
        if meta.election_type == "แบบบัญชีรายชื่อ":
            for _, row in df.iterrows():
                self._handle_party_score(session, row, location, meta, filename)
        else:
            for _, row in df.iterrows():
                self._handle_candidate_score(session, row, location, meta, filename)

    def _handle_party_score(self, session, row, location, meta, filename):
        party_num = self._safe_int(row['หมายเลข'])
        party_name = str(row['ชื่อพรรค']).strip()
        
        party = self.db.get_or_create_party(session, party_num, party_name)
        
        voted = Voted(
            location_key=location.lid,
            election_type=meta.election_type,
            party_key=party.pid,
            votes_received=self._safe_int(row['คะแนน']),
            source_file=filename
        )
        session.add(voted)

    def _handle_candidate_score(self, session, row, location, meta, filename):
        cand_num = self._safe_int(row['หมายเลข'])
        cand_name = str(row['ชื่อผู้สมัคร']).strip()
        party_name = str(row['พรรค']).strip()
        
        # Try to find party with exact name, then normalized name
        party = session.query(Party).filter(Party.name == party_name).first()
        if not party:
            # Normalize: strip "พรรค" and search
            clean_name = party_name.replace("พรรค", "").strip()
            party = session.query(Party).filter(Party.name.like(f"%{clean_name}%")).first()

        candidate = self.db.get_or_create_candidate(
            session, 
            name=cand_name, 
            number=cand_num, 
            party_pid=party.pid if party else None
        )
        
        voted = Voted(
            location_key=location.lid,
            election_type=meta.election_type,
            candidate_key=candidate.cid,
            votes_received=self._safe_int(row['คะแนน']),
            source_file=filename
        )
        session.add(voted)
