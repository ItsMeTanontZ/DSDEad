import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import *
from .models import ElectionMetadata

class DatabaseManager:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.lock = threading.Lock()

    def init_db(self):
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        return self.SessionLocal()

    def get_or_create_location(self, session, meta: ElectionMetadata):
        # Infer if it's outside kingdom: empty district/subdistrict implies outside kingdom
        is_outside = not meta.district and not meta.subdistrict
        
        # Consistent lid generation: only join parts that exist
        parts = [meta.year, meta.province, meta.area]
        if not is_outside:
            parts.extend([meta.district, meta.subdistrict, meta.unit])
        else:
            parts.extend([meta.unit])  # For outside kingdom, unit is the last part before type/filetype
        lid = "-".join([str(p) for p in parts if p])
        
        with self.lock:
            # Polymorphic query
            location = session.query(Location).filter(Location.lid == lid).first()
            if not location:
                sp = session.begin_nested()
                try:
                    if is_outside:
                        location = LocationOutsideKingdom(
                            lid=lid,
                            year=meta.year,
                            province=meta.province,
                            area=meta.area,
                            unit=meta.unit
                        )
                    else:
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
                except Exception:
                    sp.rollback()
                    location = session.query(Location).filter(Location.lid == lid).first()
            return location, is_outside

    def get_or_create_party(self, session, pid: int, name: str):
        with self.lock:
            party = session.query(Party).filter(Party.pid == pid).first()
            if not party:
                sp = session.begin_nested()
                try:
                    party = Party(pid=pid, name=name)
                    session.add(party)
                    session.flush()
                except Exception:
                    sp.rollback()
                    party = session.query(Party).filter(Party.pid == pid).first()
            return party

    def get_or_create_candidate(self, session, name: str, number: int, party_pid: int = None):
        with self.lock:
            candidate = session.query(Candidate).filter(
                Candidate.name == name, 
                Candidate.candidate_number == number
            ).first()
            
            if not candidate:
                import uuid
                sp = session.begin_nested()
                try:
                    candidate = Candidate(
                        cid=uuid.uuid4(),
                        candidate_number=number,
                        name=name,
                        party_number=party_pid
                    )
                    session.add(candidate)
                    session.flush()
                except Exception:
                    sp.rollback()
                    candidate = session.query(Candidate).filter(
                        Candidate.name == name, 
                        Candidate.candidate_number == number
                    ).first()
            elif candidate.party_number is None and party_pid is not None:
                candidate.party_number = party_pid
                session.flush()
            
            return candidate

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
