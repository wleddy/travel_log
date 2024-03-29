from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.date_utils import local_datetime_now
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device
from shotglass2.users.admin import login_required
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural
import travel_log.models as models
import travel_log.views as tl_views

PRIMARY_TABLE = None

mod = Blueprint('travel_log',__name__, 
                template_folder='templates/travel_log/', 
                static_folder='static/',
                url_prefix='/travel_log',
                )


def setExits(which=''):
    g.listURL = url_for('.home')
    g.editRL = url_for('.home')
    g.deleteURL = url_for('.home')
    g.suppress_page_header = True
    if which == 'log':
        g.listURL = url_for('.log_list')
        g.editURL = url_for('.edit_log')
        g.deleteURL = g.listURL + 'delete/'
        g.suppress_page_header = False
    elif which == 'trip':
        g.listURL = url_for('.trip_list')
        g.editURL = url_for('.edit_trip')
        g.deleteURL = g.listURL + 'delete/'
        g.suppress_page_header = False
    elif which == 'car':
        g.listURL = url_for('.car_list')
        g.editURL = url_for('.edit_car')
        g.deleteURL = g.listURL + 'delete/'
        g.suppress_page_header = False
        
    create_menus()

def compile_trip_summary(data:dict,trip_ids:int | list,summary=False) ->None:
    """
    Compile summary data for one or more trips

    Creates a list item in 'data' named 'log_entries'. 
    Each list element contains the log_entry data plus summary data for:
    
        *   Multi trip report: By submitting multiple trip ids in a list you will have a summary for
            all those trips.
        *   Trip Summary: summary data for each trip
        *   Leg Data: for some elements calculate the distance or consumption during a prev
            leg.
    
    Arguments:
        data -- A dict to store the results
        trip_ids -- a single integer for a trip.id or a list of ints for reporting on mutlple
        trips. 

    Optional Arguments:
        summary -- create a summary report without individual log data { default : False }
    """

    data['log_entries'] = []

    if not isinstance(trip_ids,list):
        trip_ids = [trip_ids]

    # report summary
    sql = f"""  
            select 
            CAST (sum(coalesce(fueling_time,0)) AS INTEGER) as report_fueling_time,
            CAST (coalesce(fuel_added,0) AS REAL) as report_fuel_added, 
            CAST (sum(coalesce(fuel_cost,0)) AS REAL) as report_fuel_cost
            from log_entry
            where trip_id in ({','.join([str(x) for x in trip_ids])})
        """
    report_summary = models.LogEntry(g.db).query_one(sql).asdict()

    for trip_id in trip_ids:
        # Trip Summary
        sql = f"""
                select 
                CAST (coalesce(min(odometer),0) AS INTEGER) as trip_starting, 
                CAST (coalesce(max(odometer),0) AS INTEGER) as trip_ending,
                CAST (sum(coalesce(arrival_fuel_level,0)) AS INTEGER) as trip_arrival_fuel_level,
                CAST (sum(coalesce(departure_fuel_level,0)) AS INTEGER) -
                    (SELECT CAST(coalesce(departure_fuel_level,0) AS INTEGER) from log_entry 
                    where trip_id = {trip_id} order by entry_date DESC limit 1) 
                    as trip_departure_fuel_level,
                CAST (sum(coalesce(fueling_time,0)) AS INTEGER) as trip_fueling_time,
                CAST (sum(coalesce(fuel_cost,0)) AS REAL) as trip_fuel_cost,
                CAST (coalesce(fuel_added,0) AS REAL) as trip_fuel_added, 
                (CAST (coalesce(max(odometer),0) AS INTEGER) - CAST (coalesce(min(odometer),0) AS INTEGER)) as trip_distance,
                vehicle.name as vehicle_name, 
                CAST (coalesce(vehicle.fuel_capacity,0) AS INTEGER) as fuel_capacity,
                vehicle.fuel_type as fuel_type
                from log_entry 
                join trip on log_entry.trip_id = trip.id
                join vehicle on trip.vehicle_id = vehicle.id
                where trip_id = {trip_id}
        """
        trip_summary = models.LogEntry(g.db).query_one(sql).asdict()
     
        if trip_summary:
            trip_summary['trip_efficiency'] = 0
            if trip_summary['trip_distance'] > 0:
                trip_summary['trip_fuel_consumed'] = trip_summary['trip_departure_fuel_level'] - trip_summary['trip_arrival_fuel_level']
                trip_summary['trip_efficiency'] = trip_summary['trip_distance'] / (trip_summary['trip_fuel_consumed'] / 100  * trip_summary['fuel_capacity'])                    

            if trip_summary['fuel_type'] and trip_summary['fuel_type'].lower() == 'electric':
                trip_summary['efficiency_factor'] = 'mi/kWh'
            else:
                trip_summary['efficiency_factor'] = 'mi/gal'
 

        sql = f"""
            select log_entry.id, location_name, 
            CAST (coalesce(odometer,0) AS INTEGER) as odometer, entry_date, entry_type, trip_id,
            memo, projected_range, charging_rate,
            CAST (coalesce(arrival_fuel_level,0) AS INTEGER) as arrival_fuel_level, 
            CAST (coalesce(departure_fuel_level,0) AS INTEGER) as departure_fuel_level, 
            CAST (coalesce(charging_rate,0) AS INTEGER) as charging_rate, 
            CAST (coalesce(fuel_added,0) AS REAL) as fuel_added, 
            CAST (coalesce(fuel_cost,0) AS REAL) as fuel_cost, 
            CAST (coalesce(fueling_time,0) AS INTEGER) as fueling_time,
            vehicle.name as vehicle_name, 
            CAST (coalesce(vehicle.fuel_capacity,0) AS INTEGER) as fuel_capacity,
            vehicle.fuel_type as fuel_type
            from log_entry 
            join trip on log_entry.trip_id = trip.id
            join vehicle on trip.vehicle_id = vehicle.id
            where trip_id = {trip_id}
            order by entry_date
        """

        recs = models.LogEntry(g.db).query(sql)
        prev_log = {
            'odometer':0,
            'last_fuel_odo':0,
            'departure_fuel_level':0
        }
        if recs:        
            # import pdb;pdb.set_trace()
            # Start of trip values...
            prev_log['last_fuel_odo'] = recs[0].odometer 
            prev_log['odometer'] = recs[0].odometer 
            prev_log['departure_fuel_level'] = recs[0].departure_fuel_level
            rec_count = len(recs)
            current_rec = 0
            for rec in recs:
                current_rec += 1
                log = rec.asdict() # as dict so we can add elements
                log['leg_distance'] = 0
                if prev_log['odometer'] <= log['odometer']:
                    log['leg_distance'] = log['odometer'] - prev_log['odometer']

                # only log fuel data if this is a fuel stop
                if log['arrival_fuel_level']:
                    log['leg_fuel_cost'] = log['fuel_cost']
                    log['leg_fueling_time'] = log['fueling_time']
                    log['leg_fuel_added'] = log['fuel_added']                    
                    log['leg_fuel_consumed'] = prev_log['departure_fuel_level'] - log['arrival_fuel_level']
                    log['leg_fuel_distance'] = log['odometer'] - prev_log['last_fuel_odo']
                    log['leg_efficiency'] = 0
                     # always include last entry and guard from div by 0
                    if log['leg_fuel_distance'] or \
                            current_rec >= rec_count and \
                            log['leg_fuel_consumed'] != 0:
                        log['leg_efficiency'] = log['leg_fuel_distance'] / \
                            (log['leg_fuel_consumed'] / 100  * log['fuel_capacity'])
                        
                        prev_log['last_fuel_odo'] = log['odometer']
                        prev_log['departure_fuel_level'] = log['departure_fuel_level']

                prev_log['odometer'] = log['odometer']
                log.update(report_summary)
                log.update(trip_summary)

                data['log_entries'].append(log)


@mod.route('/<path:path>>',methods=['GET',])
@mod.route('/',methods=['GET',])
def home():
    """ The Welcom page """
    setExits()

    data = {}
    # import pdb;pdb.set_trace()
    if'user_id' in session:

        # create a vehicle record if none exists
        make_default_vehicle(session.get('user_id'))

        # select the most "current" trip record
        trip_id = get_current_trip_id()
        data['trip'] = models.Trip(g.db).get(trip_id)
        # get logs of the most recent trips if any
        if data['trip']:
            compile_trip_summary(data,trip_id)

    return render_template('travel_log/home.html',data=data)


@mod.route('logout/',methods=['GET',])
def logout():
    """ log a user out """
    setExits()
    return redirect(url_for('login.logout') + f'?next={url_for(".home")}')

@mod.route('login/',methods=['GET',])
def login():
    """ log a user out """
    setExits()
    if 'user' in session:
        return redirect(url_for('.home'))
    
    return redirect(url_for('login.login') + f'?next={url_for(".home")}')

def make_default_vehicle(user_id) ->None:
    """
    Create a default vehicle probably for a new user

    Arguments:
        user_id -- user.id
    """
 
    if not models.Vehicle(g.db).select(where=f"user_id = {user_id}"):
        rec = models.Vehicle(g.db).new()
        rec.name = "My Car"
        rec.fuel_type = "Electric"
        rec.fuel_capacity = 62
        rec.user_id = session.get('user_id')
        models.Vehicle(g.db).save(rec,commit=True)


@mod.route('new_account/',methods=['GET',])
def new_account():
    """ log a user out """
    setExits()
    if 'user' in session:
        return redirect(url_for('.home'))
    
    return redirect(url_for('user.register') + f'?next={url_for(".home")}')

@mod.route('log_list/<path:path>',methods=['GET','POST'])
@mod.route('log_list/',methods=['GET','POST'])
@login_required
def log_list(path=''):
    setExits('log')
    g.title = f"{models.LogEntry(g.db).display_name} Record List"

    view = TableView(models.LogEntry,g.db)
    # optionally specify the list fields
    view.list_fields = [
        {'name':'id',},
        {'name':'location_name',},
        {'nmame':'entry_type',},
        {'name':'entry_date','type':'datetime','search':'datetime',},
        {'name':'memo'},
        ]
    
    view.base_layout = 'travel_log/layout.html'
    view.use_anytime_date_picker = not is_mobile_device()
    
    if view.next  and 'delete' not in path:
        return redirect(view.next) # was called from somewhere else
    
    return view.dispatch_request()
    

@mod.route('add_log/',methods=['GET','POST'])
@login_required
def add_log():
    setExits()
    return redirect(url_for('.edit_log') + f'0/?next={g.listURL}')


@mod.route('edit_log/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_log/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_log/',methods=['GET','POST'])
@login_required
def edit_log(rec_id=None):
    """ display the list of trips """
    setExits('log')
    g.title = f" {models.LogEntry.TABLE_IDENTITY.replace('_',' ').title()} Record"

    # Need to pre-fetch the log record so I can populate the form
    rec_id = cleanRecordID(request.form.get('id',rec_id))
    rec = None

    table =  models.LogEntry(g.db)
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

    view = EditView(models.LogEntry,g.db,rec_id)
    # import pdb;pdb.set_trace()

    # Set the trip id for new records
    if not view.rec.trip_id:
        view.rec.trip_id = get_current_trip_id()
        
    view.edit_fields = tl_views.log_entry.get_edit_field_list(rec)

    # convert the Trip select input to hidden and diaplay the trip name as text
    trip = models.Trip(g.db).get(view.rec.trip_id)
    if trip and view.edit_fields[0]['name'] == 'trip_id':
        view.edit_fields[0]['type'] = 'hidden'
        view.edit_fields.insert(0,{'name':'header','raw':True,'content':f'<h4 class="w3-secondary-color w3-center w3-bar">{trip.name}</h4><hr/>'})

    view.validate_form = tl_views.log_entry.validate_form
    view.base_layout = "travel_log/form_layout.html"

    view.use_anytime_date_picker = not is_mobile_device()

    if not view.rec.id:
        g.title = 'New' + g.title
    else:
        g.title = 'Edit' + g.title

    # Process the form?
    if request.form and view.success:
        # Update -> Validate -> Save...
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)
            
    #else display the form
    return view.render()


@mod.route('trips/<path:path>',methods=['GET','POST'])
@mod.route('trips/',methods=['GET','POST'])
@login_required
def trip_list(path=''):
    setExits('trip')

    view = TableView(models.Trip,g.db)
    view.list_fields = tl_views.trip.get_listing_field_list()
    view.base_layout = 'travel_log/layout.html'
    view.use_anytime_date_picker = not is_mobile_device()
    # import pdb;pdb.set_trace()
    view.sql = f"""
        select * from trip
        where vehicle_id in (select id from vehicle where user_id = {session.get('user_id'),-1})
    """

    if view.next  and 'delete' not in path:
        return redirect(view.next) # was called from somewhere else
    
    return view.dispatch_request()
    

@mod.route('add_trip/',methods=['GET','POST'])
@login_required
def add_trip():
    setExits()
    return redirect(url_for('.edit_trip') + f'0/?next={g.listURL}')


@mod.route('edit_trip/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_trip/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_trip/',methods=['GET','POST'])
@login_required
def edit_trip(rec_id=None):
    setExits('trip')

    g.title = f" {models.Trip.TABLE_IDENTITY.replace('_',' ').title()} Record"

    rec_id = cleanRecordID(request.form.get('id',rec_id))

    # import pdb;pdb.set_trace()

    view = EditView(models.Trip,g.db,rec_id)

    view.validate_form = tl_views.trip.validate_form
    view.base_layout = "travel_log/form_layout.html"
    view.edit_fields = tl_views.trip.get_edit_field_list()
    view.use_anytime_date_picker = not is_mobile_device()

    if not view.rec.id:
        g.title = 'New' + g.title
    else:
        g.title = 'Edit' + g.title
 
    # Process the form?
    if request.form and view.success:
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)
            
    #else display the form
    return view.render()

@mod.route('edit_current_trip',methods=['GET','POST'])
@mod.route('edit_current_trip/',methods=['GET','POST'])
@login_required
def edit_current_trip():
    """
    This is a shortcut from the menu to edit the current trip Record

    Returns:
        flask response
    """
    
    # try to get the current trip from the session...
    rec_id = get_current_trip_id()

    return redirect(url_for('.edit_trip') + str(rec_id) + "/?next=" + url_for('.home'))


@mod.route('select_trip',methods=['GET','POST'])
@mod.route('select_trip/',methods=['GET','POST'])
@login_required
def select_trip():
    """
    Select an existing trip to add or edit entries

    This will set the current_trip_date field of the selected trip
    record to the current UTC datetime which will make it the current
    trip.

    Returns:
        flask response
    """
    setExits()

    if request.args:
        trip_id = cleanRecordID(request.args['trip_id'])
        rec = models.Trip(g.db).get(trip_id)
        models.Trip(g.db).save(rec) # Updates current_trip_date to utcnow

        return redirect(g.listURL)
    
    data = {}
    sql = """
        select id,name,
        coalesce ((select min(log_entry.entry_date) from log_entry where trip_id = trip.id),trip.creation_date) as entry_date 
        from trip
        order by entry_date 
    """
    data['recs'] = models.Trip(g.db).query(sql)

    return render_template('travel_log/trip_select_list.html',data=data)


@mod.route('/cars/<path:path>',methods=['GET','POST'])
@mod.route('/cars/',methods=['GET','POST'])
@login_required
def car_list(path=''):
    setExits('car')

    view = TableView(models.Vehicle,g.db)
    # optionally specify the list fields
    # view.list_fields = [
    #     ]
    view.base_layout = 'travel_log/layout.html'
    view.sql = f"""
        select * from vehicle where user_id = {session.get('user_id',-1)}
    """
    if view.next  and 'delete' not in path:
        return redirect(view.next) # was called from somewhere else
    
    return view.dispatch_request()
    

@mod.route('/edit_car/<int:rec_id>',methods=['GET','POST'])
@mod.route('/edit_car/<int:rec_id>/',methods=['GET','POST'])
@mod.route('/edit_car/',methods=['GET','POST'])
@login_required
def edit_car(rec_id=None):
    setExits('car')
    g.title = f"Edit {models.Vehicle.TABLE_IDENTITY.replace('_',' ').title()} Record"
    
    rec_id = cleanRecordID(request.form.get('id',rec_id))
    if rec_id < 0:
        flash('Invalid Request')
        return redirect(g.listURL)
    
    view = EditView(models.Vehicle,g.db,rec_id)

    view.validate_form = tl_views.vehicle.validate_form
    view.base_layout = "travel_log/form_layout.html"
    view.after_get_hook = after_view_get
    view.edit_fields = tl_views.vehicle.get_edit_field_list()

    # Process the form?
    if request.form and view.success:
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)
            
    #else display the form
    return view.render()

def after_view_get(view):
    # import pdb;pdb.set_trace()
    if request.form:
        # In the case where a submit failed, load the form values
        view.table.update(view.rec,request.form)
    if view.rec and not view.rec.id and not view.rec.user_id:
        # a new record
        view.rec.user_id = int(session.get('user_id',0))


@mod.route('photos/',methods=['GET','POST'])
@login_required
def photos():
    return request.path


@mod.route('account/',methods=['GET',])
@login_required
def account():
    return request.path



def validate_form(view):
    # Validate the form
    view.success = True
                
    return view.success

def get_current_trip_id() -> int:
    """
    Get the id of the Trip record with the most recent 'current_trip_date' 

    current_trip_date is set to the current UTC time whenever a LogEntry record
    is updated. 

    Returns:
        the trip id as int
    """

    trip_id = None

    # Get the most recently edited trip or log_entry
    rec = models.Trip(g.db).select_one(where=f"trip.vehicle_id in (select id from vehicle where user_id = {session.get('user_id')})",order_by="current_trip_date DESC")
    if rec:
        trip_id = rec.id

    return trip_id


def create_menus():
    """
    Create menu items for this module

    g.menu_items and g.admin are created in app.

    Menu elements defined directly in menu_items have no access control.
    Menu elements defined using g.admin.register can have access control.

    """
    g.menu_items = []


    g.menu_items.append({'title':'Home','url':url_for('.home')})
    if 'user' in session:
        g.menu_items.append({'title':'Cars','url':url_for('.car_list')})
        g.menu_items.append({'title':'Trips','drop_down_menu':[
            {'title':'Add a Log Entry','url':url_for('.add_log'),},
            {'title':'Edit this Trip','url':url_for('.edit_current_trip'),},
            {'title':'Select a Trip','url':url_for('.select_trip'),},
            {'title':'Start a new Trip','url':url_for('.add_trip'),},
            ]
        })
        # g.menu_items.append({'title':'Photos','url':url_for('.photos')})
        if session.get('user_has_password'):
            g.menu_items.append({'title':'Account','url':url_for('.account')})
        g.menu_items.append({'title':'Log Out','url':url_for('.logout')})
        
        
def register_blueprints(app, subdomain = None) -> None:
    """
    Register this module with the app for this module

    Arguments:
        app -- the current app

    Keyword Arguments:
        subdomain -- limit access to this subdomain if difined (default: {None})
    """ 
    app.register_blueprint(mod, subdomain=subdomain)


def initialize_tables(db) -> None:
    """
    Initialize all the tables for this module

    Arguments:
        db -- connection to the database
    """
    
    models.init_db(db)