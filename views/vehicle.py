from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID, get_rec_id_if_none
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural

import travel_log.models as models

PRIMARY_TABLE = models.Vehicle
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY

mod = Blueprint(MOD_NAME,__name__, template_folder='templates/', url_prefix=f'/travel_log/{MOD_NAME}')


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
    
    view = TableView(PRIMARY_TABLE,g.db)
    # optionally specify the list fields
    # view.list_fields = [
    #     ]
    
    return view.dispatch_request()
    

## Edit the PRIMARY_TABLE
@mod.route('/edit', methods=['POST', 'GET'])
@mod.route('/edit/', methods=['POST', 'GET'])
@mod.route('/edit/<int:rec_id>/', methods=['POST','GET'])
@table_access_required(PRIMARY_TABLE)
def edit(rec_id=None):
    setExits()
    g.title = "Edit {} Record".format(g.title)
    return edit_vehicle(rec_id)

def edit_vehicle(rec_id=None,**kwargs):
    # import pdb;pdb.set_trace()
    rec_id = get_rec_id_if_none(rec_id)
    if rec_id < 0:
        flash("Record ID must be greater than 0")
        return redirect(g.listURL)
        
    view = EditView(models.Vehicle,g.db,rec_id)

    view.validate_form = validate_form
    view.base_layout = "travel_log/form_layout.html"
    view.after_get_hook = after_view_get
    view.edit_fields = get_edit_field_list()
    # view.delete = delete
    if not view.next:
        view.next = kwargs.get("next") 
        
    # Process the form?
    if request.form and view.success:
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)
            
    #else display the form
    return view.render()

    # view = EditView(PRIMARY_TABLE,g.db,rec_id)
    # view.edit_fields = get_edit_field_list()

    # if request.form and view.success:
    #     # Update -> Validate -> Save...
    #     view.update(save_after_update=True)
    #     if view.success:
    #         if view.next:
    #             return redirect(view.next)
    #         return redirect(g.listURL)

    # return view.render()

def after_view_get(view):
    # import pdb;pdb.set_trace()
    if request.form:
        # In the case where a submit failed, load the form values
        view.table.update(view.rec,request.form)
    if view.rec and not view.rec.id and not view.rec.user_id:
        # a new record
        view.rec.user_id = int(session.get('user_id',0))


def validate_form (view):
    # Validate the form
    goodForm = True
                
    return goodForm


def get_edit_field_list() ->list:
    """
    Return a list fields to display in the edit form

    Returns:
        list of dicts
    """
    from shotglass2.users.models import User

    edit_fields = [
        {'name':'name','req':True},
    ]
    options = []
    recs = models.FuelType(g.db).select()
    for rec in recs:
        options.append({'name':rec.name,'value':rec.name})
    edit_fields.append({'name':'fuel_type','type':'select', 'options': options,})
    edit_fields.append({'name':'fuel_capacity','type':'num','label':'Fuel Capacity in kWh, Gal. or Hours','class':'keypad_input'})
    edit_fields.append({'name':'battery_health','type':'num','label':'Battery Health as %','class':'keypad_input','default':100,})
    
    user_options = []
    users = User(g.db).select()
    for user in users:
        user_options.append({'name':f'{user.full_name}','value':user.id})
    edit_fields.append({'name':'user_id','type':'select','label':'User','options':user_options,})

    return edit_fields


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
        display_name='Trip Segments',
        top_level=False,
        minimum_rank_required=500,
    )

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