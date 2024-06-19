from shotglass2.takeabeltof.database import SqliteTable
from shotglass2.takeabeltof.utils import cleanRecordID
from shotglass2.takeabeltof.date_utils import local_datetime_now, getDatetimeFromString
from shotglass2.takeabeltof.file_upload import FileUpload
from datetime import datetime, timezone
import pytz


class LogEntry(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'log_entry' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'entry_date'
        self.defaults = {
            'entry_date':str(local_datetime_now()),
            'entry_UTC_date':str(datetime.now(timezone.utc)),
        }
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'location_name' TEXT,
            'entry_type' TEXT,
            'entry_date' DATETIME,
            'entry_UTC_date' DATETIME,
            'memo' TEXT,
            'lat' REAL,
            'lng' REAL,
            'odometer' INT,
            'state_of_charge' INT,
            'cost' REAL,
            'trip_id' INTEGER REFERENCES trip(id) ON DELETE CASCADE
            """
        super().create_table(sql)

        
    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
    
        column_list = []
        
        # column_list = [
        #     {'name':'fuel_added','definition':'REAL',}
        # ]
        
        return column_list
    
    def get(self, key):
        sql = f"""select *, 
        coalesce(log_photo.id,0) as log_photo_id,
        null as photo_list
        from {self.table_name}
        left join log_photo on log_photo.log_entry_id = {self.table_name}.id
        where {self.table_name}.id = {cleanRecordID(key)}
        order by {self.order_by_col}
        """
        rec = self._single_row(self.query(sql))
        if rec:
            # get log_photo records as list
            rec.photo_list = LogPhoto(self.db).select(where=f'log_entry_id={rec.id}',)

        return rec
        
    
    def update(self, rec, form, save=False) -> None:
        """
        Update the record with the contents of the form

        In the case of the LogEntry table we need to update the entry_UTC_date
        filed to it's equivelent at UTC so that we can order the entryies
        in the same order they actually occured regardless of the time zone
        at the time of entry.

        Arguments:
            rec -- A DataRow object
            form -- The request.form object

        Keyword Arguments:
            save -- If True, save the record after validating the input (default: {False})

        Returns:
            None
        """
        # import pdb;pdb.set_trace()
        old = self.get(rec.id)
        if old:
            form_entry_date = getDatetimeFromString(form.get('entry_date'))
            # Did the entry_date change?
            if form_entry_date != getDatetimeFromString(old.entry_date):
                # set entry_UTC_date to the UTC equivelent for the entry_date
                rec.entry_UTC_date = form_entry_date.astimezone(pytz.utc)
        else:
            rec.entry_UTC_date = datetime.utcnow()

        return super().update(rec, form, save)
    

class Trip(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'trip' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'lower(name)'
        self.defaults = {
                'creation_date':local_datetime_now(),
                'current_trip_date':datetime.utcnow(),
                }
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'name' TEXT,
            'creation_date' DATETIME NOT NULL,
            'current_trip_date' DATETIME NOT NULL,
            'battery_health' INT,
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
    
    def save(self, rec, **kwargs) -> None:
        """
        Special handling for the Trip record

        Set the current_trip_date field to the current UTC datetime 
        prior to save.

        Arguments:
            rec -- DataRow record

        Returns:
            None
        """
        rec.current_trip_date = datetime.utcnow()
        return super().save(rec, **kwargs)
    

class Vehicle(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'vehicle' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'lower(name)'
        self.defaults = {'battery_health':100,}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'name' TEXT,
            'fuel_type' TEXT,
            'fuel_capacity' INT,
            'battery_health' INT DEFAULT 100,
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
    
class FuelType(SqliteTable):
    """
    Create a temporary table to hold the vehicle types

    Vehicle types are defined here.

    Arguments:
        SqliteTable -- Basic table

    Returns:
        Nothing
    """

    TABLE_IDENTITY = 'vehicle_type'

    def __init__(self,db_connection):
            super().__init__(db_connection)
            self.table_name = self.TABLE_IDENTITY
            self.order_by_col = 'lower(name)'
            self.defaults = {}

    def create_table(self):

        sql = f"""
            drop table if exists {self.table_name}
        """
        self.db.execute(sql)
        sql=f"""
            CREATE TEMPORARY TABLE {self.table_name} (
            'id' INTEGER NOT NULL PRIMARY KEY,
            'name' TEXT
            )
        """
        self.db.execute(sql)

        self.db.execute(f"INSERT INTO {self.table_name} ('name') VALUES ('Electric')")
        self.db.execute(f"INSERT INTO {self.table_name} ('name') VALUES ('Gas')")
        self.db.execute(f"INSERT INTO {self.table_name} ('name') VALUES ('Human')")
        self.db.commit()
        


class LogPhoto(SqliteTable):
    """Handle some basic interactions this table"""

    TABLE_IDENTITY = 'log_photo' # so we can get the table name before the app starts up

    def __init__(self,db_connection):
        super().__init__(db_connection)
        self.table_name = self.TABLE_IDENTITY
        self.order_by_col = 'id'
        self.defaults = {}
        
    def create_table(self):
        """Define and create a table"""
        
        sql = """
            'title' TEXT,
            'caption' TEXT,
            'path' TEXT,
            'log_entry_id' INT REFERENCES log_entry(id) ON DELETE CASCADE
            """
        super().create_table(sql)


    def delete(self,id):
        """Delete the specified record and the associated image file"""

        id = cleanRecordID(id)
        if id:
            row = self.get(id)
            if super().delete(id):
                FileUpload().remove_file(row.path)
                return True
        return False
        

    @property
    def _column_list(self):
        """A list of dicts used to add fields to an existing table.
        """
        
        # {'name':'expires','definition':'DATETIME',},
        column_list = [
        
        ]
        
        return column_list

def create_triggers(db) -> None:
    """
    Create any triggers needed.

    May referenc any tables in the database

    Arguments:
        db -- The Sqlite database connection object
    """
    
    # Update the trip date when the log_entry changes
    db.execute("""
            CREATE TRIGGER IF NOT EXISTS update_trip_mod_date UPDATE ON log_entry 
            BEGIN
                UPDATE trip SET current_trip_date = datetime('now') WHERE trip.id = new.trip_id;
            END
    """)
    db.execute("""
            CREATE TRIGGER IF NOT EXISTS insert_trip_mod_date INSERT ON log_entry 
            BEGIN
                UPDATE trip SET current_trip_date = datetime('now') WHERE trip.id = new.trip_id;
            END
    """)

    # Could not get this trigger to work because apparently you can't update in a trigger on the
    # same record you are updating... which makes a lot of sense.
    # # Update the UTC date on entry log to coinside with the event date
    # db.execute("""
    #         CREATE TRIGGER IF NOT EXISTS update_log_entry_UTC_date UPDATE ON log_entry 
    #         BEGIN
    #             UPDATE log_entry SET entry_UTC_date = datetime(entry_date,'utc') WHERE log_entry.id = new.id;
    #         END
    # """)


def init_db(db):
    """Create Tables."""
    l = globals().copy()
    for n,o in l.items():
        if type(o) == type and \
            issubclass(o,SqliteTable) and \
            o != SqliteTable:
    
            o(db).init_table()

    create_triggers(db)
