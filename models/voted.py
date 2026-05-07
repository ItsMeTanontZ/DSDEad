# Voted(LocationKey (FK), ElectionType (แบ่งเขต / บัญชีรายชื่อ), CandidateKey (FK - ถ้าเป็นบัญชีรายชื่อให้เป็น Null), PartyKey (FK), คะแนนที่ได้ (จำนวน))
from sqlalchemy import Column, UUID, DateTime, ForeignKey, Integer, String, Text, func
from .models import Base
class Voted(Base):
    __tablename__ = "Voted"

    vid = Column(Integer, primary_key=True)
    location_key = Column(Integer, ForeignKey("Location.lid"))
    election_type = Column(String(50), required=True)  # แบ่งเขต / บัญชีรายชื่อ
    # แบบแบ่งเขต
    candidate_key = Column(UUID, ForeignKey("Candidate.cid"), nullable=True) # ถ้าเป็นบัญชีรายชื่อให้เป็น Null
    # แบบบัญชีรายชื่อ
    party_key = Column(Integer, ForeignKey("Party.pid"), nullable=True)
    
    votes_received = Column(Integer, required=True) # คะแนนที่ได้ (จำนวน)
    
    def __repr__(self):
        return f"id: {self.vid}, location_key: {self.location_key}, election_type: {self.election_type}, candidate_key: {self.candidate_key}, party_key: {self.party_key}, votes_received: {self.votes_received}"