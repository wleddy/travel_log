from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint, render_template_string
from shotglass2.takeabeltof.utils import printException, cleanRecordID, get_rec_id_if_none
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.views import TableView, EditView

import travel_log.models as models

PRIMARY_TABLE = models.LogPhoto
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
    return edit_photo(rec_id)

def edit_photo(rec_id,**kwargs):
    rec_id = get_rec_id_if_none(rec_id)
    if rec_id < 0:
        flash("Record ID must be greater than 0")
        return redirect(g.listURL)

    view = EditView(PRIMARY_TABLE,g.db,rec_id)
    if not view.next:
        view.next = kwargs.get("next")
        
    if request.form and view.success:
        # Update -> Validate -> Save...
        view.update(save_after_update=True)
        if view.success:
            if view.next:
                return redirect(view.next)
            return redirect(g.listURL)

    return view.render()

@mod.route("/delete_from_log/<int:rec_id>",methods=["POST","GET"])
@mod.route("/delete_from_log/<int:rec_id>/",methods=["POST","GET"])
@mod.route("/delete_from_log",methods=["POST","GET"])
@login_required
def delete_from_log(rec_id=None):
    rec_id = cleanRecordID(rec_id)
    if rec_id > 0:
        rec = PRIMARY_TABLE(g.db).get(rec_id)
        log_id = rec.log_entry_id
        PRIMARY_TABLE(g.db).delete(rec_id)
        return log_photo_list(log_id)
    
    return "<p>Invalid Request</p>"


@mod.route("/log_photo_list/<int:log_id>",methods=["POST","GET"])
@mod.route("/log_photo_list/<int:log_id>/",methods=["POST","GET"])
def log_photo_list(log_id=None):
    """ Returns fully formated html for the log_photos for the log_entry.id
        
    Args: log_id : int
    
    Returns:  str
    
    Raises: None
    """

    log_id=cleanRecordID(log_id)
    
    html = ''

    template = """
        <div class="photo_contain">
        <img src="{{ url_for('static',filename=path) }}" name="{{ title | default('',True )}}" title = "{{ caption | default('',True )}}"
        class="log_photo_small" onclick="show_big_photo(this)" />
        <div class="log_photo_small_delete" onclick="delete_photo_from_list({{id}})">X</div>
        </div>
        </div>
     """
    photos = PRIMARY_TABLE(g.db).select(where=f"log_entry_id = {log_id}")
    if photos:
        for photo in photos:
            html += render_template_string(template, **photo.asdict())
    else:
        html = "<p>No images found</p>"

    return html



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