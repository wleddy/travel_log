/* Code shared between the home page and log entry edit page */

function create_log_entry_map(map_div_id,location=undefined){
  // one of my favorite coffee shops...
  let lng = -121.4631;
  let lat = 38.56656;

  if(location != undefined){
    lng = location.lng;
    lat = location.lat;
  }
  else if ($('#lat').length){
      lat = $('#lat').val();
      lng = $('#lng').val();
  } 

  let map = new mapboxgl.Map({
    container: map_div_id,
    style: 'mapbox://styles/mapbox/standard',
    center: [lng, lat],
    zoom: 15
  });

  map.addControl(new mapboxgl.GeolocateControl({
    positionOptions: {
        enableHighAccuracy: true
    },
    trackUserLocation: true,
    showUserHeading: true
}));
    map.addControl(new mapboxgl.ScaleControl({unit: 'imperial'}));
    return map;
}

function goSat(marker){
    map.setStyle('mapbox://styles/mapbox/standard-satellite');
    marker.addClassName('sat-marker');
}
function goNorm(){
    map.setStyle('mapbox://styles/mapbox/standard');
    marker.addClassName('norm-marker');

}
function add_marker(map,lng,lat,html=''){
  // create a HTML element for each marker
  const el = document.createElement('div');
  el.className = 'marker';
  let mkr = new mapboxgl.Marker(el).setLngLat([parseFloat(lng),parseFloat(lat)]);
  if (html != ''){
      mkr.setPopup(
          new mapboxgl.Popup({ offset: 25 }) // add popups
          .setHTML(html)
      )
  }
  mkr.addTo(map);
  return mkr;
}

// ---------------- From Home script -----------------------------------


var tripCoords = [];
var globalTripID = 1;
var map;
var marker;
var map_bounds;
var map_center;
var currentLat, currentLng, currentLocError;
currentLocError = false;

function show_more(which) {
    $("#" + which + " span").toggle(500)
}


function create_trip_map() {
    map = create_log_entry_map("map",map_center);
    map.dragRotate.disable();
    // Add a scale control to the map
    map.addControl(new mapboxgl.ScaleControl({unit: 'imperial'}));
    $('#map').show();
}
// coords = {'points':['geometry':{'coordinates':[-121.6, 38.8],},'properties':{'title':'Coffee Works'}]}
function set_markers(coords){
    // add the set_markers
    for (const point of coords.points){
        marker = add_marker(map,point.geometry.coordinates[0],point.geometry.coordinates[1],'<p class="w3-bold w3-large w3-center" >'+point.properties.entry_type+'<br>'+point.properties.title+'</p>');
        if (point.properties.entry_type == 'POI'){
            marker.addClassName('marker-POI');
        } else if (point.properties.entry_type == 'ARR'){
            marker.addClassName('marker-ARR');
        } else if (point.properties.entry_type == 'DEP'){
            marker.addClassName('marker-DEP')
        } else if (point.properties.entry_type == 'CHA'){
            marker.addClassName('marker-CHA')
        }
    }
    // fit the map to the markers
    map.fitBounds(map_bounds);
}


function get_map_bounds(coords) {
    const nudge = .025; // how much space at edges
    // get the ne most and se most points
    let _ne =[-180,-90];
    let _sw = [180,90];
    for (var loc of tripCoords){
        if(loc[0]>_ne[0]){_ne[0]=loc[0];}
        if(loc[1]>_ne[1]){_ne[1]=loc[1];}
        if(loc[0]<_sw[0]){_sw[0]=loc[0];}
        if(loc[1]<_sw[1]){_sw[1]=loc[1];}
    }
    const bounds = new mapboxgl.LngLatBounds(_sw,_ne);
    const ne = bounds.getNorthEast();
    ne.lat = ne.lat + (nudge * (Math.abs(ne.lat)/90));
    ne.lng = ne.lng + nudge;
    bounds.setNorthEast(ne);
    const sw = bounds.getSouthWest();
    sw.lat = sw.lat - (nudge * (Math.abs(sw.lat)/90));
    sw.lng = sw.lng - nudge;
    bounds.setSouthWest(sw);

    return bounds;
}
