/* Shared Energy-style calendar picker. Honor HA user-profile time zone:
 * "local" = this viewing device; "server" = HA configured location.
 * UTC-midnight surrogate civil dates preserve correct 23/25h DST boundaries.
 */
const avZone=hass=>{
  const server=hass?.config?.time_zone||"UTC";
  if(hass?.locale?.time_zone!=="local")return server;
  return Intl.DateTimeFormat().resolvedOptions().timeZone||server;
};
const avCivil=(instant,zone)=>{
  const values=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{
    timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"
  }).formatToParts(instant).filter(p=>p.type!=="literal").map(p=>[p.type,+p.value]));
  return new Date(Date.UTC(values.year,values.month-1,values.day));
};
const avToday=(hass,base=new Date())=>avCivil(base,avZone(hass));
const avAddDays=(date,n)=>new Date(date.getTime()+n*86400000);
const avDaySpan=(a,b)=>Math.round((b.getTime()-a.getTime())/86400000);
const avFromUtc=(iso,hass)=>avCivil(new Date(iso),avZone(hass));
const avToUtc=(civil,hass)=>{
  const target=civil.getTime();
  const formatter=new Intl.DateTimeFormat("en-GB",{
    timeZone:avZone(hass),year:"numeric",month:"2-digit",day:"2-digit",
    hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"
  });
  let guess=target;
  for(let i=0;i<4;i++){
    const parts=Object.fromEntries(formatter.formatToParts(new Date(guess))
      .filter(p=>p.type!=="literal").map(p=>[p.type,+p.value]));
    const shown=Date.UTC(parts.year,parts.month-1,parts.day,
      parts.hour,parts.minute,parts.second);
    const correction=target-shown;
    guess+=correction;
    if(correction===0)break;
  }
  return new Date(guess).toISOString();
};
const avDateText=(date,hass)=>new Intl.DateTimeFormat(
  hass?.locale?.language||hass?.language||undefined,
  {timeZone:"UTC",month:"short",day:"numeric",year:"numeric"}
).format(date);
const avFirstWeekday=hass=>{
  const first=["sunday","monday","tuesday","wednesday","thursday","friday","saturday"]
    .indexOf(hass?.locale?.first_weekday);
  if(first>=0)return first;
  const language=hass?.locale?.language||hass?.language||
    (typeof navigator!=="undefined"?navigator.language:"en-GB");
  try{
    const locale=new Intl.Locale(language);
    return (locale.weekInfo?.firstDay??locale.getWeekInfo?.().firstDay??1)%7;
  }catch(_){return 1;}
};
const avPresetRange=(preset,base=new Date(),hass=null)=>{
  const now=avToday(hass,base),tomorrow=avAddDays(now,1);
  let start,end=tomorrow;
  const offset=(now.getUTCDay()-avFirstWeekday(hass)+7)%7;
  switch(preset){
    case "last24":return {start:new Date(base.getTime()-86400000).toISOString(),
      end:base.toISOString(),preset};
    case "today":start=now;break;
    case "yesterday":start=avAddDays(now,-1);end=now;break;
    case "week":start=avAddDays(now,-offset);break;
    case "month":start=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1));break;
    case "quarter":start=new Date(Date.UTC(now.getUTCFullYear(),Math.floor(now.getUTCMonth()/3)*3,1));break;
    case "year":start=new Date(Date.UTC(now.getUTCFullYear(),0,1));break;
    case "last7":start=avAddDays(now,-6);break;
    case "last30":start=avAddDays(now,-29);break;
    case "last365":start=avAddDays(now,-364);break;
    case "last12months":start=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth()-11,1));break;
    case "last3years":start=avAddDays(new Date(Date.UTC(now.getUTCFullYear()-3,now.getUTCMonth(),now.getUTCDate())),1);break;
    default:start=avAddDays(now,-6);preset="last7";
  }
  return {start:avToUtc(start,hass),end:avToUtc(end,hass),preset};
};

class AvailabilityDateRangePicker extends HTMLElement {
  constructor(){
    super();this.attachShadow({mode:"open"});
    this._hass=null;this._range=avPresetRange("week");this._open=false;
    this._month=avToday(null);this._draftStart=null;this._draftEnd=null;this._draftClicks=0;
  }
  set hass(value){
    const previous=this._hass;
    this._hass=value;
    const zoneChanged=previous&&avZone(previous)!==avZone(value);
    if(zoneChanged&&this._range?.preset!=="last24"){
      // Preserve the chosen *calendar dates* when a user switches between
      // local/server time. Recompute the UTC instants for the new zone.
      const start=avCivil(new Date(this._range.start),avZone(previous));
      const end=avCivil(new Date(this._range.end),avZone(previous));
      this._range={...this._range,
        start:avToUtc(start,value),end:avToUtc(end,value)};
      this._month=avToday(value);
      this.dispatchEvent(new CustomEvent("date-range-changed",{
        detail:this._range,bubbles:true,composed:true
      }));
    }else if((!previous||avFirstWeekday(previous)!==avFirstWeekday(value))
      &&this._range?.preset==="week"){
      this._range=avPresetRange("week",new Date(),value);
      this._month=avToday(value);
      this.dispatchEvent(new CustomEvent("date-range-changed",{
        detail:this._range,bubbles:true,composed:true
      }));
    }
    this._render();
  }
  set range(value){if(value){this._range=value;this._render();}}
  get range(){return this._range;}
  connectedCallback(){this._render();}
  _el(tag,text,cls){
    const e=document.createElement(tag);
    if(text!=null)e.textContent=text;
    if(cls)e.className=cls;
    return e;
  }
  _btn(label,handler,cls,disabled=false){
    const e=this._el("button",label,cls);e.type="button";e.disabled=disabled;
    e.addEventListener("click",handler);return e;
  }
  _limits(start,end){
    return start<end&&end<=avAddDays(avToday(this._hass),1)&&avDaySpan(start,end)<=1099;
  }
  _publish(range){
    this._range=range;this._open=false;
    this._draftStart=null;this._draftEnd=null;this._draftClicks=0;
    this._render();
    this.dispatchEvent(new CustomEvent("date-range-changed",{
      detail:range,bubbles:true,composed:true
    }));
  }
  _apply(start,end,preset="custom"){
    if(!this._limits(start,end))return;
    this._publish({start:avToUtc(start,this._hass),end:avToUtc(end,this._hass),preset});
  }
  _usePreset(preset){this._publish(avPresetRange(preset,new Date(),this._hass));}
  _shift(direction){
    const preset=this._range.preset;
    if(preset==="last24"){
      const delta=direction*86400000;
      const start=new Date(new Date(this._range.start).getTime()+delta);
      const end=new Date(new Date(this._range.end).getTime()+delta);
      if(end<=new Date())this._publish({start:start.toISOString(),end:end.toISOString(),preset});
      return;
    }
    const start=avFromUtc(this._range.start,this._hass);
    const end=avFromUtc(this._range.end,this._hass);
    let nextStart,nextEnd;
    const months=({month:1,quarter:3,year:12})[preset];
    if(months){
      nextStart=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+months*direction,1));
      nextEnd=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+months*(direction+1),1));
      const tomorrow=avAddDays(avToday(this._hass),1);
      if(nextEnd>tomorrow)nextEnd=tomorrow;
    }else if(preset==="last12months"||preset==="last3years"){
      const monthsBack=preset==="last3years"?36:12;
      nextStart=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+monthsBack*direction,start.getUTCDate()));
      nextEnd=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+monthsBack*(direction+1),start.getUTCDate()));
      const tomorrow=avAddDays(avToday(this._hass),1);
      if(nextEnd>tomorrow)nextEnd=tomorrow;
    }else{
      const days=avDaySpan(start,end);
      nextStart=avAddDays(start,days*direction);
      nextEnd=avAddDays(end,days*direction);
    }
    if(this._limits(nextStart,nextEnd))this._apply(nextStart,nextEnd,preset);
  }
  _dayClick(date){
    if(!this._draftStart||this._draftClicks>=2){
      this._draftStart=date;this._draftEnd=avAddDays(date,1);this._draftClicks=1;
    }else{
      if(date<this._draftStart){
        this._draftEnd=avAddDays(this._draftStart,1);this._draftStart=date;
      }else this._draftEnd=avAddDays(date,1);
      this._draftClicks=2;
    }
    this._render();
  }
  _render(){
    if(!this.isConnected)return;
    const root=this.shadowRoot;root.replaceChildren();
    const style=this._el("style");
style.textContent=[
      ":host{display:block;color:var(--primary-text-color);font:inherit;position:relative;z-index:5}",
      "*{box-sizing:border-box}",
      ".toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}",
      "button{font:inherit;background:var(--card-background-color,var(--ha-card-background,#fff));border:1px solid var(--divider-color,#ddd);color:inherit;border-radius:8px;cursor:pointer;padding:8px 11px}",
      "button:disabled{opacity:.4;cursor:default}",
      ".label{font-weight:600;font-size:14px;display:flex;align-items:center;gap:8px}",
      ".chevron{padding:7px 12px;font-size:18px;min-width:36px}",
      ".now{color:var(--primary-color,#039bc6)}",
      ".popup{position:absolute;top:calc(100% + 8px);left:0;z-index:100;display:grid;grid-template-columns:170px minmax(265px,320px);background:var(--card-background-color,var(--ha-card-background,#fff));box-shadow:0 8px 28px #0003;border:1px solid var(--divider-color,#ddd);border-radius:16px;overflow:hidden;max-width:calc(100vw - 30px)}",
      ".presets{border-right:1px solid var(--divider-color,#ddd);max-height:420px;overflow-y:auto;padding:8px}",
      ".preset{display:block;width:100%;border:0;background:transparent;text-align:left;padding:10px 12px;border-radius:6px;font-size:13px}",
      ".preset.selected,.preset:hover{background:var(--secondary-background-color,#eee)}",
      ".right{padding:12px;min-width:0}",
      ".month-head{display:flex;align-items:center;justify-content:space-between;font-weight:600;font-size:14px;margin-bottom:12px}",
      ".calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:1px}",
      ".weekday{text-align:center;font-size:11px;color:var(--secondary-text-color,#888);padding:8px 0}",
      ".day{border:0;border-radius:6px;padding:9px 0;min-width:0;background:transparent;font-size:12px}",
      ".day.inrange{background:var(--primary-color,#039bc6);color:#fff}",
      ".day.outside{color:var(--disabled-text-color,#aaa)}",
      ".day.today{outline:1px solid var(--primary-color,#039bc6)}",
      ".footer{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}",
      ".choose{background:var(--primary-color,#039bc6);color:var(--text-primary-color,#fff)}",
      "@media(max-width:570px){.popup{grid-template-columns:minmax(0,1fr);width:min(360px,calc(100vw - 30px))}.presets{display:grid;grid-template-columns:1fr 1fr;max-height:140px;border-right:0;border-bottom:1px solid var(--divider-color,#ddd)}.preset{padding:7px 8px}}"
    ].join("\n");
    root.append(style);
    const start=avFromUtc(this._range.start,this._hass);
    const end=avFromUtc(this._range.end,this._hass);
    const bar=this._el("div",null,"toolbar");
    const label=avDateText(start,this._hass)+" – "+avDateText(avAddDays(end,-1),this._hass);
    bar.append(this._btn("▣  "+label,()=>{
      this._open=!this._open;
      if(this._open)this._month=avFromUtc(this._range.start,this._hass);
      this._render();
    },"label"));
    bar.append(this._btn("Now",()=>this._usePreset(
      this._range.preset==="custom"?"week":this._range.preset
    ),"now"));
    bar.append(this._btn("‹",()=>this._shift(-1),"chevron"));
    bar.append(this._btn("›",()=>this._shift(1),"chevron",
      this._range.preset==="last24"?new Date(this._range.end)>=new Date():
      end>=avAddDays(avToday(this._hass),1)));
    root.append(bar);
    if(!this._open)return;
    const popup=this._el("div",null,"popup");
    const presets=this._el("div",null,"presets");
    for(const [key,title] of [
      ["today","Today"],["yesterday","Yesterday"],["week","This week"],
      ["month","This month"],["quarter","This quarter"],["year","This year"],
      ["last7","Last 7 days"],["last30","Last 30 days"],
      ["last365","Last 365 days"],["last12months","Last 12 months"],
      ["last3years","Last 3 years"]
    ]){
      presets.append(this._btn(title,()=>this._usePreset(key),
        "preset"+(this._range.preset===key?" selected":"")));
    }
    popup.append(presets);
    const right=this._el("div",null,"right");
    const head=this._el("div",null,"month-head");
    head.append(this._btn("‹",()=>{
      this._month=new Date(Date.UTC(this._month.getUTCFullYear(),this._month.getUTCMonth()-1,1));
      this._render();
    },"chevron"));
    head.append(this._el("span",this._month.toLocaleDateString(undefined,{
      month:"long",year:"numeric",timeZone:"UTC"
    })));
    head.append(this._btn("›",()=>{
      this._month=new Date(Date.UTC(this._month.getUTCFullYear(),this._month.getUTCMonth()+1,1));
      this._render();
    },"chevron"));
    right.append(head);
    const hint=this._el("div","Tap one date for a day, or two dates for a range.","muted");
    hint.style.cssText="font-size:12px;color:var(--secondary-text-color,#888);margin-bottom:6px";
    right.append(hint);
    const cal=this._el("div",null,"calendar");
    const first=avFirstWeekday(this._hass);
    for(let i=0;i<7;i++){
      const d=new Date(Date.UTC(2026,10,1+((first+i)%7)));
      cal.append(this._el("span",d.toLocaleDateString(undefined,{
        weekday:"narrow",timeZone:"UTC"
      }),"weekday"));
    }
    const monthStart=new Date(Date.UTC(this._month.getUTCFullYear(),this._month.getUTCMonth(),1));
    const offset=(monthStart.getUTCDay()-first+7)%7;
    const draftStart=this._draftStart||start;
    const draftEnd=this._draftEnd||end;
    for(let i=0;i<42;i++){
      const date=avAddDays(monthStart,i-offset);
      const future=date>avToday(this._hass);
      const inRange=date>=draftStart&&date<draftEnd;
      const cls="day"+(date.getUTCMonth()!==this._month.getUTCMonth()?" outside":"")+
        (inRange?" inrange":"")+(avDaySpan(date,avToday(this._hass))===0?" today":"");
      cal.append(this._btn(String(date.getUTCDate()),()=>this._dayClick(date),cls,future));
    }
    right.append(cal);
    const footer=this._el("div",null,"footer");
    footer.append(this._btn("Cancel",()=>{
      this._open=false;this._draftStart=null;this._draftEnd=null;this._draftClicks=0;this._render();
    }));
    footer.append(this._btn("Select",()=>{
      this._apply(this._draftStart||start,this._draftEnd||end,"custom");
    },"choose"));
    right.append(footer);popup.append(right);root.append(popup);
  }
}

if(!customElements.get("availability-date-range-picker"))
  customElements.define("availability-date-range-picker",AvailabilityDateRangePicker);
const AV_PICKER_VERSION=(new URL(import.meta.url).searchParams.get("v")||"dev").replace(/\./g,"-");
const AV_VERSIONED_PICKER_TAG="availability-date-range-picker-v"+AV_PICKER_VERSION;
if(!customElements.get(AV_VERSIONED_PICKER_TAG))
  customElements.define(AV_VERSIONED_PICKER_TAG,class extends AvailabilityDateRangePicker {});

export { avPresetRange, avZone };
