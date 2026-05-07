from sqlalchemy import UUID, Column, DateTime, String, Integer, Boolean, func
from .models import Base
from typing import List

class Party(Base):
    __tablename__ = "Party"

    pid = Column(Integer, primary_key=True) #หมายเลขพรรค
    name = Column(String(60), required=True) # ชื่อพรรค
    
    def __repr__(self):
        return f"id: {self.pid}, name: {self.name}"