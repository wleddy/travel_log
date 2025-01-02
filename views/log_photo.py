from flask import request, session, g, redirect, url_for, \
     render_template, flash, Blueprint, render_template_string
from shotglass2.takeabeltof.file_upload import FileUpload
from shotglass2.takeabeltof.utils import printException, cleanRecordID, get_rec_id_if_none
from shotglass2.users.admin import login_required, table_access_required
from shotglass2.takeabeltof.views import TableView, EditView
from werkzeug.exceptions import RequestEntityTooLarge

import travel_log.models as models

PRIMARY_TABLE = models.LogPhoto
MOD_NAME = PRIMARY_TABLE.TABLE_IDENTITY
IMAGE_PATH = "travel_log/log_entry"

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
    return list(path)


def list(path,**kwargs):
    view = TableView(PRIMARY_TABLE,g.db)
    # optionally specify the list fields
    # view.list_fields = [
    #     ]
    
    return view.dispatch_request(**kwargs)
    

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
    next = kwargs.get('next',g.listURL)
    try:
        rec_id = get_rec_id_if_none(rec_id)
    except RequestEntityTooLarge as e:
        # This error is raised as soon as you try to access the request.form if too large
        flash("The image file you submitted was too large. Maximum size is {} MB".format(request.max_content_length/1048576))
        return redirect(next)
    except Exception as e:
        mes = (f"An unexpected error occured: {str(e)}")
        printException(mes,level='error',err=e)
        flash(mes)
        return redirect(next)

    if rec_id < 0:
        flash("Record ID must be greater than 0")
        return redirect(next)
        
    view = EditView(PRIMARY_TABLE,g.db,rec_id)
    # import pdb;pdb.set_trace()
    view.edit_fields = get_edit_field_list(view,**kwargs)
    view.validate_form = validate_form
    if not view.next:
        view.next = kwargs.get("next")
    
    upload = FileUpload() # success is True
    # if there is already a path set, can't add a new one
    if request.form and not view.rec.path and view.success:
        view.update(save_after_update=False)
        if not view.rec.log_entry_id:
            flash('No Log Entry ID provided')
            view.success = False
        else:
            upload = save_photo_to_disk(view.rec.log_entry_id,'log_photo')
            if upload.success:
                view.rec.path = upload.saved_file_path_string

    if request.form and view.success and upload.success:
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


def get_embedded_fields() -> str: 
    """ 
    Return a HTML string representing fields needed to edit a photo record 
    from within the log entry form
    Will be called with render_template_string(rec) with a photo record

    Args: None

    Returns:  str

    Raises: None
    """

    embedded_fields =   """
    <div id="embedded_photo_fields" >
    <p class="form_button_row w3-contain w3-panel" >
	<input type=submit title="Click to Save" class="{{ base_class }} w3-save-button-color" value='{{ save_value | safe }}' />&nbsp;&nbsp;
	{% if rec.id and rec.id > 0 and (not no_delete or is_admin) and not g.cancelURL %}
	<a id="form_delete_link"  class="{{ base_class }} w3-delete-button-color" title="Click to Delete" href = "{{g.deleteURL}}{{rec.id}}/{{ next }}" onclick="return confirmRecordDelete();">{{ delete_value | safe }}</a>&nbsp;&nbsp;
	{% endif %}
    <a  class="{{ base_class }} w3-cancel-button-color" title="Click to Cancel" href="{% if g.cancelURL %}{{g.cancelURL}}{{ next }}{% else %}{{ g.listURL }}{{ next }}{% endif %}" >{{ cancel_value | safe }}</a>
    </p> 
    <input type="hidden" name="photo_id" id="photo_id" value="{{ rec.id | default(0,True)}}" >
    <p><label class="w3-block w3-label-color">Title</label></p>
    <p><input class="w3-input None" type="text" name="title" data-label="Title" id="title"
        value="{{ rec.title | default('',True)}" 
        >
    </p>
    <p><label class="w3-block w3-label-color">Caption</label></p>
    <p>
        <input class="w3-input" type="text" name="caption" data-label="Caption" id="caption"
        value="{{ rec.caption | default('',True)}}" >
    </p>
    <input type="hidden" name="path" id="path" value="{{ rec.path | default('',True)}}" >
    {% if rec.path %}
    <div class="photo_contain">
        {% if rec.path %}{% set filepath=rec.path %}{% else %}{% set filepath = '' %}{% endif %}
        <img src="{{ url_for('static',filename=f'{rec.path}')}}" name="log_photo_large" id="log_photo_large" alt="a big one" >
    </div>
    {% else %}
    <input type="file" name="log_photo" id="log_photo" style="display:none;">
    {% endif %}
    </div>
    """
    return embedded_fields


def get_edit_field_list(view,**kwargs) -> list:
    edit_fields = [
        {'name':'title','type':'text','default':'',},
        {'name':'caption','type':'text','default':'',},
    ]
    log_id = view.rec.log_entry_id
    # display a select list of log entries?
    sql = """
    select log_entry.*, trip.name as trip_name from log_entry
    join trip on trip.id = log_entry.trip_id
    order by trip.id
    """
    log_entries = models.LogEntry(g.db).query(sql)
    options = []
    if log_entries:
        for log in log_entries:
            options.append({'name':f'{log.trip_name}: {log.location_name}','value':log.id})
        edit_fields.extend([
            {"name":"log_entry_id","type":"select",'options':options,'label':'Log Entry'}, 
        ])
    else:
        edit_fields.extend(
            [{'name':'log_entry_id','type':'hidden','default':log_id,},
            ]
        )

    if view.rec.path:
        # display image
        img_src = url_for('static',filename=view.rec.path)
        entry_dict = {'name':"log_photo","code":True,"label":None,'content':''}
        entry_dict["content"] = f"""
        <div id="log_photo_contain">
            <img src="{img_src}" style="width:100%;" />
        </div>
        """
        edit_fields.extend([entry_dict])
    else:
        edit_fields.extend([
        {"name":"log_photo","type":"file","label":"Pick a Photo",},
        ])

    return edit_fields


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

def save_photo_to_disk(log_id,form_element='image_file'):
    """ Save an image file if in request.files to disk
    
    Args: log_id : int ; The id of the log file to associate with the image
          form_element : str ; The name of the request.files element containing the image
    
    Returns:  upload : FileUpload
    
    Raises: None
    """

    upload = FileUpload(local_path='{}/{}'.format(IMAGE_PATH.rstrip('/'),log_id))
    file = request.files.get(form_element)
    if file and file.filename:
        filename = file.filename
        x = filename.find('.')
        if x > 0:
            upload.save(file,filename=filename,max_size=1000)
            if not upload.success:
                flash(upload.error_text)
                upload.success = False
        else:
            # there must be an extenstion
            flash('The image file must have an extension at the end of the name.')
            upload.success = False
    else:
        # This may not be an error if no file was submitted
        upload.success = False

    return upload

    
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