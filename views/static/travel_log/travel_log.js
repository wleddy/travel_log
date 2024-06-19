
function delete_photo_from_list(which){
    if(confirm("Delete this Photo?")){
        $('#log_photo_list').load('/travel_log/log_photo/delete_from_log/'+which.toString())
    }
}

function load_photo_in_list(which){
    $('#log_photo_list').load('/travel_log/log_photo/log_photo_list/'+which.toString());
    }