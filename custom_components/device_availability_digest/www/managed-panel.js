/* Integration-managed Availability & Home Presence diagnostics.
 * Uses Home Assistant theme variables, tabs and responsive cards like the
 * managed Tado X and Tylö dashboards. Read-only, administrator-only API.
 */
const version=new URL(import.meta.url).searchParams.get("v")||"dev";
const tag="availability-diagnostics-managed-panel-v"+version.replace(/\./g,"-");
const pickerTag="availability-date-range-picker-v"+version.replace(/\./g,"-");
const css=`
:host{display:block;min-height:100%;background:var(--primary-background-color,#fafafa);color:var(--primary-text-color,#202124);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
*{box-sizing:border-box}
.shell{max-width:1450px;margin:0 auto;padding:24px clamp(12px,3vw,30px) 45px}
.heading{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px}
.heading-group{display:flex;align-items:center;gap:10px;min-width:0;flex:1 1 auto}
.ha-mobile-menu{display:none;align-items:center;justify-content:center;width:40px;height:40px;flex:0 0 40px;padding:8px;border:0;border-radius:50%;background:transparent;color:inherit;cursor:pointer}
.ha-mobile-menu:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
@media(max-width:870px){.ha-mobile-menu{display:inline-flex}}
h1{font-size:29px;line-height:1.3;font-weight:600;margin:0}
h2{font-size:19px;font-weight:600;margin:0 0 14px}
h3{font-size:15px;font-weight:600;margin:0 0 7px}
.subtitle,.muted{color:var(--secondary-text-color,#777)}
.subtitle{margin:6px 0 2px;font-size:14px}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:21px 0 16px}
.btn,.tab{font:inherit;border:1px solid var(--divider-color,#d7d7d7);background:var(--card-background-color,#fff);color:var(--primary-text-color);border-radius:10px;padding:9px 15px;cursor:pointer}
.btn[aria-pressed=true],.tab[aria-selected=true]{color:var(--primary-color,#1769aa);border-color:var(--primary-color,#1769aa);background:var(--secondary-background-color,#f1f6fa);font-weight:600}
.btn:hover,.tab:hover{border-color:var(--primary-color,#1769aa)}
.tabs{display:flex;gap:9px;border-bottom:1px solid var(--divider-color,#ddd);padding-bottom:11px;flex-wrap:wrap}
.tab{border-radius:9px}
.card{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:14px;padding:20px;min-width:0}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;margin-top:16px}
.span4{grid-column:span 4}.span6{grid-column:span 6}.span8{grid-column:span 8}.span12{grid-column:span 12}
.stat{font-size:31px;font-weight:650;margin-top:6px}
.badge{display:inline-block;padding:4px 10px;border-radius:99px;background:var(--secondary-background-color,#eee);color:var(--primary-text-color);font-size:12px;font-weight:600}
.badge.home,.badge.recovered{background:#e4f3e9;color:#1a743c}
.badge.stale,.badge.suspect,.badge.away,.badge.offline{background:#fff0e8;color:#a34315}
.badge.unknown{background:#f6f0df;color:#7b6420}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pill{font-size:12px;border-radius:6px;padding:6px 8px;background:var(--secondary-background-color,#efefef);overflow-wrap:anywhere}
.evidence-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:10px;margin:10px 0 22px}
.evidence-item{padding:12px;border:1px solid var(--divider-color,#ddd);border-radius:10px;min-width:0}
.evidence-name{font-size:13px;font-weight:600;overflow-wrap:anywhere}
.evidence-sub{font-size:11px;color:var(--secondary-text-color,#777);overflow-wrap:anywhere;margin-top:3px}
.evidence-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:9px}
.evidence-dates{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.evidence-dates>div{min-width:0}
.evidence-dates small{display:block;font-size:11px;color:var(--secondary-text-color,#777)}
.evidence-dates time{display:block;font-size:12px;overflow-wrap:anywhere;margin-top:3px}
@media(max-width:460px){.evidence-dates{grid-template-columns:1fr}}
.small{font-size:12px}.error{color:var(--error-color,#b33);margin:12px 0;white-space:pre-wrap}
.search{display:block;width:100%;padding:11px;border-radius:9px;border:1px solid var(--divider-color,#ddd);background:var(--primary-background-color,#fff);color:inherit;font:inherit;margin-bottom:12px}
.mode-track{position:relative;height:40px;background:var(--secondary-background-color,#eee);border-radius:7px;overflow:hidden;margin-top:14px}
.mode-segment{position:absolute;top:0;height:100%;min-width:1px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;white-space:nowrap;overflow:hidden}
.mode-empty{position:absolute;left:12px;top:12px;font-size:12px;color:var(--secondary-text-color,#777)}
.mode-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px;font-size:12px}
.mode-legend-item{display:inline-flex;align-items:center;gap:6px}
.mode-swatch{width:11px;height:11px;border-radius:3px}
.timeline{display:flex;align-items:flex-end;gap:4px;min-height:110px;overflow-x:auto;padding:7px 1px 4px;border-bottom:1px solid var(--divider-color,#ddd)}
.barcol{min-width:9px;max-width:24px;flex:1 0 9px;display:flex;flex-direction:column;justify-content:end;height:96px}
.bar{width:100%;border-radius:3px 3px 0 0;min-height:0;background:var(--primary-color,#367cbb)}
.bar.alt{background:var(--warning-color,#e9903a)}
.chartlabels{display:flex;justify-content:space-between;color:var(--secondary-text-color);font-size:11px;margin-top:6px}
.event{border-top:1px solid var(--divider-color,#ddd);padding:12px 0}
.event summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.event summary::-webkit-details-marker{display:none}
.eventtitle{display:flex;gap:9px;align-items:center;flex-wrap:wrap;min-width:0}
.eventname{font-weight:600;overflow-wrap:anywhere}
.time{flex:0 0 auto;color:var(--secondary-text-color);font-size:12px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6;padding:12px;background:var(--secondary-background-color,#f4f4f4);border-radius:8px;font-size:12px;max-height:430px;overflow-y:auto}
.empty{padding:24px 5px;color:var(--secondary-text-color);text-align:center}
.foot{color:var(--secondary-text-color);font-size:12px;margin:24px 0}
.statusrow{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
a{color:var(--primary-color,#2673bc)}
@media(max-width:950px){.span4,.span6,.span8{grid-column:span 12}.shell{padding-top:17px}}
`;
const E=(name,text,className)=>{
  const el=document.createElement(name);
  if(text!==undefined&&text!==null)el.textContent=String(text);
  if(className)el.className=className;
  return el;
};
const fmt=(ts)=>{if(!ts)return "—";const d=new Date(ts);return isNaN(d)?String(ts):d.toLocaleString();};
const statusClass=(s)=>String(s||"").toLowerCase();
const MODE_COLORS={home:"#218657",away:"#d38221",unknown:"#949ba4",unavailable:"#949ba4"};
const modeState=value=>{
  const state=String(value??"unknown").toLowerCase();
  return Object.hasOwn(MODE_COLORS,state)?state:"unknown";
};
const modeLabel=value=>value==="home"?"Home":value==="away"?"Away":
  value==="unavailable"?"Unavailable":"Unknown";
const modeEpoch=entry=>{
  const value=entry.lu??entry.lc??entry.last_changed??entry.last_updated;
  if(typeof value==="number")return value<1e11?value*1000:value;
  const at=Date.parse(value);
  return Number.isFinite(at)?at:NaN;
};
const isSourceDetails=e=>e.kind==="presence_details"||
  (e.kind==="presence_source"&&e.previous!=null&&e.previous===e.state);
const eventTitle=(e)=>{
  if(e.kind==="presence_state")return "Household: "+(e.previous??"initial")+" → "+(e.state??"unknown");
  if(isSourceDetails(e))return "Source details updated: "+(e.name||e.entity_id||"Source")+
    " (still "+(e.state??"unknown")+")";
  if(e.kind==="presence_source")return (e.name||e.entity_id||"Source")+": "+(e.previous??"unknown")+" → "+(e.state??"unknown");
  if(e.kind==="availability_digest"||e.kind==="stale_digest")
    return "Email sent: "+(e.title||e.event||"Summary");
  if(e.kind==="stale_measurement")
    return (e.event||"MEASUREMENT")+": "+(e.name||e.entity_id||"sensor");
  return (e.event||"AVAILABILITY")+": "+(e.name||e.entity_id||"device");
};
class AvailabilityDiagnosticsManagedPanel extends HTMLElement{
  constructor(){
    super();this.attachShadow({mode:"open"});
    this._hass=null;this._tab="presence";this._data=null;this._staleShowAll=false;
    const start=new Date();start.setHours(0,0,0,0);start.setDate(start.getDate()-6);
    const end=new Date();end.setHours(0,0,0,0);end.setDate(end.getDate()+1);
    this._range={start:start.toISOString(),end:end.toISOString(),preset:"last7"};
    this._pickerReady=false;this._pickerPromise=null;this._pickerError="";
    this._loading=false;this._reloadQueued=false;this._error="";this._search="";this._tick=null;
    this._lastLoad=0;this._route=null;this._narrow=false;this._panel=null;
    this._modeHistory=[];this._modeHistoryKey="";this._modeHistoryError="";
    this._modeHistoryLoading=false;this._modeRequest=0;
  }
  set hass(v){
    this._hass=v;
    if(this._picker?.isConnected)this._picker.hass=v;
    if(this.isConnected && !this._data && !this._loading)this._load();
  }
  set panel(v){this._panel=v;}
  set route(v){this._route=v;const p=(v?.path||"").split("/").filter(Boolean)[0];
    if((p==="devices"||p==="presence"||p==="stale")&&p!==this._tab){
      this._tab=p;this._render();
      if(p==="presence")this._loadModeHistory();
    }}
  set narrow(v){this._narrow=!!v;}
  async _ensurePicker(){
    if(this._pickerReady||this._pickerPromise)return this._pickerPromise;
    this._pickerPromise=import("./availability-date-range-picker.js?v="+encodeURIComponent(version))
      .then(mod=>{
        if(typeof mod.avPresetRange!=="function")throw Error("Date range selector unavailable");
        this._pickerReady=true;this._pickerError="";
        if(this.isConnected)this._render();
      })
      .catch(error=>{
        this._pickerError=error?.message||String(error);
        if(this.isConnected)this._render();
      })
      .finally(()=>{this._pickerPromise=null;});
    return this._pickerPromise;
  }
  connectedCallback(){
    this._render();
    this._ensurePicker();
    if(this._hass)this._load();
    this._tick??=setInterval(()=>this._load(),60000);
  }
  disconnectedCallback(){
    this._modeRequest++;
    if(this._tick!==null){clearInterval(this._tick);this._tick=null;}
  }
  async _load(){
    if(this._loading){this._reloadQueued=true;return;}
    if(!this._hass?.callWS)return;
    if(this._tab==="presence")this._loadModeHistory();
    this._loading=true;
    const selected={...this._range};
    try{
      const data=await this._hass.callWS({
        type:"device_availability_digest/history",
        start_time:selected.start,end_time:selected.end,limit:5000
      });
      if(!this.isConnected)return;
      if(selected.start!==this._range.start||selected.end!==this._range.end){
        this._reloadQueued=true;return;
      }
      this._data=data;this._error="";this._lastLoad=Date.now();
    }catch(error){this._error=error?.message||String(error);}
    finally{
      this._loading=false;
      if(this.isConnected)this._render();
      if(this._reloadQueued){this._reloadQueued=false;this._load();}
    }
  }
  async _loadModeHistory(){
    if(!this.isConnected||!this._hass?.callWS)return;
    const start=Date.parse(this._range.start);
    const end=Math.min(Date.parse(this._range.end),Date.now());
    const key=this._range.start+"|"+this._range.end;
    const request=++this._modeRequest;
    if(this._modeHistoryKey!==key)this._modeHistory=[];
    this._modeHistoryKey=key;
    this._modeHistoryLoading=true;
    this._modeHistoryError="";
    if(!this._hass.states?.["sensor.home_presence"]||
       !Number.isFinite(start)||!Number.isFinite(end)||end<=start){
      this._modeHistory=[];
      this._modeHistoryLoading=false;
      this._render();
      return;
    }
    try{
      const result=await this._hass.callWS({
        type:"history/history_during_period",
        start_time:new Date(start).toISOString(),
        end_time:new Date(end).toISOString(),
        entity_ids:["sensor.home_presence"],
        include_start_time_state:true,
        significant_changes_only:true,
        minimal_response:true,
        no_attributes:true
      });
      if(request!==this._modeRequest||!this.isConnected||key!==this._modeHistoryKey)return;
      const rows=result?.["sensor.home_presence"];
      this._modeHistory=Array.isArray(rows)?rows:[];
    }catch(error){
      if(request!==this._modeRequest||!this.isConnected)return;
      this._modeHistory=[];
      this._modeHistoryError="Recorder mode history unavailable: "+
        (error?.message||String(error));
    }finally{
      if(request===this._modeRequest&&this.isConnected){
        this._modeHistoryLoading=false;
        this._render();
      }
    }
  }
  _mobileMenuButton(){
    // HA custom sidebar panels must request navigation on mobile explicitly.
    const button=E("button",null,"ha-mobile-menu");
    button.type="button";button.title="Open Home Assistant menu";
    button.setAttribute("aria-label","Open Home Assistant menu");
    const icon=E("ha-icon");
    icon.setAttribute("icon","mdi:menu");
    icon.setAttribute("aria-hidden","true");
    button.append(icon);
    button.addEventListener("click",()=>this.dispatchEvent(
      new Event("hass-toggle-menu",{bubbles:true,composed:true})
    ));
    return button;
  }
  _btn(title,active,click,cls="btn"){
    const b=E("button",title,cls);
    b.type="button";
    b.setAttribute(cls==="tab"?"aria-selected":"aria-pressed",active?"true":"false");
    b.onclick=click;return b;
  }
  _card(title,span=12){
    const div=E("section",null,"card span"+span);
    if(title)div.append(E("h2",title));
    return div;
  }
  _badge(value){
    return E("span",String(value??"unknown"),"badge "+statusClass(value));
  }
  _stat(title,value,detail,presenceMode=null){
    const card=this._card(null,4);
    card.append(E("div",title,"muted"));
    const stat=E("div",value,"stat");
    if(presenceMode!==null)stat.style.color=MODE_COLORS[modeState(presenceMode)];
    card.append(stat);
    if(detail)card.append(E("div",detail,"muted small"));
    return card;
  }
  _modeChart(){
    const card=this._card("Home Presence · mode over time",12);
    const start=Date.parse(this._range.start);
    const end=Math.min(Date.parse(this._range.end),Date.now());
    if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start){
      card.append(E("div","No past dates in the selected period.","empty"));
      return card;
    }
    if(!this._hass?.states?.["sensor.home_presence"]){
      card.append(E("div","sensor.home_presence is not available.","empty"));
      return card;
    }
    const key=this._range.start+"|"+this._range.end;
    const rows=this._modeHistoryKey===key?this._modeHistory:[];
    const changes=[];
    for(const item of rows.map(row=>({
      at:modeEpoch(row),state:modeState(row.s??row.state)
    })).filter(item=>Number.isFinite(item.at)&&item.at<=end)
      .sort((a,b)=>a.at-b.at)){
      if(!changes.length||changes[changes.length-1].state!==item.state)
        changes.push(item);
    }
    const segments=[];
    for(let i=0;i<changes.length;i++){
      const from=Math.max(start,changes[i].at);
      const to=Math.min(end,changes[i+1]?.at??end);
      if(to>from)segments.push({start:from,end:to,state:changes[i].state});
    }
    const track=E("div",null,"mode-track");
    track.setAttribute("role","img");
    track.setAttribute("aria-label","Household Home, Away and Unknown modes over the selected period");
    if(!segments.length){
      track.append(E("span",this._modeHistoryLoading?"Loading mode history…":
        "No recorded states in this period","mode-empty"));
    }
    for(const segment of segments){
      const piece=E("div",null,"mode-segment");
      const fraction=(segment.end-segment.start)/(end-start);
      piece.style.left=((segment.start-start)/(end-start)*100)+"%";
      piece.style.width=(fraction*100)+"%";
      piece.style.background=MODE_COLORS[segment.state];
      piece.title=modeLabel(segment.state)+" · "+
        new Date(segment.start).toLocaleString()+" – "+
        new Date(segment.end).toLocaleString();
      if(fraction>0.13)piece.append(E("span",modeLabel(segment.state)));
      track.append(piece);
    }
    card.append(track);
    const axis=E("div",null,"chartlabels");
    axis.append(E("span",new Date(start).toLocaleString()),
      E("span",new Date(end).toLocaleString()));
    card.append(axis);
    const legend=E("div",null,"mode-legend");
    for(const [name,label] of [["home","Home"],["away","Away"],
      ["unknown","Unknown / Unavailable"]]){
      const item=E("span",null,"mode-legend-item");
      const swatch=E("i",null,"mode-swatch");
      swatch.style.background=MODE_COLORS[name];
      item.append(swatch,E("span",label));
      legend.append(item);
    }
    card.append(legend);
    if(this._modeHistoryLoading&&segments.length)
      card.append(E("p","Refreshing Recorder mode history…","muted small"));
    if(this._modeHistoryError)card.append(E("p",this._modeHistoryError,"error"));
    card.append(E("p",
      "Based on Home Assistant Recorder, as in the Tado dashboard. Gaps mean no recorded state; "+
      "history before the sensor existed is not invented. This timeline is read-only.",
      "muted small"));
    return card;
  }
  _chart(events,matcher){
    const rangeStart=new Date(this._range.start),rangeEnd=new Date(this._range.end);
    const startUTC=Date.UTC(rangeStart.getFullYear(),rangeStart.getMonth(),rangeStart.getDate());
    const endUTC=Date.UTC(rangeEnd.getFullYear(),rangeEnd.getMonth(),rangeEnd.getDate());
    const days=Math.max(1,Math.round((endUTC-startUTC)/86400000));
    const unit=days===1?"hour":days<=90?"day":days<=365?"week":"month";
    const card=this._card("Recorded "+(unit==="hour"?"hourly":unit==="day"?"daily":unit==="week"?"weekly":"monthly")+" activity",12);
    const counts=[];
    let cursor=new Date(rangeStart);
    while(cursor<rangeEnd&&counts.length<150){
      const next=new Date(cursor);
      if(unit==="hour")next.setTime(next.getTime()+3600000);
      else if(unit==="day")next.setDate(next.getDate()+1);
      else if(unit==="week")next.setDate(next.getDate()+7);
      else next.setMonth(next.getMonth()+1);
      if(next>rangeEnd)next.setTime(rangeEnd.getTime());
      if(next<=cursor)break;
      counts.push({start:new Date(cursor),end:next,n:0,offline:0});
      cursor=new Date(next);
    }
    for(const evt of events){
      const at=new Date(evt.at);
      if(isNaN(at)||!matcher(evt))continue;
      const bin=counts.find(x=>at>=x.start&&at<x.end);
      if(bin){
        bin.n++;
        if(evt.kind==="availability_event"&&evt.event==="OFFLINE")bin.offline++;
      }
    }
    const max=Math.max(1,...counts.map(x=>x.n));
    const container=E("div",null,"timeline");
    container.setAttribute("role","img");
    container.setAttribute("aria-label","Recorded events by "+unit+" over selected period");
    for(const item of counts){
      const col=E("div",null,"barcol");
      const bar=E("div",null,"bar"+(item.offline?" alt":""));
      bar.style.height=(item.n?Math.max(3,Math.round(item.n/max*94)):0)+"px";
      bar.title=item.start.toLocaleString()+": "+item.n+" events"+
        (item.offline?" ("+item.offline+" confirmed offline)":"");
      col.append(bar);container.append(col);
    }
    card.append(container);
    const labels=E("div",null,"chartlabels");
    const format=unit==="hour"?d=>d.toLocaleString():d=>d.toLocaleDateString();
    labels.append(E("span",format(rangeStart)),E("span",format(rangeEnd)));
    card.append(labels);
    card.append(E("div",
      "Event counts, not device connection duration. Records are retained for up to 90 days; earlier calendar periods may be empty.",
      "muted small"));
    return card;
  }
  _events(list,label){
    const card=this._card(label,12);
    const inp=E("input",null,"search");inp.type="search";
    inp.placeholder="Filter by entity ID, device, MAC, IP, status or reason";
    inp.value=this._search;
    inp.onchange=()=>{this._search=inp.value.toLowerCase().trim();this._render();};
    card.append(inp);
    const matches=list.filter(x=>!this._search ||
      JSON.stringify(x).toLowerCase().includes(this._search));
    card.append(E("div",matches.length+" events shown · select an event for full diagnostic details",
      "muted small"));
    if(!matches.length)card.append(E("div","No matching events in the selected period.","empty"));
    for(const event of matches.slice(0,750)){
      const details=E("details",null,"event");
      const summary=E("summary");
      const left=E("span",null,"eventtitle");
      const badge=["availability_event","availability_digest","stale_measurement","stale_digest"].includes(event.kind)?event.event:
        event.kind==="presence_state"?"STATE":isSourceDetails(event)?"DETAILS":"SOURCE";
      left.append(this._badge(badge));
      left.append(E("span",eventTitle(event),"eventname"));
      summary.append(left,E("time",fmt(event.at),"time"));
      details.append(summary);
      const display={...event};
      if(!display.mac)delete display.mac;if(!display.ip)delete display.ip;
      if(!display.ssid)delete display.ssid;
      details.append(E("pre",JSON.stringify(display,null,2)));
      card.append(details);
    }
    if(matches.length>750)
      card.append(E("div","Showing the latest 750 matching events. Narrow the date range or search for specific IDs.","muted small"));
    return card;
  }
  _sourceEvidence(id, state, lastHome, {isPerson=false, tracker=null}={}){
    const current=state?.state||"unknown";
    const isHome=isPerson?current==="home":
      (id.startsWith("binary_sensor.")||id.startsWith("input_boolean.")
        ? current==="on":current==="home");
    const reported=tracker||state;
    const lastUpdate=reported?.last_reported||reported?.last_updated||
      reported?.last_changed||null;
    // The persistent Home cache is populated after installing this version.
    // If already Home, the current HA timestamp is a truthful fallback.
    const lastPositive=lastHome||(isHome?
      (state?.last_reported||state?.last_updated||state?.last_changed):null);
    const card=E("div",null,"evidence-item");
    const heading=E("div",null,"evidence-heading");
    const names=E("div");
    names.append(E("div",state?.attributes?.friendly_name||id,"evidence-name"));
    names.append(E("div",id,"evidence-sub"));
    if(isPerson&&state?.attributes?.source)
      names.append(E("div","GPS source: "+state.attributes.source,"evidence-sub"));
    const net=state?.attributes||{};
    if(!isPerson&&(net.ip||net.mac||net.essid||net.ssid))
      names.append(E("div",
        [net.ip&&"IP "+net.ip,net.mac&&"MAC "+net.mac,
          (net.essid||net.ssid)&&"SSID "+(net.essid||net.ssid)]
          .filter(Boolean).join(" · "),"evidence-sub"));
    heading.append(names,this._badge(current));
    card.append(heading);
    const dates=E("div",null,"evidence-dates");
    for(const [title,value] of [
      [tracker?"Last GPS tracker update":"Last update",lastUpdate],
      ["Last seen Home",lastPositive]
    ]){
      const cell=E("div");
      cell.append(E("small",title));
      const valueEl=E("time",fmt(value));
      if(value)valueEl.dateTime=value;
      cell.append(valueEl);
      dates.append(cell);
    }
    card.append(dates);
    return card;
  }

  _presence(grid,data){
    const current=this._hass?.states?.["sensor.home_presence"];
    const status=current?.state||data.presence||"unknown";
    const records=(data.events||[]).filter(x=>x.kind?.startsWith("presence_"));
    const people=current?.attributes?.tracked_people||[];
    const evidence=current?.attributes?.active_home_evidence||[];
    const currentMode=modeState(status);
    grid.append(this._stat("Household presence",modeLabel(currentMode),
      "home / away / unknown",currentMode));
    grid.append(this._stat("Tracked people",people.length,"Person location entities"));
    grid.append(this._stat("Positive Home sources",evidence.length,"Trusted labeled signals currently confirming Home"));
    grid.append(this._modeChart());
    const sources=this._card("Current evidence",12);
    const homeTimes=data.source_last_home||{};
    sources.append(E("h3","People / Companion App GPS"));
    if(!people.length)sources.append(E("div","No Person entities configured; Away is intentionally blocked.","muted"));
    const peopleBox=E("div",null,"evidence-list");
    for(const id of people){
      const p=this._hass?.states?.[id];
      const trackerId=p?.attributes?.source;
      const tracker=trackerId?this._hass?.states?.[trackerId]:null;
      peopleBox.append(this._sourceEvidence(id,p,homeTimes[id],
        {isPerson:true,tracker}));
    }
    sources.append(peopleBox);
    sources.append(E("h3","Trusted Home sources · Wi-Fi and manual overrides"));
    const labeled=current?.attributes?.labeled_home_sources||[];
    if(!labeled.length)sources.append(E("div",
      "No Home Presence-labeled sources configured. Add each trusted Wi-Fi phone tracker as an entity-level label.",
      "muted small"));
    const wifi=E("div",null,"evidence-list");
    for(const id of labeled){
      const s=this._hass?.states?.[id];
      wifi.append(this._sourceEvidence(id,s,homeTimes[id]));
    }
    sources.append(wifi);
    sources.append(E("div",
      "Last update is the latest timestamp Home Assistant reports for the tracker (not a guarantee of fresh GPS or Wi-Fi). Last seen Home is the most recent positive Home observation retained by this integration, including after departure and Home Assistant restarts. A dash means no known observation yet. No GPS coordinates are copied into this diagnostic cache.",
      "muted small"));
    grid.append(sources);
    grid.append(this._events(records.slice().reverse(),"Home Presence · state changes and source diagnostics"));
  }
  _devices(grid,data){
    const active=data.active||[],pending=data.pending||[];
    const records=(data.events||[]).filter(x=>x.kind?.startsWith("availability_"));
    const offline=records.filter(x=>x.event==="OFFLINE").length;
    grid.append(this._stat("Currently offline",active.length,"Confirmed outages"));
    grid.append(this._stat("Pending confirmation",pending.length,"Within the offline grace period"));
    grid.append(this._stat("Offline events",offline,"In the selected time range"));
    const current=this._card("Current outages & pending devices",12);
    if(!active.length&&!pending.length)current.append(E("div","No open outages or pending disconnections.","empty"));
    for(const [status,items] of [["OFFLINE",active],["PENDING",pending]]){
      for(const item of items){
        const d=E("details",null,"event"),s=E("summary"),left=E("span",null,"eventtitle");
        left.append(this._badge(status),E("span",item.name||item.entity_id,"eventname"));
        if(item.integration&&item.integration!=="unknown"){
          left.append(E("span","via "+item.integration,"muted small"));
        }
        s.append(left,E("span","Since "+fmt(item.since),"time"));
        d.append(s,E("pre",JSON.stringify(item,null,2)));current.append(d);
      }
    }
    grid.append(current);
    grid.append(this._chart(records,e=>e.kind==="availability_event"));
    grid.append(this._events(records.slice().reverse(),"Device Availability · confirmed offline/recovered history"));
  }
  _stale(grid,data){
    const monitor=data.stale||{};
    const counts=monitor.counts||{};
    if(!monitor.enabled){
      grid.append(this._card("Stale sensor monitoring is disabled in integration Options.",12));
      return;
    }
    grid.append(this._stat("Stale measurements",counts.stale||0,"Missing reports, invalid readings or PM2.5 stuck low for 24 hours"));
    grid.append(this._stat("Suspect measurements",counts.suspect||0,"Opt-in frozen-value heuristic; PM2.5 stuck-low readings are now STALE"));
    grid.append(this._stat("Sensors monitored",counts.monitored||0,
      (counts.healthy||0)+" healthy · "+(counts.pending||0)+" pending"));
    const info=this._card("Monitoring status",12);
    info.append(E("div",
      "Last scan: "+fmt(monitor.checked_at)+" · Scan interval: 15 minutes · "+
      "Next regular digests: 08:00 and 20:00 (Home Assistant local time) · "+
      "Queued changes: "+(monitor.queued_events||0)+
      " · Last accepted by notify: "+fmt(monitor.last_digest),"small"));
    info.append(E("div",
      "Email target: "+(monitor.notification_target||"not configured")+
      " · Last attempt: "+fmt(monitor.last_attempt)+
      " · Result: "+(monitor.last_attempt_success==null?"not attempted":
        monitor.last_attempt_success?"accepted by notify":"FAILED")+
      " · Daily unresolved reminder: "+(monitor.daily_reminder_enabled?"enabled":"disabled"),
      "small"));
    if(monitor.last_error)info.append(E("div","Last delivery error: "+monitor.last_error,"muted small"));
    info.append(E("p",
      "Missing reports use last_reported (not last_changed). Some integrations publish only "+
      "when a value changes, so these are missing HA reports, not proof the hardware is faulty. "+
      "A repeated identical value with a fresh report is healthy unless you explicitly enable "+
      "frozen-value suspicion on that entity. Unknown/unavailable sensors are flagged after a grace period. "+
      "Acceptance by the Home Assistant notify service does not guarantee mailbox delivery.",
      "muted small"));
    info.append(E("p",
      "Configure entity-level labels: stale_monitor_include, stale_monitor_ignore, "+
      "stale_monitor_fast (3h), stale_monitor_slow (168h), "+
      "stale_monitor_watch_value (unchanged-value heuristic). PM2.5 stuck-low detection uses "+
      "24h of the sensor's own readings, allows occasional 2–5 µg/m³ fluctuations, and requires "+
      "45 minutes continuously above 5 µg/m³ for recovery. Defaults: air 12h, ambient 48h, "+
      "electrical 72h, other 168h. Digests at 08:00 and 20:00; optional daily unresolved reminder.",
      "muted small"));
    grid.append(info);
    const card=this._card("Current measurements",12);
    const controls=E("div",null,"toolbar");
    controls.append(this._btn("Flagged and pending",!this._staleShowAll,()=>{
      this._staleShowAll=false;this._render();
    }));
    controls.append(this._btn("All monitored",this._staleShowAll,()=>{
      this._staleShowAll=true;this._render();
    }));
    card.append(controls);
    const input=E("input",null,"search");input.type="search";
    input.placeholder="Filter by room, entity ID, device, status or integration";
    input.value=this._search;
    input.onchange=()=>{this._search=input.value.toLowerCase().trim();this._render();};
    card.append(input);
    const rows=(monitor.rows||[]).filter(row=>
      (this._staleShowAll||row.status!=="healthy") &&
      (!this._search||JSON.stringify(row).toLowerCase().includes(this._search)));
    card.append(E("div",rows.length+" measurements displayed", "muted small"));
    if(!rows.length)card.append(E("div",
      (counts.monitored||0)===0?"No eligible numeric device-backed measurements found. "+
      "Use stale_monitor_include on an entity to opt it in.":
      "No matching flagged or pending measurements. Choose All monitored to audit coverage.",
      "empty"));
    for(const row of rows.slice(0,500)){
      const details=E("details",null,"event");
      const summary=E("summary");
      const left=E("span",null,"eventtitle");
      left.append(this._badge(row.status),E("span",row.name||row.entity_id,"eventname"));
      left.append(E("span",(row.value||"—")+(row.unit?" "+row.unit:""),"small"));
      summary.append(left,E("span",
        row.age_hours+"h / "+row.threshold_hours+"h","time"));
      details.append(summary,E("div",row.entity_id+" · "+row.reason+
        " · "+row.area+" · "+row.integration,"muted small"),
        E("div","Last HA report: "+(row.report_age_hours??row.age_hours)+"h ago · "+
          "Value unchanged: "+(row.unchanged_hours??"—")+"h"+
          (row.low_variation_hours==null?"":" · PM2.5 observed window: "+row.low_variation_hours+"h"),
          "muted small"),
        E("pre",JSON.stringify(row,null,2)));
      card.append(details);
    }
    if(rows.length>500)card.append(E("div",
      "Showing 500 of "+rows.length+" matching readings. Narrow the search.","muted small"));
    grid.append(card);
    const records=(data.events||[]).filter(e=>e.kind==="stale_measurement"||e.kind==="stale_digest");
    grid.append(this._chart(records,e=>e.kind==="stale_measurement"));
    grid.append(this._events(records.slice().reverse(),"Stale sensors · transitions and digest delivery"));
  }
  _render(){
    if(!this.isConnected)return;
    const root=this.shadowRoot;
    root.replaceChildren(E("style",css));
    const shell=E("div",null,"shell");
    const heading=E("div",null,"heading");
    const header=E("div");
    header.append(E("h1","Availability & Home Presence"));
    header.append(E("p","Device connectivity, household presence, stale measurements and diagnostic history","subtitle"));
    const headingGroup=E("div",null,"heading-group");
    headingGroup.append(this._mobileMenuButton(),header);
    heading.append(headingGroup);
    const refresh=this._btn(this._loading?"Refreshing…":"Refresh",false,()=>this._load());
    refresh.disabled=this._loading;heading.append(refresh);shell.append(heading);
    const toolbar=E("div",null,"toolbar");
    if(this._pickerReady){
      const picker=E(pickerTag);
      picker.range=this._range;
      picker.hass=this._hass;
      this._picker=picker;
      picker.addEventListener("date-range-changed",event=>{
        this._range=event.detail;
        this._search="";
        this._load();
      });
      toolbar.append(picker);
    }else{
      toolbar.append(E("span",this._pickerError?
        "Date selector could not load: "+this._pickerError:
        "Loading shared date selector…","muted small"));
      if(this._pickerError)toolbar.append(this._btn("Retry calendar",false,()=>{
        this._pickerError="";this._ensurePicker();
      }));
    }
    if(this._lastLoad)toolbar.append(E("span","Updated "+new Date(this._lastLoad).toLocaleTimeString(),"muted small"));
    shell.append(toolbar);
    const tabs=E("div",null,"tabs");
    tabs.setAttribute("role","tablist");
    tabs.append(this._btn("Home Presence",this._tab==="presence",()=>{
      this._tab="presence";this._search="";this._render();
      this._loadModeHistory();
    },"tab"));
    tabs.append(this._btn("Device availability",this._tab==="devices",()=>{
      this._tab="devices";this._search="";this._render();
    },"tab"));
    tabs.append(this._btn("Stale sensors",this._tab==="stale",()=>{
      this._tab="stale";this._search="";this._render();
    },"tab"));
    shell.append(tabs);
    if(this._error)shell.append(E("p",this._error,"error"));
    if(!this._data)shell.append(E("div",this._loading?"Loading diagnostic history…":"No diagnostics available yet.","empty"));
    else{
      const grid=E("main",null,"grid");
      if(this._tab==="presence")this._presence(grid,this._data);
      else if(this._tab==="stale")this._stale(grid,this._data);
      else this._devices(grid,this._data);
      shell.append(grid);
    }
    shell.append(E("p",
      "Read-only dashboard · 90-day retention (maximum 5,000 events) · Administrator access · History begins with this integration version. Diagnostic events persist across Home Assistant restarts; this view does not change device settings or send messages.",
      "foot"));
    root.append(shell);
  }
}
if(!customElements.get(tag))
  customElements.define(tag,AvailabilityDiagnosticsManagedPanel);
