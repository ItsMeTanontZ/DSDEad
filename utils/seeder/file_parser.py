import os
from .models import ElectionMetadata

class FileParser:
    @staticmethod
    def parse_file_info(root: str, filename: str, base_dir: str) -> ElectionMetadata:
        # Expected pattern: จังหวัด_เขตเลือกตั้ง_อำเภอ_ตำบล_type_(check or ผลคะแนน).csv
        # Note: If 'unit' is also there, it might be: จังหวัด_เขตเลือกตั้ง_อำเภอ_ตำบล_หน่วย_type_filetype.csv
        parts = filename.replace(".csv", "").split("_")
        
        if len(parts) < 5:
            return None
        
        # Clean up common prefixes
        province = parts[0].replace("จังหวัด", "")
        area = parts[1].replace("เขตเลือกตั้งที่", "").replace("เขตเลือกตั้ง", "").replace("เขต", "")
        district = parts[2].replace("อำเภอ", "")
        subdistrict = parts[3].replace("ตำบล", "")
        
        # Handle cases with or without 'unit'
        if len(parts) >= 7:
            # จังหวัด_เขต_อำเภอ_ตำบล_หน่วย_type_filetype
            unit = parts[4].replace("หน่วยที่", "").replace("หน่วย", "")
            election_type = parts[5]
            file_type = parts[6]
        elif len(parts) == 6:
            # จังหวัด_เขต_อำเภอ_ตำบล_type_filetype
            unit = "1" # Default if not specified
            election_type = parts[4]
            file_type = parts[5]
        else:
            # Fallback for 5 parts (old format or similar)
            unit = parts[2].replace("หน่วยที่", "").replace("หน่วย", "")
            election_type = parts[3]
            file_type = parts[4]
            # In this case, province/area might be defaults if only 5 parts
            province = "เชียงใหม่"
            area = "10"

        return ElectionMetadata(
            district=district.strip(),
            subdistrict=subdistrict.strip(),
            unit=unit.strip(),
            election_type=election_type.strip(),
            file_type=file_type.strip(),
            year="2566", # Default year
            province=province.strip(),
            area=area.strip()
        )
