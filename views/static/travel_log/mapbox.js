
mapboxgl.accessToken = 'pk.eyJ1IjoiYmxlZGR5IiwiYSI6ImNpanh3endiNzFlNm12Mm01YjUwcmt0dzEifQ.Fgy28_Hfzzl_WEvN_ur2xQ';

function make_map(map_div_id,location=undefined){
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
    style: 'mapbox://styles/bleddy/ck7mere9w0g8k1inv74yyvgl6',
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
  return map;
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

//async function setWayPoint(location){
//    if((currentLocError == false) && (currentLat != undefined ) && (currentLng != undefined)){
//        location = {"lat":currentLat,"lng":currentLng,"trip_id":globalTripID}
//
//        // send it to the server
//        const query = await fetch(
//        `{{config["HOST_PROTOCOL"]}}://{{config["HOST_NAME"]}}/travel_log/log_entry/log_waypoint/`+ JSON.stringify(location),
//        { method: 'GET' }
//        );
//        const response = await query;
//        //alert(response);
//    }
//
//}
//function waypointHandler(){
//    setWayPoint();
//}

//let waypointer = setInterval(waypointHandler,60000);

let globalCoords;
let globalTripID = 1;

function show_more(which) {
    $("#" + which + " span").toggle(500)
}
function onMapClick(e) {
    // alert("You clicked the map at " + e.lngLat.lng + "," + e.lngLat.lat);
    //marker = add_marker(map,e.lngLat.lng,e.lngLat.lat);
    //setWayPoint({"lat":e.lngLat.lat,"lng":e.lngLat.lng,"trip_id":globalTripID})
    //globalCoords.splice(1,0, [e.lngLat.lng,e.lngLat.lat])
    ////updateRoute(globalCoords)
}


function create_map() {
    map = make_map("map",map_center);
    map.dragRotate.disable();
    map.on('click', onMapClick);
    $('#map').show();
}
// coords = {'points':['geometry':{'coordinates':[-121.6, 38.8],},'properties':{'title':'Coffee Works'}],'match_path':[[-121.6, 38.8],[-121.6, 38.8]]}
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
        } else {
            marker.addClassName("marker-WAY");
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
    for (var loc of globalCoords){
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


//function updateRoute(coords) {
//    removeRoute(); // Overwrite any existing layers
//
//    const profile = 'driving'; // Set the profile
//     // Set the radius for each coordinate pair to 25 meters
//    const radius = globalCoords.map(() => 50);
//    // Format the coordinates
//    newCoords = globalCoords.join(';');
//    // matching only seems to work for very short distances for me...
//    getMatch(newCoords, radius, profile);
//  }

    // // Make a Map Matching request
    // async function getMatch(coordinates, radius, profile) {
    //   // Separate the radiuses with semicolons
    //   const radiuses = radius.join(';');
    //   // Create the query
    //   const query = await fetch(
    //     `https://api.mapbox.com/matching/v5/mapbox/${profile}/${coordinates}?geometries=geojson&radiuses=${radiuses}&steps=false&access_token=${mapboxgl.accessToken}`,
    //     { method: 'GET' }
    //   );
    //   const response = await query.json();
    //   // Handle errors
    //   if (response.code !== 'Ok') {
    //       if(response.message !== "All coordinates are too far away from each other")
    //       {
    //       alert(
    //           `${response.code} - ${response.message}.\n\nFor more information: https://docs.mapbox.com/api/navigation/map-matching/#map-matching-api-errors`
    //       );
    //       }
    //     return;
    //   } else {
    //       // Draw the route on the map
    //       addRoute(response.matchings[0].geometry);
    //   }
//
    // }

//  // Draw the Map Matching route as a new layer on the map
//  function addRoute(coords) {
//    // If a route is already loaded, remove it
//    /*
//    if (map.getSource('route')) {
//      map.removeLayer('route');
//      map.removeSource('route');
//    } else {
//     */
//      map.addLayer({
//        'id': 'route',
//        'type': 'line',
//        'source': {
//          'type': 'geojson',
//          'data': {
//            'type': 'Feature',
//            'properties': {},
//            'geometry': coords
//          }
//        },
//        'layout': {
//          'line-join': 'round',
//          'line-cap': 'round'
//        },
//        'paint': {
//          'line-color': '#03AA46',
//          'line-width': 8,
//          'line-opacity': 0.8
//        }
//      });
//    }
//  //}
//
//  // If the user clicks the delete draw button, remove the layer if it exists
//  function removeRoute() {
//    if (!map.getSource('route')) return;
//    map.removeLayer('route');
//    map.removeSource('route');
//  }

//function _setCurrentLoc(position){
//    //use coordinates
//    currentLat = position.coords.latitude;
//    currentLng = position.coords.longitude;
//    currentLocError = false
//    $('#geoLng').html(currentLng);
//    $('#geoLat').html(currentLat);
//    setWayPoint();
//}
//
//const geoWatchID = navigator.geolocation.watchPosition((position) => {
//    _setCurrentLoc(position);
//});

var map;
var marker;
var map_bounds;
var map_center;
let currentLat, currentLng, currentLocError;
currentLocError = false;