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


@mod.route('/<path:path>>',methods=['GET',])
@mod.route('/',methods=['GET',])
def home():
    """ The Welcom page """
    setExits()

    data = {}
    # import pdb;pdb.set_trace()
    if'user_id' in session:

        # create a vehicle record if none exists
        if not models.Vehicle(g.db).select():
            rec = models.Vehicle(g.db).new()
            rec.name = "My Car"
            rec.fuel_type = "Electric"
            rec.fuel_capacity = 62
            rec.user_id = session.get('user_id')
            models.Vehicle(g.db).save(rec,commit=True)

        # select the most recent trip record or at least the one the user wants
        trip_id = get_current_trip_id()
        data['trip'] = models.Trip(g.db).get(trip_id)
        # get logs of the most recent trips if any
        data['log_entries'] = None
        if data['trip']:
            data['log_entries'] = models.LogEntry(g.db).select(where=f"trip_id = {data['trip'].id}")

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
    g.title = f"{plural(models.LogEntry.TABLE_IDENTITY,2)} Record List"

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
    
    

@mod.route('edit_log/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_log/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_log/',methods=['GET','POST'])
@login_required
def edit_log(rec_id=None):
    """ display the list of trips """
    setExits('log')
    g.title = f"Edit {models.LogEntry.TABLE_IDENTITY.replace('_',' ').title()} Record"

    # Need to pre-fetch the log record so I can populate the form
    rec_id = cleanRecordID(request.form.get('id',rec_id))
    rec = None

    table =  models.LogEntry(g.db)
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

    view = EditView(models.LogEntry,g.db,rec_id)
    # import pdb;pdb.set_trace()

    view.edit_fields = tl_views.log_entry.get_edit_field_list(rec)
    view.validate_form = tl_views.log_entry.validate_form
    view.base_layout = "travel_log/form_layout.html"

    view.use_anytime_date_picker = not is_mobile_device()


    # Process the form?
    if request.form and view.success:
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

    if view.next  and 'delete' not in path:
        return redirect(view.next) # was called from somewhere else
    
    return view.dispatch_request()
    

@mod.route('edit_trip/<int:rec_id>',methods=['GET','POST'])
@mod.route('edit_trip/<int:rec_id>/',methods=['GET','POST'])
@mod.route('edit_trip/',methods=['GET','POST'])
@login_required
def edit_trip(rec_id=None):
    setExits('trip')
    g.title = f"Edit {models.Trip.TABLE_IDENTITY.replace('_',' ').title()} Record"

    rec_id = cleanRecordID(request.form.get('id',rec_id))

    # import pdb;pdb.set_trace()

    view = EditView(models.Trip,g.db,rec_id)

    view.validate_form = tl_views.trip.validate_form
    view.base_layout = "travel_log/form_layout.html"
    view.edit_fields = tl_views.trip.get_edit_field_list()
    view.use_anytime_date_picker = not is_mobile_device()

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

    This will set session['current_trip_id'] to the id of the 
    trip selected

    Returns:
        flask response
    """
    setExits('trip')

    if request.args:
        session['current_trip_id'] = request.args['trip_id']

    return request.path


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
    get the id of the trip that we want to work with

    This will get/set session['current_trip_id']

    Returns:
        the trip id as int
    """

    trip_id = session.get('current_trip_id')
    if trip_id:
        return trip_id
    
    # Get the most recent trip
    rec = models.Trip(g.db).select_one(where=f"creation_date = (select max(trip.creation_date) from trip)")
    if rec:
        trip_id = rec.id

    if trip_id:
        session['current_trip_id'] = trip_id

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
            {'title':'Edit Current Trip','url':url_for('.edit_current_trip'),},
            {'title':'Select a Trip','url':url_for('.select_trip'),},
            {'title':'Trip List','url':url_for('.trip_list'),},
            ]
        })
        g.menu_items.append({'title':'Log Entry','url':url_for('.log_list')})
        # g.menu_items.append({'title':'Photos','url':url_for('.photos')})
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