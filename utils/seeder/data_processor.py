import pandas as pd
import uuid
from models import Party, Candidate, ElectionStatistic, Voted
from .models import ElectionMetadata
from .db_manager import DatabaseManager

class DataProcessor:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def process(self, session, file_path: str, meta: ElectionMetadata, filename: str):
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        location = self.db.get_or_create_location(session, meta)
        
        if meta.file_type == "check":
            self._process_check(session, df, meta, location, filename)
        elif meta.file_type == "ผลคะแนน":
            self._process_scores(session, df, meta, location, filename)

    def _process_check(self, session, df, meta, location, filename):
        data = dict(zip(df['รายการ'], df['ตัวเลข']))
        stat = ElectionStatistic(
            location_key=location.lid,
            type=meta.election_type,
            total_voters=int(data.get('จำนวนผู้มีสิทธิเลือกตั้งตามบัญชีรายชื่อผู้มีสิทธิเลือกตั้ง', 0)),
            voters_turnout=int(data.get('จำนวนผู้มีสิทธิเลือกตั้งที่มาแสดงตน', 0)),
            valid_ballots=int(data.get('บัตรดี', 0)),
            invalid_ballots=int(data.get('บัตรเสีย', 0)),
            blank_ballots=int(data.get('บัตรที่ไม่เลือกบัญชีรายชื่อของพรรคการเมืองใด', data.get('บัตรที่ไม่เลือกผู้สมัครผู้ใด', 0))),
            remaining_ballots=int(data.get('บัตรเลือกตั้งที่เหลือ', 0)),
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
        party_num = int(row['หมายเลข'])
        party_name = row['ชื่อพรรค']
        
        party = session.query(Party).filter(Party.pid == party_num).first()
        if not party:
            party = Party(pid=party_num, name=party_name)
            session.add(party)
            session.flush()
        
        voted = Voted(
            location_key=location.lid,
            election_type=meta.election_type,
            party_key=party.pid,
            votes_received=int(row['คะแนน']),
            source_file=filename
        )
        session.add(voted)

    def _handle_candidate_score(self, session, row, location, meta, filename):
        cand_num = int(row['หมายเลข'])
        cand_name = row['ชื่อผู้สมัคร']
        party_name = row['พรรค']
        
        party = session.query(Party).filter(Party.name == party_name).first()
        candidate = session.query(Candidate).filter(
            Candidate.name == cand_name, 
            Candidate.candidate_number == cand_num
        ).first()
        
        if not candidate:
            candidate = Candidate(
                cid=uuid.uuid4(),
                candidate_number=cand_num,
                name=cand_name,
                party_number=party.pid if party else None
            )
            session.add(candidate)
            session.flush()
        
        voted = Voted(
            location_key=location.lid,
            election_type=meta.election_type,
            candidate_key=candidate.cid,
            votes_received=int(row['คะแนน']),
            source_file=filename
        )
        session.add(voted)
