from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, Integer, Boolean, func
from .models import Base
from typing import List

class Candidate(Base):
    __tablename__ = "Candidate"

    cid = Column(UUID, primary_key=True)
    candidate_number = Column(Integer, required=True) # หมายเลขผู้สมัคร
    name = Column(String(60), required=True) # ชื่อผู้สมัคร
    party_number = Column(Integer, ForeignKey("Party.pid")) # หมายเลขพรรค(FK)

    def __repr__(self):
        return f"id: {self.cid}, candidate_number: {self.candidate_number}, name: {self.name}, party_number: {self.party_number}"