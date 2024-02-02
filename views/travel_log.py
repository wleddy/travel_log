from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural
from shotglass2.users.views import login, user
import travel_log.models as models

PRIMARY_TABLE = None

mod = Blueprint('travel_log',__name__, 
                template_folder='templates/travel_log/', 
                static_folder='static/travel_log/',
                url_prefix='/travel_log',
                )


def setExits():
    # g.listURL = url_for('.display')
    # g.editURL = url_for('.edit')
    # g.deleteURL = url_for('.display') + 'delete/'
    # g.title = f'{plural(PRIMARY_TABLE(g.db).display_name,2)}'
    create_menus()

@mod.route('/',methods=['GET',])
def home():
    """ The Welcom page """
    setExits()
    data = {}
    # import pdb;pdb.set_trace()
    if'user_id' in session:
        # Get the trip data
        sql = f"""
        select log_entry.id, log_entry.location_name,log_entry.entry_type,
        log_entry.entry_date, trip.name as trip_name 
        from log_entry
        join trip on trip.id = log_entry.trip_id
        join vehicle on vehicle.id = trip.vehicle_id
        where vehicle.user_id = {session.get('user_id')}
        order by log_entry.entry_date DESC
        """
        data['recs'] = models.LogEntry(g.db).query(sql)

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

@mod.route('edit_trip/',methods=['GET',])
@mod.route('edit_trip/<int:rec_id>',methods=['GET',])
@login_required
def edit_trip(rec_id=None):
    """ display the list of trips """
    setExits()
    data = {}

    return render_template('travel_log/home.html',data=data)


@mod.route('cars/',methods=['GET',])
@login_required
def cars():
    return request.path


@mod.route('photos/',methods=['GET',])
@login_required
def photos():
    return request.path


@mod.route('account/',methods=['GET',])
@login_required
def account():
    return request.path



    
def validate_form(view):
    # Validate the form
    goodForm = True
                
    return goodForm


def create_menus():
    """
    Create menu items for this module

    g.menu_items and g.admin are created in app.

    Menu elements defined directly in menu_items have no access control.
    Menu elements defined using g.admin.register can have access control.

    """
    g.menu_items = []

    # # Static dropdown menu...
    # g.menu_items.append({'title':'Drop down header','drop_down_menu':{
    #         'name':'First','url':url_for('.something'),
    #         'name':'Second','url':url_for('.another'),
    #         }
    #     })
    # single line menu

    g.menu_items.append({'title':'Home','url':url_for('.home')})
    if 'user' in session:
        g.menu_items.append({'title':'Cars','url':url_for('.cars')})
        # g.menu_items.append({'title':'Photos','url':url_for('.photos')})
        g.menu_items.append({'title':'Account','url':url_for('.account')})
        g.menu_items.append({'title':'Log Out','url':url_for('.logout')})

    
    # # This makes a drop down menu for this application
    # g.admin.register(models.TripSegment,url_for('trip_segment.display'),display_name='Trip Logging',header_row=True,minimum_rank_required=500,roles=['admin',])
    # g.admin.register(models.TripSegment,
    #     url_for('trip_segment.display'),
    #     display_name='Trip Segments',
    #     top_level=False,
    #     minimum_rank_required=500,
    # )
        
        
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