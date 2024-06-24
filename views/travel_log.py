from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.date_utils import local_datetime_now
from shotglass2.takeabeltof.file_upload import FileUpload
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device
from shotglass2.users.admin import login_required
from shotglass2.takeabeltof.views import TableView, EditView
import travel_log.models as models
import travel_log.views as tl_views

import json

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
    g.base_layout = 'travel_log/layout.html'
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
    # import pdb;pdb.set_trace()

    if not isinstance(trip_ids,list):
        trip_ids = [trip_ids]

    # # report summary
    # sql = f"""  
    #         select *
    #         from log_entry
    #         where trip_id in ({','.join([str(x) for x in trip_ids])})
    #     """
    # report_summary = models.LogEntry(g.db).query_one(sql)
    # if report_summary:
    #     report_summary = report_summary.asdict()

    for trip_id in trip_ids:
        # Trip Summary
        sql = f"""
                select 
                CAST (coalesce(min(odometer),0) AS INTEGER) as trip_starting, 
                CAST (coalesce(max(odometer),0) AS INTEGER) as trip_ending,
                CAST (sum(coalesce(state_of_charge,0)) AS INTEGER) as trip_arrival_fuel_level,
                CAST (sum(coalesce(state_of_charge,0)) AS INTEGER) -
                    (SELECT CAST(coalesce(state_of_charge,0) AS INTEGER) from log_entry 
                    where trip_id = {trip_id} order by entry_date DESC limit 1) 
                    as trip_departure_fuel_level,
                CAST (sum(coalesce(cost,0)) AS REAL) as trip_fuel_cost,
                (CAST (coalesce(max(odometer),0) AS INTEGER) - CAST (coalesce(min(odometer),0) AS INTEGER)) as trip_distance,
                vehicle.name as vehicle_name, 
                CAST (coalesce(vehicle.fuel_capacity,0) AS INTEGER) as fuel_capacity,
                vehicle.fuel_type as fuel_type,
                trip.battery_health as trip_battery_health
                from log_entry 
                join trip on log_entry.trip_id = trip.id
                join vehicle on trip.vehicle_id = vehicle.id
                where trip_id = {trip_id}
        """
        trip_summary = models.LogEntry(g.db).query_one(sql).asdict()
     
        if trip_summary:
            trip_summary['trip_efficiency'] = 0
            trip_summary["trip_fuel_consumed"] = 0
            if trip_summary['trip_distance'] > 0 and trip_summary['trip_fuel_consumed'] > 0 :
                trip_summary['trip_fuel_consumed'] = trip_summary['trip_departure_fuel_level'] - trip_summary['trip_arrival_fuel_level']
                trip_summary['trip_efficiency'] = trip_summary['trip_distance'] / (trip_summary['trip_fuel_consumed'] / 100  * trip_summary['fuel_capacity'])                    

            if trip_summary['fuel_type'] and trip_summary['fuel_type'].lower() == 'electric':
                trip_summary['efficiency_factor'] = 'mi/kWh'
            else:
                trip_summary['efficiency_factor'] = 'mi/gal'
 

        sql = f"""
            select log_entry.id, location_name, 
            CAST (coalesce(odometer,0) AS INTEGER) as odometer, entry_date, entry_type, trip_id,
            memo, 
            CAST (coalesce(lng,0) AS REAL) as lng,
            CAST (coalesce(lat,0) AS REAL) as lat,
            CAST (coalesce(state_of_charge,0) AS INTEGER) as state_of_charge, 
            CAST (coalesce(cost,0) AS REAL) as cost, 
            vehicle.name as vehicle_name, 
            CAST (coalesce(vehicle.fuel_capacity,0) AS INTEGER) as fuel_capacity,
            vehicle.fuel_type as fuel_type,
            trip.battery_health as trip_battery_health
            from log_entry 
            join trip on log_entry.trip_id = trip.id
            join vehicle on trip.vehicle_id = vehicle.id
            where trip_id = {trip_id}
            order by entry_UTC_date
        """

        recs = models.LogEntry(g.db).query(sql)
        trip_consumption = 0
        prev_log = {
            'odometer':0,
            'state_of_charge':0,
        }
        data['coords'] = {'points':[],'match_path':[]}
        if recs:        
            # import pdb;pdb.set_trace()
            # Start of trip values...
            prev_log['odometer'] = recs[0].odometer 
            prev_log['state_of_charge'] = recs[0].state_of_charge
            rec_num = 0
            for rec in recs:
                if not rec.location_name:
                    continue
                rec_num += 1
                log = rec.asdict() # as dict so we can add elements
                log['leg_distance'] = log['odometer'] - prev_log['odometer']
                log['consumption'] = 0
                if log['state_of_charge'] < prev_log["state_of_charge"]:
                    log['consumption'] = (prev_log["state_of_charge"] - log["state_of_charge"])/100 * (log["fuel_capacity"] * (log["trip_battery_health"]/100))
                    trip_consumption += log["consumption"]
                prev_log['state_of_charge'] = log['state_of_charge']
                log["leg_efficiency"] = 0
                if log['consumption'] > 0:
                    log["leg_efficiency"] = log['leg_distance'] / log["consumption"]
                prev_log["odometer"] = log["odometer"]

                log.update(trip_summary)
                # log.update(report_summary)

                data['log_entries'].append(log)

                # Create data to populate map
                # coords = {'points':['geometry':{'coordinates':[-121.6, 38.8],},'properties':{'title':'Coffee Works'}],'match_path':[[-121.6, 38.8],[-121.6, 38.8]]}
                data['coords']["points"].append({"geometry":{"coordinates":[log["lng"],log["lat"]]},"properties":{"title":log['location_name'],"entry_type":log["entry_type"][:3].upper()}})
                data['coords']["match_path"].append([log["lng"],log["lat"]])
                                        

        data['trip_consumption'] = trip_consumption
        data['coords'] = json.dumps(data['coords'])

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
  

@mod.route('add_log/',methods=['GET','POST'])
@login_required
def add_log():
    return edit_log(0)


@mod.route('edit_log/<int:rec_id>/<int:trip_id>',methods=['GET','POST'])
@mod.route('edit_log/<int:rec_id>/<int:trip_id>/',methods=['GET','POST'])
@mod.route('edit_log/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_log/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_log/',methods=['GET','POST'])
@login_required
def edit_log(rec_id=None,trip_id=None):
    setExits('log')
    rec_id = cleanRecordID(rec_id)
    if not rec_id:
        # import pdb; pdb.set_trace()
        rec = models.LogEntry(g.db).new()
        rec.trip_id = trip_id if trip_id else get_current_trip_id()
        rec.save() # so images can be attached
        rec_id = rec.id
        g.cancelURL = f"{g.deleteURL.rstrip('/')}/{rec_id}" #Clicking cancel will delete this stub record
    return tl_views.log_entry.edit_log(rec_id,next=url_for(".home"))


@mod.route('log_list/<path:path>',methods=['GET','POST'])
@mod.route('log_list/',methods=['GET','POST'])
@login_required
def log_list(path=''):
    setExits('log')
    # import pdb;pdb.set_trace()
    if '?next=' not in path:
        path += f"?next={url_for('.home')}"
    return tl_views.log_entry.log_entry_list(path)


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
    return edit_trip(0)


@mod.route('edit_trip/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_trip/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_trip/',methods=['GET','POST'])
@login_required
def edit_trip(rec_id=None):
    setExits('trip')
    g.title = f" {models.Trip.TABLE_IDENTITY.replace('_',' ').title()} Record"

    rec_id = cleanRecordID(rec_id)
    return tl_views.trip.edit_trip(rec_id,next=url_for(".home"))


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
    g.title = f" {models.Trip.TABLE_IDENTITY.replace('_',' ').title()} Record"

    rec_id = cleanRecordID(rec_id)
    return tl_views.vehicle.edit_vehicle(rec_id,next=g.listURL)


@mod.route('photos/',methods=['GET','POST'])
@login_required
def photos():
    return request.path


@mod.route('account/',methods=['GET',])
@login_required
def account():
    return request.path


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
        # if session.get('user_has_password'):
        #     g.menu_items.append({'title':'Account','url':url_for('.account')})
        g.menu_items.append({'title':'Log Out','url':url_for('.logout')})
        
