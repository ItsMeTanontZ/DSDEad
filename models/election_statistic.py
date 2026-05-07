from sqlalchemy import Column, UUID, DateTime, ForeignKey, Integer, String, Text, func
from .models import Base


class ElectionStatistic(Base):
    __tablename__ = "ElectionStatistic"

    id = Column(Integer, primary_key=True)
    location_key = Column(String(120), ForeignKey("Location.lid"))
    type = Column(String(50), nullable=False)  # แบบแบ่งเขต / แบบบัญชีรายชื่อ
    total_voters = Column(Integer, nullable=False) # จำนวนผู้มีสิทธิ์
    voters_turnout = Column(Integer, nullable=False) # จำนวนผู้มาแสดงตน
    valid_ballots = Column(Integer, nullable=False) # จำนวนบัตรดี
    invalid_ballots = Column(Integer, nullable=False) # จำนวนบัตรเสีย
    blank_ballots = Column(Integer, nullable=False) # จำนวนบัตรไม่เลือกใคร
    remaining_ballots = Column(Integer, nullable=False) # จำนวนบัตรเหลือ
    source_file = Column(String(255), nullable=True) # ชื่อไฟล์ที่มา
    
    def __repr__(self):
        return f"id: {self.id}, location_key: {self.location_key}, type: {self.type}, source_file: {self.source_file}"
