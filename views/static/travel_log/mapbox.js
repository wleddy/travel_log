
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