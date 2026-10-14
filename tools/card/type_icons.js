/* Fixed Material Design Icons (Pictogrammers), Apache-2.0.
 * Source/provenance and license: frontend/licenses/material-design-icons.txt.
 * Inline paths avoid icon-font, image-service or Home Assistant lazy-load races
 * inside MapLibre markers. Only this allowlist can become SVG markup.
 */
const OSM_PARKING_GLYPHS = Object.freeze({
  paid: Object.freeze({name:'cash',path:'M3,6H21V18H3V6M12,9A3,3 0 0,1 15,12A3,3 0 0,1 12,15A3,3 0 0,1 9,12A3,3 0 0,1 12,9M7,8A2,2 0 0,1 5,10V14A2,2 0 0,1 7,16H17A2,2 0 0,1 19,14V10A2,2 0 0,1 17,8H7Z'}),
  open: Object.freeze({name:'parking',path:'M13.2,11H10V7H13.2A2,2 0 0,1 15.2,9A2,2 0 0,1 13.2,11M13,3H6V21H10V15H13A6,6 0 0,0 19,9C19,5.68 16.31,3 13,3Z'}),
  street: Object.freeze({name:'road-variant',path:'M18.1,4.8C18,4.3 17.6,4 17.1,4H13L13.2,7H10.8L11,4H6.8C6.3,4 5.9,4.4 5.8,4.8L3.1,18.8C3,19.4 3.5,20 4.1,20H10L10.3,15H13.7L14,20H19.8C20.4,20 20.9,19.4 20.8,18.8L18.1,4.8M10.4,13L10.6,9H13.2L13.4,13H10.4Z'}),
  underground: Object.freeze({name:'tunnel',path:'M12 2C6.5 2 2 6.5 2 12V22H22V12C22 6.5 17.5 2 12 2M7.1 5.69C8.21 4.83 9.54 4.25 11 4.07V6.09C10.09 6.24 9.25 6.6 8.53 7.11L7.1 5.69M15.47 7.11C14.75 6.6 13.91 6.24 13 6.09V4.07C14.46 4.25 15.79 4.83 16.9 5.69L15.47 7.11M5.69 7.1L7.11 8.53C6.6 9.25 6.24 10.09 6.09 11H4.07C4.25 9.54 4.83 8.21 5.69 7.1M6 13V15.5H4V13H6M4 20V17.5H6V20H4M16.89 8.53L18.31 7.1C19.17 8.21 19.75 9.54 19.93 11H17.91C17.76 10.09 17.4 9.25 16.89 8.53M18 13H20V15.5H18V13M18 20V17.5H20V20H18Z'}),
  multi_storey: Object.freeze({name:'office-building',path:'M5,3V21H11V17.5H13V21H19V3H5M7,5H9V7H7V5M11,5H13V7H11V5M15,5H17V7H15V5M7,9H9V11H7V9M11,9H13V11H11V9M15,9H17V11H15V9M7,13H9V15H7V13M11,13H13V15H11V13M15,13H17V15H15V13M7,17H9V19H7V17M15,17H17V19H15V17Z'}),
  park_and_ride: Object.freeze({name:'train-car',path:'M12,4H5A3,3 0 0,0 2,7V15A3,3 0 0,0 5,18L4,19V20H5L7,17.97L9,18V13H4V6H13V8H15V7A3,3 0 0,0 12,4M5,14A1,1 0 0,1 6,15A1,1 0 0,1 5,16A1,1 0 0,1 4,15A1,1 0 0,1 5,14M20.57,9.66C20.43,9.26 20.05,9 19.6,9H12.41C11.95,9 11.58,9.26 11.43,9.66L10,13.77V19.28C10,19.66 10.32,20 10.7,20H11.32C11.7,20 12,19.62 12,19.24V18H20V19.24C20,19.62 20.31,20 20.69,20H21.3C21.68,20 22,19.66 22,19.28V17.91L22,13.77L20.57,9.66M12.41,10H19.6L20.63,13H11.38L12.41,10M12,16A1,1 0 0,1 11,15A1,1 0 0,1 12,14A1,1 0 0,1 13,15A1,1 0 0,1 12,16M20,16A1,1 0 0,1 19,15A1,1 0 0,1 20,14A1,1 0 0,1 21,15A1,1 0 0,1 20,16Z'}),
  other: Object.freeze({name:'map-marker-question',path:'M12,2C8.14,2 5,5.14 5,9C5,14.25 12,22 12,22C12,22 19,14.25 19,9C19,5.14 15.86,2 12,2M12.88,15.75H11.13V14H12.88M12.88,12.88H11.13C11.13,10.04 13.75,10.26 13.75,8.5A1.75,1.75 0 0,0 12,6.75A1.75,1.75 0 0,0 10.25,8.5H8.5A3.5,3.5 0 0,1 12,5A3.5,3.5 0 0,1 15.5,8.5C15.5,10.69 12.88,10.91 12.88,12.88Z'}),
});
function osmIconType(item) {
  const type=typeof item?.category==='string'?item.category:'';
  return Object.prototype.hasOwnProperty.call(OSM_PARKING_GLYPHS,type)?type:'other';
}
function osmTypeIconMarkup(item) {
  const glyph=OSM_PARKING_GLYPHS[osmIconType(item)];
  // Name and path are code-owned constants, never interpolated provider data.
  return `<svg xmlns="http://www.w3.org/2000/svg" class="parking-type-glyph" data-icon="${glyph.name}" viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true" focusable="false"><path d="${glyph.path}"></path></svg>`;
}
