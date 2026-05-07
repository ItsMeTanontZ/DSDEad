# Election_statistic(LocationKey (FK), type (แบบแบ่งเขต / แบบบัญชีรายชื่อ),จำนวนผู้มีสิทธิ์, จำนวนผู้มาแสดงตน, บัตรดี, บัตรเสีย, บัตรไม่เลือกใคร, บัตรเหลือ)
from sqlalchemy import Column, UUID, DateTime, ForeignKey, Integer, String, Text, func
from .models import Base


class ElectionStatistic(Base):
    __tablename__ = "ElectionStatistic"

    id = Column(Integer, primary_key=True)
    location_key = Column(Integer, ForeignKey("Location.lid"))
    type = Column(String(50), required=True)  # แบบแบ่งเขต / แบบบัญชีรายชื่อ
    total_voters = Column(Integer, required=True) # จำนวนผู้มีสิทธิ์
    voters_turnout = Column(Integer, required=True) # จำนวนผู้มาแสดงตน
    valid_ballots = Column(Integer, required=True) # จำนวนบัตรดี
    invalid_ballots = Column(Integer, required=True) # จำนวนบัตรเสีย
    blank_ballots = Column(Integer, required=True) # จำนวนบัตรไม่เลือกใคร
    remaining_ballots = Column(Integer, required=True) # จำนวนบัตรเหลือ
    
    def __repr__(self):
        return f"id: {self.id}, location_key: {self.location_key}, type: {self.type}, total_voters: {self.total_voters}, voters_turnout: {self.voters_turnout}, valid_ballots: {self.valid_ballots}, invalid_ballots: {self.invalid_ballots}, blank_ballots: {self.blank_ballots}, remaining_ballots: {self.remaining_ballots}"
