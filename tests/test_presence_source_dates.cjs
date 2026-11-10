/* Verify the presence dashboard includes disconnected Wi-Fi trackers and
 * shows accurate source update / persisted last Home times. No browser needed.
 */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent="";this.style={};this.attributes={};}
  attachShadow(){this.shadowRoot=new Element("shadow");return this.shadowRoot;}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  addEventListener(){}
}
const classes=new Map();
const code=fs.readFileSync(path.join(__dirname,
  "../custom_components/device_availability_digest/www/managed-panel.js"),"utf8")
  .replaceAll("import.meta.url",
    JSON.stringify("https://localhost/local/managed-panel.js?v=0.3.7"));
const context={
  URL,Date,Math,String,JSON,Object,Array,Number,
  HTMLElement:Element,
  document:{createElement:tag=>new Element(tag)},
  customElements:{get:tag=>classes.get(tag),define:(tag,cls)=>classes.set(tag,cls)}
};
vm.runInNewContext(code,context);
const Panel=classes.get("availability-diagnostics-managed-panel-v0-3-7");
assert.ok(Panel);
const panel=new Panel();

function strings(node,result=[]){
  if(node.textContent)result.push(String(node.textContent));
  for(const child of node.children||[])strings(child,result);
  return result;
}
const lastHome="2026-11-07T17:00:00+00:00";
const p=panel._sourceEvidence("device_tracker.wifi_phone",{
  state:"not_home",
  last_updated:"2026-11-09T07:00:00+00:00",
  attributes:{friendly_name:"Phone Wi-Fi",ip:"192.0.2.2"}
},lastHome);
const labels=strings(p).join(" ");
assert.match(labels,/Phone Wi-Fi/);
assert.match(labels,/not_home/);
assert.match(labels,/Last update/);
assert.match(labels,/Last seen Home/);
assert.match(labels,/2026|Nov/);
assert.equal(p.children[1].children[1].children[1].dateTime,lastHome);

const tracker={
  state:"not_home",last_reported:"2026-11-09T08:30:00+00:00",
  last_updated:"2026-11-08T08:00:00+00:00",attributes:{}
};
const person=panel._sourceEvidence("person.child",{
  state:"not_home",last_updated:"2026-11-09T08:00:00+00:00",
  attributes:{source:"device_tracker.child_gps"}
},null,{isPerson:true,tracker});
assert.match(strings(person).join(" "),/Last GPS tracker update/);
assert.equal(person.children[1].children[0].children[1].dateTime,
  tracker.last_reported,"Use GPS tracker report time rather than Person update");

const grid=new Element("main");
panel._hass={states:{
  "sensor.home_presence":{state:"unknown",attributes:{
    tracked_people:["person.child"],
    active_home_evidence:[],
    labeled_home_sources:["device_tracker.wifi_phone","device_tracker.offline_phone"]
  }},
  "person.child":{
    state:"not_home",last_updated:"2026-11-09T08:00:00+00:00",
    attributes:{source:"device_tracker.child_gps"}
  },
  "device_tracker.child_gps":tracker,
  "device_tracker.wifi_phone":{
    state:"not_home",last_updated:"2026-11-09T07:00:00+00:00",
    attributes:{friendly_name:"Phone Wi-Fi"}
  },
  "device_tracker.offline_phone":{
    state:"unavailable",last_updated:"2026-11-09T07:30:00+00:00",
    attributes:{friendly_name:"Offline phone"}
  }
}};
panel._presence(grid,{
  presence:"unknown",events:[],
  source_last_home:{"device_tracker.wifi_phone":lastHome}
});
const full=strings(grid).join(" ");
assert.match(full,/Phone Wi-Fi/,"Offline Wi-Fi tracker must remain in the list");
assert.match(full,/Offline phone/,"Unavailable tracker must remain visible");
assert.match(full,/Last seen Home/);
assert.match(full,/Last GPS tracker update/);
assert.doesNotMatch(full,/Only Companion App.*establishes Away/,
  "Old incorrect Away rule must not remain in dashboard");
// The summary and the mode-history timeline must share their exact palette.
const statusCard=grid.children[0];
assert.equal(statusCard.children[1].textContent,"Unknown");
assert.equal(statusCard.children[1].style.color,"#949ba4");
for(const [state,label,color] of [
  ["home","Home","#218657"],
  ["away","Away","#d38221"],
  ["unavailable","Unavailable","#949ba4"]
]){
  panel._hass.states["sensor.home_presence"].state=state;
  const stateGrid=new Element("main");
  panel._presence(stateGrid,{presence:state,events:[],source_last_home:{}});
  assert.equal(stateGrid.children[0].children[1].textContent,label);
  assert.equal(stateGrid.children[0].children[1].style.color,color);
}
assert.equal(panel._stat("Tracked people",2,"People").children[1].style.color,
  undefined,"Only the presence-state summary should have mode coloring");
console.log("Home Presence source dates and shared status/timeline colors verified");
