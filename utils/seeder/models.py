from dataclasses import dataclass

@dataclass
class ElectionMetadata:
    district: str
    subdistrict: str
    unit: str
    election_type: str
    file_type: str
    year: str
    province: str
    area: str

@dataclass
class ProcessingError:
    filename: str
    error: str
    path: str
