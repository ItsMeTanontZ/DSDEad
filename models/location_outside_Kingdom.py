from sqlalchemy import Column, String
from .location import Location

class LocationOutsideKingdom(Location):
    __mapper_args__ = {
        'polymorphic_identity': 'outside_kingdom'
    }
    
    def __repr__(self):
        return f"id: {self.lid}, type: {self.location_type}, year: {self.year}, province: {self.province}, area: {self.area}"
