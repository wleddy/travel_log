from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint
from shotglass2.takeabeltof.utils import printException, cleanRecordID, is_mobile_device
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.date_utils import date_to_string, local_datetime_now
from shotglass2.takeabeltof.views import TableView, EditView
from shotglass2.takeabeltof.jinja_filters import plural
from shotglass2.users.models import User

import travel_log.models as models

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


    view.edit_fields = []
    options = []
    user = User(g.db).get(session.get('user'))
    if user:
        cars = models.Vehicle(g.db).select(where=f"user_id = {user.id}")
    if cars:
        trips = models.Trip(g.db).select(where=f"vehicle_id in ({','.join([str(car.id) for car in cars ] )})")
        if trips:
            for trip in trips:
                options.append({'name':f'{trip.name}','value':trip.id})
            view.edit_fields.append({'name':'trip_id','type':'select','label':'Trip','req':True,'options':options,})
        else:
            flash('You must have at least one Trip',category="warning")
            return redirect(g.listURL)
    else:
        flash('You must have at least one Vehicle',category="warning")
        return redirect(g.listURL)

    
    view.edit_fields.extend(
        [
        {'name':'location_name','req':True,},
        {'name':'entry_type','req':True,'type':'select','options':[
            {'name':'Departure'},
            {'name':'Point of Interest'},
            {'name':'Arrival'},
        ]},
        ]
    )    
    if is_mobile_device():
        view.use_anytime_date_picker = False

    view.edit_fields.append({'name':'entry_date','type':'label_only','label':'When','id':'entry_date_label'})
    entry_date_dict = {'name':'entry_date','type':'datetime','raw':True,'content':''}
    if is_mobile_device():
        field_type = 'datetime-local' #Safari like this. I like it for mobile
    else:
        field_type = 'datetime' # I like this one better for Desktop

    content = f"""
    <div class="w3-row" >
    <p>
        <input name="entry_date" class="w3-input w3-col l10 m10 s10" type="{field_type}" id="entry_date" value="{date_to_string(rec.entry_date,'iso_datetime')}" />
        <input class="w3-col l2 m2 s2 w3_button w3-round-large w3-primary-color" type="button" name="Now" value="Now" />
    </p>
    </div>
    """
    
    entry_date_dict['content'] = content

    view.edit_fields.extend([entry_date_dict])

    view.edit_fields.extend(
        [
        {'name':'memo','type':'textarea',},
        {'name':'longitude','type':'number'},
        {'name':'latitude','type':'number'},
        {'name':'odometer','type':'number'},
        {'name':'projected_range','type':'number'},
        {'name':'fuel_qty','type':'number','label':'Fuel Quantity as % of Full','placeholder':'00%'},
        {'name':'charging_rate','type':'number','label':'Max Charging Rate (Electric Only)'},
        {'name':'fuel_cost','type':'number'},
        ]
    )
    
    

    # Some methods in view you can override
    view.validate_form = validate_form # view does almost no validation
    # view.after_get_hook = ? # view has just loaded the record from disk
    # view.before_commit_hook = ? # view is about to commit the record

    # Process the form?
    if request.form:
        view.update(save_after_update=True)
        if view.success:
            return redirect(g.listURL)

    # otherwise send the list...
    return view.render()

    
def validate_form(view):
    # Validate the form
    valid_form = True
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
                valid_form = False
            
    return valid_form


    
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