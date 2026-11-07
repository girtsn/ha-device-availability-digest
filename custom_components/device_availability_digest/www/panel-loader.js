/* Stable managed-panel loader, following the Tado X / Tylö sidebar pattern.
 * Cache-busted versioned modules update with HACS, without manual resources.
 */
class AvailabilityDiagnosticsLoaderPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._hass=null;this._panel=null;this._route=null;this._narrow=false;
    this._active=null;this._version=null;this._checking=false;
    this._timer=null;this._retry=0;
    this._focus=()=>this._check();
    this._visibility=()=>{if(!document.hidden)this._check();};
    const style=document.createElement("style");
    style.textContent=":host{display:block;color:var(--primary-text-color)}.status{padding:12px 18px;color:var(--secondary-text-color);font-size:13px}.status:empty{display:none}";
    this._status=document.createElement("div");this._status.className="status";
    this._mount=document.createElement("div");
    this.shadowRoot.append(style,this._status,this._mount);
  }
  set hass(v){this._hass=v;if(this._active)this._active.hass=v;}
  set panel(v){this._panel=v;if(this._active)this._active.panel=v;}
  set narrow(v){this._narrow=!!v;if(this._active)this._active.narrow=this._narrow;}
  set route(v){this._route=v;if(this._active)this._active.route=v;}
  connectedCallback(){
    if(this._timer!==null)return;
    this._check();
    this._timer=window.setInterval(()=>this._check(),60000);
    window.addEventListener("focus",this._focus);
    document.addEventListener("visibilitychange",this._visibility);
  }
  disconnectedCallback(){
    if(this._timer!==null){clearInterval(this._timer);this._timer=null;}
    window.removeEventListener("focus",this._focus);
    document.removeEventListener("visibilitychange",this._visibility);
  }
  async _check(){
    if(this._checking||!this.isConnected)return;
    this._checking=true;
    try{
      const response=await fetch("/device_availability_digest/manifest.json?_="+Date.now(),
        {cache:"no-store",credentials:"same-origin"});
      if(!response.ok)throw Error("Manifest HTTP "+response.status);
      const manifest=await response.json(),version=manifest?.version;
      if(typeof version!=="string"||!/^[0-9]+\.[0-9]+\.[0-9]+$/.test(version))
        throw Error("Invalid integration version");
      if(version===this._version){this._status.textContent="";return;}
      const tag="availability-diagnostics-managed-panel-v"+version.replace(/\./g,"-");
      if(!customElements.get(tag)){
        await import("/device_availability_digest/assets/"+version+
          "/managed-panel.js?v="+version+"&retry="+(this._retry++));
      }
      if(!customElements.get(tag))throw Error("Dashboard module not registered");
      const next=document.createElement(tag);
      next.hass=this._hass;next.panel=this._panel;
      next.route=this._route;next.narrow=this._narrow;
      this._mount.replaceChildren(next);
      this._active=next;this._version=version;this._status.textContent="";
    }catch(error){
      this._status.textContent=(this._active?
        "New dashboard version is temporarily unavailable; continuing with the current version. ":
        "Unable to load Availability dashboard. ")+(error?.message||String(error));
    }finally{this._checking=false;}
  }
}
if(!customElements.get("availability-diagnostics-loader-panel"))
  customElements.define("availability-diagnostics-loader-panel",AvailabilityDiagnosticsLoaderPanel);
