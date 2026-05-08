from sqlalchemy import Column, String, DateTime, func
from .models import Base

class ProcessedFile(Base):
    __tablename__ = "processed_files"

    filename = Column(String(255), primary_key=True)
    processed_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"filename: {self.filename}, processed_at: {self.processed_at}"
