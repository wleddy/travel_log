from shotglass2.takeabeltof.database import SqliteTable
from shotglass2.takeabeltof.utils import cleanRecordID
        
class TripSegment(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'trip_segment' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'segment_date DESC'
        self.defaults = {}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'location_name' TEXT,
            'segment_type' TEXT,
            'segment_date' DATETIME,
            'memo' TEXT,
            'longitude' REAL,
            'latitude' REAL,
            'odometer' INT,
            'projected_range' INT,
            'fuel_qty' REAL,
            'fuel_cost' REAL,
            'trip_id' INT,
            FOREIGN KEY (trip_id) REFERENCES trip(id) ON DELETE CASCADE
            """
        super().create_table(sql)
        
        
    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
    
        column_list = [
        
        ]
        
        return column_list
    

class Trip(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'trip' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'lower(name)'
        self.defaults = {}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'name' TEXT,
            'vehicle_id' INT,
             FOREIGN KEY (vehicle_id) REFERENCES vehicle(id) ON DELETE CASCADE
            """
        super().create_table(sql)
        
        
    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
    
        column_list = [
        
        ]
        
        return column_list
    

class Vehicle(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'vehicle' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'lower(name)'
        self.defaults = {}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'name' TEXT,
            'fuel_type' TEXT,
            'fuel_capacity' INT,
            'user_id' INT,
             FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
            """
        super().create_table(sql)
        
        
    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
        
        # {'name':'expires','definition':'DATETIME',},
        column_list = [
        
        ]
        
        return column_list
    
    
class TripPhoto(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'trip_photo' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'image_date'
        self.defaults = {}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'title' TEXT,
            'caption' TEXT,
            'image_date' DATETIME,
            'full' BLOB,
            'thumbnail' BLOB,
            'trip_segment_id' INT,
             FOREIGN KEY (trip_segment_id) REFERENCES trip_segment(id) ON DELETE CASCADE
            """
        super().create_table(sql)
        
        
    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
        
        # {'name':'expires','definition':'DATETIME',},
        column_list = [
        
        ]
        
        return column_list


def init_db(db):
    """Create Tables."""
    l = globals().copy()
    for n,o in l.items():
        if type(o) == type and \
            issubclass(o,SqliteTable) and \
            o != SqliteTable:
    
            o(db).init_table()
