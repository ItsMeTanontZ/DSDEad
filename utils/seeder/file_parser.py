import os
from .models import ElectionMetadata

class FileParser:
    @staticmethod
    def parse_file_info(root: str, filename: str, base_dir: str) -> ElectionMetadata:
        # Pattern: Province_Area_Detail_Type_Filetype.csv
        name = filename.replace(".csv", "")
        parts = name.split("_")
        
        if len(parts) < 5:
            return None
        is_outside = "ล่วงหน้านอกเขตและนอกราชอาณาจักร" == parts[2]
                
        province = parts[0].replace("จังหวัด", "")
        area = parts[1].replace("เขตเลือกตั้งที่", "").replace("เขตเลือกตั้ง", "").replace("เขต", "")   
        election_type = parts[-2]
        file_type = parts[-1]
        
        if is_outside:
            print('yes')
            district = ""
            subdistrict = ""
            unit = parts[-3].replace("ชุดที่", "")
        else:
            district = parts[2].replace("อำเภอ", "")
            subdistrict = parts[3].replace("ตำบล", "").replace("เทศบาล", "")
            unit = parts[4].replace("หน่วยที่", "")
            
        
        return ElectionMetadata(
            file_type = file_type.strip(),
            election_type = election_type.strip(),
            unit = unit.strip(),
            subdistrict = subdistrict.strip(),
            district = district.strip(),

            location_type = "ล่วงหน้านอกเขตและนอกราชอาณาจักร" if is_outside else "ในประเทศ",
            
            area = area.strip(),
            province = province.strip(),
            year = "2566", # Default year
        )
