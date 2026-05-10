from dataclasses import dataclass

@dataclass
class ElectionMetadata:
    file_type: str
    election_type: str
    unit: str
    subdistrict: str
    district: str

    location_type: str

    area: str
    province: str
    year: str


@dataclass
class ProcessingError:
    filename: str
    error: str
    path: str
