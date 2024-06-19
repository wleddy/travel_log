
function delete_photo_from_list(which){
    if(confirm("Delete this Photo?")){
        $('#log_photo_list').load('/travel_log/log_photo/delete_from_log/'+which.toString())
    }
}

function load_photo_in_list(which){
    $('#log_photo_list').load('/travel_log/log_photo/log_photo_list/'+which.toString());
    }

function show_big_photo(source){
    biggy = $("#log_photo_large");
    biggy.attr("src",source.src)
    $("#log_photo_large_title h3").html(source.name);
    $("#log_photo_large_title p").html(source.title);
    biggy.toggle();
    $("#large_photo_contain").toggle();
    $(".photo_contain").toggle();
}