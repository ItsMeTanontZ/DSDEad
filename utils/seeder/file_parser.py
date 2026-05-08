import os
from .models import ElectionMetadata

class FileParser:
    @staticmethod
    def parse_file_info(root: str, filename: str, base_dir: str) -> ElectionMetadata:
        # Expected pattern: จังหวัด_เขตเลือกตั้ง_อำเภอ_ตำบล_หน่วย_type_filetype.csv
        parts = filename.replace(".csv", "").split("_")
        
        if len(parts) < 5:
            return None
        
        # Default fallback values
        province = "เชียงใหม่"
        area = "10"
        year = "2566"
        
        if len(parts) >= 7:
            # จังหวัด_เขต_อำเภอ_ตำบล_หน่วย_type_filetype
            province = parts[0].replace("จังหวัด", "")
            area = parts[1].replace("เขตเลือกตั้งที่", "").replace("เขตเลือกตั้ง", "").replace("เขต", "")
            district = parts[2].replace("อำเภอ", "")
            subdistrict = parts[3].replace("ตำบล", "")
            unit = parts[4].replace("หน่วยที่", "").replace("หน่วย", "")
            election_type = parts[5]
            file_type = parts[6]
        elif len(parts) == 6:
            # จังหวัด_เขต_อำเภอ_ตำบล_type_filetype
            province = parts[0].replace("จังหวัด", "")
            area = parts[1].replace("เขตเลือกตั้งที่", "").replace("เขตเลือกตั้ง", "").replace("เขต", "")
            district = parts[2].replace("อำเภอ", "")
            subdistrict = parts[3].replace("ตำบล", "")
            unit = "1"
            election_type = parts[4]
            file_type = parts[5]
        else:
            # Fallback for 5 parts: อำเภอ_ตำบล_หน่วย_type_filetype
            district = parts[0].replace("อำเภอ", "")
            subdistrict = parts[1].replace("ตำบล", "")
            unit = parts[2].replace("หน่วยที่", "").replace("หน่วย", "")
            election_type = parts[3]
            file_type = parts[4]

        return ElectionMetadata(
            district=district.strip(),
            subdistrict=subdistrict.strip(),
            unit=unit.strip(),
            election_type=election_type.strip(),
            file_type=file_type.strip(),
            year=year,
            province=province.strip(),
            area=area.strip()
        )
