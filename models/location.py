from sqlalchemy import UUID, Column, DateTime, String, Integer, Boolean, func
from .models import Base
from typing import List

class Location(Base):
    __tablename__ = "Location"

    lid = Column(String(120), primary_key=True) # ปี-จังหวัด-เขต-อำเภอ-ตำบล(เทศบาล-ถ้าก็มี)-หน่วย
    year = Column(String(60), nullable=False) # ปี
    province = Column(String(60), nullable=False) # จังหวัด
    area = Column(String(60), nullable=False)     # เขตเลือกตั้ง
    unit = Column(String(60), nullable=False)     # หน่วยที่ or ชุดที่ (สำหรับนอกเขต)
    
    # Single Table Inheritance discriminator
    location_type = Column(String(50))

    # Domestic-specific fields made nullable for STI
    district = Column(String(60), nullable=True) # อำเภอ
    subdistrict = Column(String(60), nullable=True) # ตำบล(เทศบาล-ถ้าก็มี)

    __mapper_args__ = {
        'polymorphic_on': location_type,
        'polymorphic_identity': 'ในเขต'
    }

    def __repr__(self):
        return f"id: {self.lid}, type: {self.location_type}, year: {self.year}, province: {self.province}, area: {self.area}"