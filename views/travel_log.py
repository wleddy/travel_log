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
    return render_template('home.html')

@mod.route('logout/',methods=['GET',])
def logout():
    """ log a user out """
    setExits()
    return redirect(url_for('login.logout') + f'?next={url_for(".home")}')

@mod.route('login/',methods=['GET',])
def login():
    """ log a user out """
    setExits()
    if user in session:
        return redirect(url_for('.home'))
    
    return redirect(url_for('login.login') + f'?next={url_for(".home")}')

@mod.route('new_account/',methods=['GET',])
def new_account():
    """ log a user out """
    setExits()
    if user in session:
        return redirect(url_for('.home'))
    
    return redirect(url_for('user.register') + f'?next={url_for(".home")}')

@mod.route('trips/',methods=['GET',])
def trip_list():
    """ display the list of trips """
    setExits()
    if not user in session:
        return redirect(url_for('.login'))
    data = {}

    return render_template('home.html',data=data)

    
def validForm(rec):
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
        g.menu_items.append({'title':'Trips','url':url_for('.trip_list')})
        # g.menu_items.append({'title':'Cars','url':url_for('.cars')})
        # g.menu_items.append({'title':'Photos','url':url_for('.photos')})
        # g.menu_items.append({'title':'Account','url':url_for('.user_edit')})
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