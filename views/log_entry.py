from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.date_utils import date_to_string, local_datetime_now
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural

import travel_log.models as models
from travel_log.views.travel_log import get_current_trip_id

PRIMARY_TABLE = models.LogEntry
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY

mod = Blueprint(MOD_NAME,__name__, template_folder='templates/', url_prefix=f'/{MOD_NAME}')


def setExits():
    g.listURL = url_for('.display')
    g.editURL = url_for('.edit')
    g.deleteURL = url_for('.display') + 'delete/'
    g.title = f'{plural(PRIMARY_TABLE(g.db).display_name,2)}'
    

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
        # rec.entry_date = local_datetime_now()
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

    if view.rec.charging_rate and cleanRecordID(view.rec.charging_rate) < 0:
        flash('The Charging Rate must be a positive number.')
        view.success = False

    try:
        view.rec.fuel_cost = float(view.rec.fuel_cost)
    except:
        flash('The Fuel Cost must be a positive number.')
        view.success = False

    if isinstance(view.rec.fuel_qty,str):
        view.rec.fuel_qty = view.rec.fuel_qty.strip()
        if view.rec.fuel_qty.strip().endswith('%'):
            view.rec.fuel_qty = view.rec.fuel_qty[0:-1]
    try:
        view.rec.fuel_qty = float(view.rec.fuel_qty)
    except:
        flash('The Fuel Quantity must be a positive number.')
        view.success = False
            
    return view.success # This is really redundant now...


    
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
    
    sql=f"""
        select max(log_entry.odometer) as odometer from log_entry
        join trip on trip.id = log_entry.trip_id
        join vehicle on vehicle.id = trip.vehicle_id
        where vehicle.id = trip.vehicle_id and trip.id = {get_current_trip_id()}
    """
    # import pdb;pdb.set_trace()
    prev_odometer= models.LogEntry(g.db).query_one(sql)
    if prev_odometer:
        prev_odometer = prev_odometer.odometer
    if not prev_odometer:
        prev_odometer = 0

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
        {'name':'location_name','req':True,},
        {'name':'entry_type','req':True,'type':'select','options':[
            {'name':'Departure'},
            {'name':'Point of Interest'},
            {'name':'Arrival'},
        ]},
        ]
    )    
 
    edit_fields.append({'name':'entry_date','type':'label_only','label':'When','id':'entry_date_label'})
    entry_date_dict = {'name':'entry_date','type':'datetime','raw':True,'content':''}
    if is_mobile_device():
        field_type = 'datetime-local' #Safari like this. I like it for mobile
    else:
        field_type = 'datetime' # I like this one better for Desktop

    content = f"""
    <p>
        <input name="entry_date" class="w3-input" type="{field_type}" id="entry_date" value="{date_to_string(log_entry_rec.entry_date,'iso_datetime')}" />
    </p>
    """
    
    entry_date_dict['content'] = content

    edit_fields.extend([entry_date_dict])

    edit_fields.extend(
        [
        {'name':'odometer','type':'number','default':prev_odometer},
        {'name':'memo','type':'textarea',},
        {'name':'projected_range','type':'number','default':0},
        {'name':'fuel_qty','type':'number','label':'Fuel Quantity as % of Full','default':0},
        {'name':'charging_rate','type':'number','label':'Max Charging Rate (Electric Only)'},
        {'name':'fuel_cost','type':'text','default':'0.00'},
        ]
    )
    
    return edit_fields
