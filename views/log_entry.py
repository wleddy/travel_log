from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
import json
from shotglass2.mapping.views.maps import get_distance
from shotglass2.takeabeltof.file_upload import FileUpload
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device, get_rec_id_if_none
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.date_utils import date_to_string, local_datetime_now, getDatetimeFromString
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural
from werkzeug.exceptions import RequestEntityTooLarge

import travel_log.models as models
from travel_log.views import log_photo
from travel_log.views.travel_log import get_current_trip_id

from datetime import datetime, timedelta
import pytz
from timezonefinder import TimezoneFinder 


PRIMARY_TABLE = models.LogEntry
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY

mod = Blueprint(MOD_NAME,__name__, template_folder='templates/travel_log', url_prefix=f'/travel_log/{MOD_NAME}')

def setExits():
    g.listURL = url_for('.display')
    g.editURL = url_for('.edit')
    g.deleteURL = url_for('.display') + 'delete/'
    g.title = f'{PRIMARY_TABLE(g.db).display_name}'


# this handles table list and record delete
@mod.route('/<path:path>',methods=['GET','POST',])
@mod.route('/<path:path>/',methods=['GET','POST',])
@mod.route('/',methods=['GET','POST',])
@table_access_required(PRIMARY_TABLE)
def display(path=None):
    # import pdb;pdb.set_trace()
    setExits()
    return log_entry_list(path)

def log_entry_list(path=None,**kwargs):
    # this may be called from the travel_log module
    # import pdb;pdb.set_trace()
    view = TableView(PRIMARY_TABLE,g.db)
    view.delete = delete
    # optionally specify the list fields
    view.list_fields = [
        {'name':'id',},
        {'name':'location_name',},
        {'name':'entry_type',},
        {'name':'entry_date','type':'datetime','search':'datetime',},
        {'name':'memo'},
        ]
    
    return view.dispatch_request()
    

## Edit the PRIMARY_TABLE
@mod.route('/edit', methods=['POST', 'GET'])
@mod.route('/edit/', methods=['POST', 'GET'])
@mod.route('/edit/<int:rec_id>/', methods=['POST','GET'])
@table_access_required(PRIMARY_TABLE)
def edit(rec_id=None):
    setExits()
    g.title = "Edit {} Record".format(g.title)
    return edit_log(rec_id)

def edit_log(rec_id=None,**kwargs):
    # designed to be called from travel_log.py
    # Need to pre-fetch the log record so I can populate the form
    # The record may now include an image so test upload size
    # import pdb;pdb.set_trace()
    next = kwargs.get('next',g.listURL)
    try:
        rec_id = get_rec_id_if_none(rec_id)
        if rec_id < 0:
            flash("Record ID must be greater than 0")
            return redirect(next)
    except RequestEntityTooLarge as e:
        # This error is raised as soon as you try to access the request.form if too large
        flash("The image file you submitted was too large. Maximum size is {} MB".format(request.max_content_length/1048576))
        return redirect(next)
    except Exception as e:
        mes = (f"An unexpected error occured: {str(e)}")
        printException(mes,level='error',err=e)
        flash(mes)
        return redirect(next)
    
    rec = None
    table =  PRIMARY_TABLE(g.db)
    if rec_id == 0:
        rec = table.new()
    else:
        rec = table.get(rec_id)
        if rec is None:
            flash("Record Not Found")
            return g.listURL
        if request.form:
            table.update(rec,request.form)
        if not rec.entry_date:
            rec.entry_date = local_datetime_now()
 
    view = EditView(PRIMARY_TABLE,g.db,rec_id)

    if is_mobile_device():
        view.use_anytime_date_picker = False

    # Set the trip id for new records
    if not view.rec.trip_id:
        view.rec.trip_id = get_current_trip_id()

    view.edit_fields = get_edit_field_list(rec)
    if view.edit_fields is None:
        return redirect(next)

    # convert the Trip select input to hidden and diaplay the trip name as text
    trip = models.Trip(g.db).get(view.rec.trip_id)
    if trip and view.edit_fields[0]['name'] == 'trip_id':
        # hide the trip type picker
        view.edit_fields[0]['type'] = 'hidden'
        view.edit_fields.insert(0,{'name':'header','raw':True,'content':f'<h4 class="w3-secondary-color w3-center w3-bar">{trip.name}</h4><hr/>'})

    view.base_layout = "travel_log/form_layout.html"
    view.delete = delete
    # Some methods in view you can override
    view.validate_form = validate_form 

    view.use_anytime_date_picker = not is_mobile_device()
    if not view.next:
        view.next = kwargs.get("next",'')

     # Process the form?
    if request.form and view.success:
        # import pdb;pdb.set_trace()
        # Update -> Validate -> Save...
        view.update(save_after_update=True)
        if view.success:
            # save the image file if one exists
            # import pdb;pdb.set_trace()
            # log_photo module will try to save the file and create an image record
            # if any errors are encountered it will flash them
            upload = log_photo.save_photo_to_disk(view.rec.id,'log_photo')
            if upload.success:
                images = models.LogPhoto(g.db)
                image_rec = images.new()
                image_rec.path = upload.saved_file_path_string
                image_rec.log_entry_id = view.rec.id
                images.save(image_rec,commit=True)

            #if user clicked "Save and continue", redisplay this form
            if 'add_log_photo' in request.form:
                view.next = url_for("travel_log.edit_log") + str(view.rec.id)

            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)
            
    #else display the form
    return view.render()


def delete(view):
    """ensure that image files are deleted when deleting a log entry"""        

    # import pdb;pdb.set_trace()
    temp_rec = view.table.get(view.rec_id) #temp_rec.photo_list may contain a list of LogPhoto DataRows

    view.success = view.table.delete(view.rec_id) # Related LogPhoto recs have been deleted too
    if view.success:
        view.db.commit()
        if temp_rec.photo_list:
            for pic in temp_rec.photo_list:
                FileUpload().remove_file(pic.path)
    else:
        view.result_text = 'Not able to delete the Log Entry record.'


def validate_form(view):
    # Validate the form
    if not view.rec.location_name:
        flash("You must enter a location name")
        view.success = False
        
    if cleanRecordID(view.rec.odometer) < 0:
        flash('The Odometer reading must be a positive number.')
        view.success = False

    try:
        view.rec.cost = float(view.rec.cost)
        if view.rec.cost < 0:
            flash('The Fuel Cost must be a positive number or zero.')
            view.success = False
    except:
        flash('The Fuel Cost must be a number or zero')
        view.success = False
            
    # set the UTC datetime based on the location from the map
    if view.rec.lat and view.rec.lng:
        try:
            tz = TimezoneFinder().timezone_at(lng=float(view.rec.lng), lat=float(view.rec.lat)) 
            local = pytz.timezone(tz)
            naive = datetime.strptime(str(view.rec.entry_date)[:19], "%Y-%m-%d %H:%M:%S")
            local_dt = local.localize(naive, is_dst=None)
            view.rec.entry_UTC_date = local_dt.astimezone(pytz.utc)
        except:
            view.rec.entry_UTC_date = datetime.now(pytz.utc)

    return view.success


@mod.route('/log_waypoint/<data>/', methods=['GET'])
@table_access_required(PRIMARY_TABLE)
def log_waypoint(data=""):
    """ Record a waypoint.
    
    The idea is that the web page will periodically emit a request to record the
    current location lngLat to be used for MapBox rounting display
    
    Args: data: str; a JSON string containing the data needed to record the waypoint
    
    Returns:  str: Always returns "OK"
    
    Raises: None
    """
    # import pdb;pdb.set_trace()
    try:
        data = json.loads(data)
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
        
        if data["trip_id"] and data["lat"] and data["lng"]:
            entry = models.LogEntry(g.db)
            new_rec = entry.new()
            # get the last point recorded
            last_rec = entry.select_one(where=f"trip_id = {data['trip_id']}", order_by="entry_UTC_date DESC")
            
            if 'location_name' not in data:
                new_rec.location_name = "Waypoint"
            if "entry_type" not in data:
                new_rec.entry_type = "WAY"
            if "entry_date" not in data:
                new_rec.entry_date = local_datetime_now()

            new_rec.update(data)
            ok_to_save = True
            if last_rec:
                # measure the distance
                dist = get_distance({"lat":last_rec.lat,"lng":last_rec.lng},{"lat":new_rec.lat,"lng":new_rec.lng})
                print(f"Distance: {dist}mi.")
                if dist < 0.25:
                    # to close to last
                    ok_to_save = False
                    print("too close")

                # import pdb;pdb.set_trace()
                newDate = getDatetimeFromString(new_rec.entry_UTC_date)
                oldDate = getDatetimeFromString(last_rec.entry_UTC_date)
                if newDate > oldDate + timedelta(minutes=120):
                    # its longer than 2 hours since last entry
                    ok_to_save = False
                    print("Too soon")

                if ok_to_save:
                    new_rec.save()
                    print(f"Waypoint {new_rec.id} Created",data['lng'],data["lat"])
                else:
                    g.db.rollback()

    except Exception as e:
        print(str(e))
    finally:
        pass

    return "OK"
    
    
def create_menus():
    """
    Create menu items for this module

    g.menu_items and g.admin are created in app.

    Menu elements defined directly in menu_items have no access control.
    Menu elements defined using g.admin.register can have access control.

    """

    # # Static dropdown menu...
    # g.menu_items.append({'title':'Drop down header','drop_down_menu':{
    #         'name':'First','url':url_for('.something'),
    #         'name':'Second','url':url_for('.another'),
    #         }
    #     })
    # # single line menu
    # g.menu_items.append({'title':'Something','url':url_for('.something')})
    
    # This makes a drop down menu for this application
    g.admin.register(models.TripSegment,url_for('trip_segment.display'),display_name='Trip Logging',header_row=True,minimum_rank_required=500,roles=['admin',])
    g.admin.register(models.TripSegment,
        url_for('trip_segment.display'),
        display_name='Log Entries',
        top_level=False,
        minimum_rank_required=500,
    )


def register_blueprints(app, subdomain = None) -> None:
    """
    Register this module with the app for this module

    Arguments:
        app -- the current app

    Keyword Arguments:
        subdomain -- limit access to this subdomain if defined (default: {None})
    """ 
    app.register_blueprint(mod, subdomain=subdomain)


def initialize_tables(db) -> None:
    """
    Initialize all the tables for this module

    Arguments:
        db -- connection to the database
    """
    
    models.init_db(db)


def get_edit_field_list(log_entry_rec) -> list | None:
    """
    Returns a list of edit field dicts for use with ViewEdit

    Arguments:
        log_entry_rec -- The log_entry record we are about to edit
    Returns:
        list or None on error
    """ 
    from shotglass2.users.models import User
    from travel_log import models

    edit_fields = []
    options = []
    user = User(g.db).get(session.get('user'))
    
    sql = f"""
        select max(cast(log_entry.odometer as integer)) as odometer from trip
        join log_entry on log_entry.trip_id = trip.id
        where odometer is not null and trip.vehicle_id = (select vehicle_id from trip where trip.id = {get_current_trip_id()}) 
    """
    # import pdb;pdb.set_trace()
    prev_odometer= models.LogEntry(g.db).query_one(sql)
    if prev_odometer:
        prev_odometer = prev_odometer.odometer
    if not prev_odometer:
        prev_odometer = 0
    sql = f"""
        select log_entry.state_of_charge as soc from trip
        join log_entry on log_entry.trip_id = trip.id
        where odometer is not null and trip.vehicle_id = (select vehicle_id from trip where trip.id = {get_current_trip_id()}) 
        order by log_entry.entry_UTC_date DESC
        limit 1
    """
    # import pdb;pdb.set_trace()
    prev_soc= models.LogEntry(g.db).query_one(sql)
    if prev_soc:
        prev_soc = prev_soc.soc
    if not prev_soc:
        prev_soc = 0

    if user:
        cars = models.Vehicle(g.db).select(where=f"user_id = {user.id}")
    if cars:
        trips = models.Trip(g.db).select(where=f"vehicle_id in ({','.join([str(car.id) for car in cars ] )})")
        if trips:
            for trip in trips:
                options.append({'name':f'{trip.name}','value':trip.id})
            edit_fields.append({'name':'trip_id','type':'select','label':'Trip','req':True,'options':options,})
        else:
            flash('You must have at least one Trip',category="warning")
            return None
    else:
        flash('You must have at least one Vehicle',category="warning")
        return None

    
    edit_fields.extend(
        [
        {"name":"choose_type","type":"text","label":"",'code':True,'req':False,
         'content': """
        <div id="choose_type" class="w3-col w3-border w3-center w3-primary-color" >
            <h2 class="w3-center">Select Entry Type</h2>
            <div class="w3-row w3-padding">
                <a href="#" class="w3-col w3-button w3-padding w3-secondary-color choose-type" >Departure</a>
            </div>
            <div class="w3-row w3-padding">
                <a href="#" class="w3-col w3-button w3-padding w3-secondary-color choose-type" >Point of Interest</a>
            </div>
            <div class="w3-row w3-padding">
                <a href="#" class="w3-col w3-button w3-padding w3-secondary-color choose-type" >Arrival</a>
            </div>
        </div>
        """,
         },
        {'name':'entry_type','type':'hidden','default':'',},
        {"name":"log_fields",'code':True,'content':"""<div id="log_fields">""",},
        {"name":"log_type_title",'code':True,
         'content':"""<h3 class="w3-center w3-primary-color" id="type_display"></h3>""",},
        {'name':'location_name','label':'Where','req':True,},
        {'name':'lat','type':'hidden', 'default':"0"},
        {'name':'lng','type':'hidden','default':"0"},
        ]
    )    
 
    edit_fields.append({'name':'entry_date_label','type':'label_only','label':'When','id':'entry_date_label'})
    entry_dict = {'name':'entry_date','type':'datetime','raw':True,'content':''}
    if is_mobile_device():
        field_type = 'datetime-local' #Safari likes this. I like it for mobile
    else:
        field_type = 'datetime' # I like this one better for Desktop

    entry_dict['content'] = f"""
    <p>
        <input name="entry_date" class="w3-input" type="{field_type}" id="entry_date" value="{date_to_string(log_entry_rec.entry_date,'iso_datetime')[:-3]}" />
    </p>
    """
    

    edit_fields.extend([entry_dict])

    edit_fields.extend(
        [
        {'name':'odometer','label':'Odometer Reading','type':'number','default':prev_odometer,'class':'keypad_input',},
        {'name':'state_of_charge','type':'number','label':'State of charge as % of Full','default':prev_soc,'class':'keypad_input',},
        {"name":"end_of_log_fields_div",'code':True,'req':False,'content':"<div id='cost-container'>",},
        {'name':'cost','type':'text','default':'0','class':'keypad_input',},
        {"name":"end_of_cost_div",'code':True,'req':False,'content':"</div>",},
        {'name':'memo','type':'textarea',},
        ])
    if log_entry_rec.photo_list:
        # import pdb;pdb.set_trace()
        edit_fields.extend([{'name':'log_image_label',"type":"label_only","label":"Photos",}]),
        entry_dict = {'name':"photo_list","code":True,"label":None,'content':''}
        entry_dict["content"] = """
        <div id="large_photo_contain">
            <img id="log_photo_large" src="" onclick="show_big_photo(this)" />
            <div id="log_photo_large_title"><h3></h3><p></p></div>
        </div>
        """
        edit_fields.extend([entry_dict])
        entry_dict = {'name':"photo_list","code":True,"label":None,'content':''}
        entry_dict["content"] = """<div id="log_photo_list";></div><p class="clear">&nbsp;</p>"""
        
        edit_fields.extend([entry_dict])
    edit_fields.extend([{"name":"log_photo","type":"file","label":"Add a photo",}])
    edit_fields.extend([{"name":"add_log_photo","type":"submit","label":"Save and Continue",},])
        
    edit_fields.extend(
        [
        {"name":"map",'code':True,'content':'<div id="map" class="map"></div>'},
        {"name":"end_of_log_fields_div",'code':True,'req':False,'content':"</div>",},
        ]
    )
    
    return edit_fields
