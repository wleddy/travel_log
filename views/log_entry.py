from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.date_utils import date_to_string, local_datetime_now
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural

import travel_log.models as models
from travel_log.views.travel_log import get_current_trip_id

from datetime import datetime   
import pytz
from timezonefinder import TimezoneFinder 


PRIMARY_TABLE = models.LogEntry
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY

mod = Blueprint(MOD_NAME,__name__, template_folder='templates/', url_prefix=f'/travel_log/{MOD_NAME}')


def setExits():
    g.listURL = url_for('.display')
    g.editURL = url_for('.edit')
    g.deleteURL = url_for('.display') + 'delete/'
    g.title = f'{PRIMARY_TABLE(g.db).display_name}'
    g.layout_to_extend = 'layout.html'


# this handles table list and record delete
@mod.route('/<path:path>',methods=['GET','POST',])
@mod.route('/<path:path>/',methods=['GET','POST',])
@mod.route('/',methods=['GET','POST',])
@table_access_required(PRIMARY_TABLE)
def display(path=None):
    # import pdb;pdb.set_trace()
    setExits()
    
    view = TableView(PRIMARY_TABLE,g.db)
    # optionally specify the list fields
    view.list_fields = [
        {'name':'id',},
        {'name':'location_name',},
        {'nmame':'entry_type',},
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

    # Need to pre-fetch the log record so I can populate the form
    rec_id = cleanRecordID(request.form.get('id',rec_id))
    rec = None
    table =  PRIMARY_TABLE(g.db)
    if rec_id < 0:
        flash("Invalid Request")
        return redirect(g.listURL)
    if rec_id == 0:
        rec = table.new()
    else:
        rec = table.get(rec_id)
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
        return redirect(g.listURL)

    view.base_layout = "travel_log/form_layout.html"

    # Some methods in view you can override
    view.validate_form = validate_form # view does almost no validation
    # view.after_get_hook = ? # view has just loaded the record from disk
    # view.before_commit_hook = ? # view is about to commit the record

    # Process the form?
    if request.form and view.success:
        # Update -> Validate -> Save...
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)

    # otherwise send the list...
    return view.render()

    
def validate_form(view):
    # Validate the form
    view._set_edit_fields()
    for field in view.edit_fields:
        if field['name'] in request.form and field['req']:
            val = view.rec.__getattribute__(field['name'])
            if isinstance(val,str):
                val = val.strip()
            if not val:
                view.result_text = "You must enter a value for {}".format(field['name'])
                flash(view.result_text)
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
        {'name':'log_image_label',"type":"label_only","label":"Photos",},
        ])
    if log_entry_rec.photo_list:
        # import pdb;pdb.set_trace()
        entry_dict = {'name':"photo_list","code":True,"label":None,'content':''}
        entry_dict["content"] = """<div id="log_photo_list";><p>"""
        for photo in log_entry_rec.photo_list:
            entry_dict["content"] += f"""<img src="{ url_for('static',filename=photo.path)}" class="log_photo_small" />"""
        
        entry_dict["content"] += "</p></div>"
        
        edit_fields.extend([entry_dict])

    edit_fields.extend([{"name":"log_photo_id","type":"file","label":"Pick a Photo",}])
        
    edit_fields.extend(
        [
        {"name":"map",'code':True,'content':'<div id="map" class="map"></div>'},
        {"name":"end_of_log_fields_div",'code':True,'req':False,'content':"</div>",},
        ]
    )
    
    return edit_fields
