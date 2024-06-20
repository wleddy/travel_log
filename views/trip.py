from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device, get_rec_id_if_none
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural
from shotglass2.users.models import User

import travel_log.models as models
from travel_log.views import log_entry, log_photo, vehicle

PRIMARY_TABLE = models.Trip
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY

mod = Blueprint(MOD_NAME,__name__, template_folder=f'templates/travel_log', url_prefix=f'/travel_log/{MOD_NAME}')


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
    view.list_fields = get_listing_field_list()
    view.use_anytime_date_picker = not is_mobile_device()

    return view.dispatch_request()
    

## Edit the PRIMARY_TABLE
@mod.route('/edit', methods=['POST', 'GET'])
@mod.route('/edit/', methods=['POST', 'GET'])
@mod.route('/edit/<int:rec_id>/', methods=['POST','GET'])
@table_access_required(PRIMARY_TABLE)
def edit(rec_id=None):
    setExits()
    return edit_trip(rec_id)

def edit_trip(rec_id=None,**kwargs):
    rec_id = get_rec_id_if_none(rec_id)
    if rec_id < 0:
        flash("Record ID must be greater than 0")
        return redirect(g.listURL)

    g.title = "Edit {} Record".format(g.title)
    view = EditView(PRIMARY_TABLE,g.db,rec_id)
    view.edit_fields = get_edit_field_list()
    view.validate_form = validate_form
    view.base_layout = "travel_log/form_layout.html"

    if not view.next:
        view.next = kwargs.get("next",'')

    if request.form and view.success:
        # Update -> Validate -> Save...
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)

    return view.render()

    
def validate_form(view):
    # Validate the form
    goodForm = True
    # import pdb; pdb.set_trace()
    if not view.rec.id and cleanRecordID(view.rec.vehicle_id) > 0:
        car = models.Vehicle(g.db).get(cleanRecordID(view.rec.vehicle_id))
        if car:
            view.rec.battery_health = car.battery_health

    return goodForm

def get_edit_field_list() -> list:
    """
    Return a list of fields to include in the edit form

    Returns:
        a list of dicts
    """
    # import pdb;pdb.set_trace()
    edit_fields = [
        {'name':'name','req':True,'label':'Trip Name'},
        ]
    options = []
    user = User(g.db).get(session.get('user'))
    if user:
        cars = models.Vehicle(g.db).select(where=f"user_id = {user.id}")
    if cars:
        for car in cars:
            options.append({'name':f'{car.name}','value':car.id})
        edit_fields.append({'name':'vehicle_id','type':'select','label':'Vehicles','options':options,})

    return edit_fields
    
def get_listing_field_list() -> list:
    """
    Return a list of fields to diaplay in list

    Returns:
        list of dicts
    """

    list_fields = [
        {'name':'id',},
        {'name':'name','label':'Trip Name',},
        {'name':'creation_date','type':'datetime','search':'datetime'},
        ]
    
    return list_fields


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
    g.admin.register(models.Trip,url_for('trip.display'),display_name='Trip Log',header_row=True,minimum_rank_required=500,roles=['admin',])
    g.admin.register(models.Trip,
        url_for('trip.display'),
        display_name='Trips',
        top_level=False,
        minimum_rank_required=500,
    )
    g.admin.register(models.LogEntry,
        url_for('log_entry.display'),
        display_name='Log Entry',
        top_level=False,
        minimum_rank_required=500,
    )
    g.admin.register(models.Vehicle,
        url_for('vehicle.display'),
        display_name='Vehicles',
        top_level=False,
        minimum_rank_required=500,
    )
    g.admin.register(models.LogPhoto,
        url_for('log_photo.display'),
        display_name='Photos',
        top_level=False,
        minimum_rank_required=500,
    )


def register_blueprints(app, subdomain = None) -> None:
    """
    Register one or more modules with the app

    Arguments:
        app -- the current app

    Keyword Arguments:
        subdomain -- limit access to this subdomain if difined (default: {None})
    """ 

    from travel_log.views import vehicle, log_entry, travel_log
    app.register_blueprint(mod, subdomain=subdomain)
    app.register_blueprint(vehicle.mod, subdomain=subdomain)
    app.register_blueprint(log_entry.mod, subdomain=subdomain)
    app.register_blueprint(log_photo.mod, subdomain=subdomain)
    app.register_blueprint(travel_log.mod, subdomain=subdomain)


def initialize_tables(db) -> None:
    """
    Initialize all the tables for this module

    Arguments:
        db -- connection to the database
    """
    
    models.init_db(db)