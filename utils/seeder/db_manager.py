from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Location, Party, Candidate, ElectionStatistic, Voted, ProcessedFile
from .models import ElectionMetadata

class DatabaseManager:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        return self.SessionLocal()

    def get_or_create_location(self, session, meta: ElectionMetadata):
        lid = f"{meta.year}-{meta.province}-{meta.area}-{meta.district}-{meta.subdistrict}-{meta.unit}"
        location = session.query(Location).filter(Location.lid == lid).first()
        if not location:
            location = Location(
                lid=lid,
                year=meta.year,
                province=meta.province,
                area=meta.area,
                district=meta.district,
                subdistrict=meta.subdistrict,
                unit=meta.unit
            )
            session.add(location)
            session.flush()
        return location

    def is_file_processed(self, session, filename: str):
        return session.query(ProcessedFile).filter(ProcessedFile.filename == filename).first() is not None

    def mark_file_processed(self, session, filename: str):
        processed = ProcessedFile(filename=filename)
        session.add(processed)

    def delete_by_filename(self, filename: str):
        session = self.get_session()
        try:
            session.query(ElectionStatistic).filter(ElectionStatistic.source_file == filename).delete()
            session.query(Voted).filter(Voted.source_file == filename).delete()
            session.query(ProcessedFile).filter(ProcessedFile.filename == filename).delete()
            session.commit()
            print(f"Successfully deleted data for {filename}")
        except Exception as e:
            session.rollback()
            print(f"Error deleting data for {filename}: {e}")
        finally:
            session.close()
