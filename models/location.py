from sqlalchemy import UUID, Column, DateTime, String, Integer, Boolean, func
from .models import Base
from typing import List

class Location(Base):
    __tablename__ = "Location"

    lid = Column(String(120), primary_key=True) # ปี-จังหวัด-เขต-อำเภอ-ตำบล(เทศบาล-ถ้าก็มี)-หน่วย
    year = Column(String(60), nullable=False) # ปี
    province = Column(String(60), nullable=False) # จังหวัด
    area = Column(String(60), nullable=False)     # เขตเลือกตั้ง
    district = Column(String(60), nullable=False) # อำเภอ
    subdistrict = Column(String(60), nullable=False) # ตำบล(เทศบาล-ถ้าก็มี)
    unit = Column(String(60), nullable=False)     # หน่วยที่
    def __repr__(self):
        return f"id: {self.lid}, year: {self.year}, province: {self.province}, area: {self.area}, district: {self.district}, subdistrict: {self.subdistrict}, unit: {self.unit}"