from sqlalchemy import Column, UUID, DateTime, ForeignKey, Integer, String, Text, func
from .models import Base
class Voted(Base):
    __tablename__ = "Voted"

    vid = Column(Integer, primary_key=True)
    location_key = Column(String(120), ForeignKey("Location.lid"))
    election_type = Column(String(50), nullable=False)  # แบ่งเขต / บัญชีรายชื่อ
    # แบบแบ่งเขต
    candidate_key = Column(UUID, ForeignKey("Candidate.cid"), nullable=True) # ถ้าเป็นบัญชีรายชื่อให้เป็น Null
    # แบบบัญชีรายชื่อ
    party_key = Column(Integer, ForeignKey("Party.pid"), nullable=True)
    
    votes_received = Column(Integer, nullable=False) # คะแนนที่ได้ (จำนวน)
    source_file = Column(String(255), nullable=True) # ชื่อไฟล์ที่มา
    
    def __repr__(self):
        return f"id: {self.vid}, location_key: {self.location_key}, election_type: {self.election_type}, source_file: {self.source_file}"