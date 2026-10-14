/* Built into the existing card: reuse its translations and recovery actions.
 * Backend data, source selection, credentials and deduplication are untouched.
 */
const OSM_EXPLORER_SORTS = ['distance', 'type', 'name', 'free_first', 'availability', 'data_quality', 'source'];
const OSM_EXPLORER_KINDS = ['live', 'reported', 'estimated', 'predicted', 'static'];
const OSM_EXPLORER_TYPES = ['paid', 'open', 'street', 'underground', 'multi_storey', 'park_and_ride', 'other'];
const osmNumber = value => value === null || value === undefined || typeof value === 'boolean' || typeof value === 'object' || (typeof value === 'string' && !value.trim()) ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
const osmKind = item => OSM_EXPLORER_KINDS.includes(item.availability_kind) ? item.availability_kind : (item.has_realtime_data ? 'live' : 'static');
const osmFree = item => {
  const n = osmNumber(item.free_capacity), total = osmNumber(item.capacity);
  return ['live','reported'].includes(osmKind(item)) && n !== null && Number.isInteger(n) && n >= 0 && (total === null || n <= total) ? n : null;
};
const osmKey = item => item.osm_id != null ? `osm:${item.osm_type || ''}:${item.osm_id}` : `${item.provider || ''}:${item.provider_id || [item.name,item.latitude,item.longitude].join(':')}`;
function osmVisible(items, ui, locale='en', typeLabel=item=>item.category || '') {
  let collator;
  try { collator = new Intl.Collator(locale, {numeric:true,sensitivity:'base'}); } catch (_) { collator = new Intl.Collator('en'); }
  const text = (a,b) => collator.compare(String(a || ''),String(b || ''));
  const number = (a,b,descending=false) => a === null ? (b === null ? 0 : 1) : b === null ? -1 : (descending ? b-a : a-b);
  const query = (ui.query || '').trim().toLocaleLowerCase().normalize('NFD').replace(/\p{M}/gu,'');
  const list = items.map((item,index)=>({item,index})).filter(({item}) => {
    if (ui.types.length && !ui.types.includes(item.category)) return false;
    if (ui.cost !== 'all' && (['yes','no'].includes(item.fee) ? item.fee : 'unknown') !== ui.cost) return false;
    if (ui.quality !== 'all' && osmKind(item) !== ui.quality) return false;
    if (ui.source !== 'all' && (item.provider || 'unknown') !== ui.source) return false;
    if (ui.available && (osmKind(item) !== 'live' || !(osmFree(item) > 0) || item.opening_status === 'closed')) return false;
    if (ui.maxDistance !== null && (osmNumber(item.distance_m) === null || Number(item.distance_m) > ui.maxDistance)) return false;
    return !query || [item.name,item.address,item.provider_name,typeLabel(item)].some(v=>String(v || '').toLocaleLowerCase().normalize('NFD').replace(/\p{M}/gu,'').includes(query));
  });
  return list.sort((a,b)=>{
    const x=a.item,y=b.item;
    let comparison=0;
    switch(ui.sort) {
      case 'type': comparison=text(typeLabel(x),typeLabel(y)); break;
      case 'name': comparison=text(x.name,y.name); break;
      case 'source': comparison=text(x.provider_name || x.provider,y.provider_name || y.provider); break;
      case 'free_first': comparison=(x.fee==='no'?0:x.fee==='yes'?1:2)-(y.fee==='no'?0:y.fee==='yes'?1:2); break;
      case 'data_quality': comparison=OSM_EXPLORER_KINDS.indexOf(osmKind(x))-OSM_EXPLORER_KINDS.indexOf(osmKind(y)); break;
      case 'availability': comparison=number(osmFree(x),osmFree(y),true); break;
      default: comparison=number(osmNumber(x.distance_m),osmNumber(y.distance_m));
    }
    return comparison || number(osmNumber(x.distance_m),osmNumber(y.distance_m)) || text(x.name,y.name) || a.index-b.index;
  }).map(({item})=>item);
}
function osmCleanPrefs(value={}, defaultSort='distance') {
  return {query:typeof value.query==='string' ? value.query.slice(0,160) : '',
    types:Array.isArray(value.types) ? [...new Set(value.types.filter(t=>OSM_EXPLORER_TYPES.includes(t)))] : [],
    cost:['all','no','yes','unknown'].includes(value.cost)?value.cost:'all',
    quality:['all',...OSM_EXPLORER_KINDS].includes(value.quality)?value.quality:'all',
    source:typeof value.source==='string' ? value.source.slice(0,150) : 'all',
    available:value.available===true,
    maxDistance:osmNumber(value.maxDistance)>0 ? Math.min(10000,osmNumber(value.maxDistance)) : null,
    sort:OSM_EXPLORER_SORTS.includes(value.sort)?value.sort:defaultSort};
}

let osmResultsRegionId = 0;

class OsmParkingExplorerCard extends OsmParkingMapCardV070 {
  static getStubConfig() { return {entity:'sensor.parking_suggestions',map_height:220,theme_mode:'auto',show_list:true}; }
  setConfig(config) {
    if (!config?.entity) throw new Error('Please define an entity');
    this._dispose();
    this._originalConfig = {...config};
    // Expansion is view state, not a saved preference: every new card starts folded.
    this._resultsExpanded=false; this._contentVisible=false;
    const height=Number(config.map_height ?? config.height ?? 220);
    this._ui=osmCleanPrefs({},OSM_EXPLORER_SORTS.includes(config.sort_by)?config.sort_by:'distance');
    this._prefKey=null; this._selected=null; this._rows=new Map(); this._pins=new Map();
    this._themeChoice=['auto','light','dark'].includes(config.theme_mode)?config.theme_mode:'auto';
    this._epoch=(this._epoch || 0)+1;
    super.setConfig({...config,height:Number.isFinite(height)?Math.max(160,Math.min(700,height)):220,
      show_filters:config.show_filters!==false,remember_filters:config.remember_filters!==false});
    this._rowHeight=this.config.height;
    if (this.isConnected) this.connectedCallback();
    if (this._hass) this.hass=this._hass;
  }
  connectedCallback() {
    if (!this.config || this._observer) return;
    this._media=window.matchMedia('(prefers-color-scheme: dark)');
    this._mediaHandler=()=>this._renderView();
    this._media.addEventListener?.('change',this._mediaHandler);
    this._observer=new ResizeObserver(()=>{
      cancelAnimationFrame(this._resizeFrame);
      this._resizeFrame=requestAnimationFrame(()=>this._map?.resize());
    });
    this._observer.observe(this._els.map);
    if(this._hass) this._renderView();
  }
  disconnectedCallback() { this._dispose(); }
  _dispose() {
    this._epoch=(this._epoch || 0)+1;
    this._observer?.disconnect(); this._observer=null;
    this._media?.removeEventListener?.('change',this._mediaHandler);
    cancelAnimationFrame(this._resizeFrame); cancelAnimationFrame(this._renderFrame);
    clearTimeout(this._styleTimer);
    this._cancelResultReveal();
    this._cancelMapWait?.(); this._cancelMapWait=null;
    this._popup?.remove(); this._popup=null;
    this._clearMapPins();
    this._map?.remove(); this._map=null; this._mapPromise=null;
    this._pins?.clear(); this._zoneEvents=false; this._zoneIdlePending=false; this._fitSignature=null;
  }
  set hass(hass) {
    this._hass=hass;
    if(!this.config) return;
    this._restorePrefs();
    const state=hass?.states?.[this.config.entity];
    this._stateObj=state || null;
    const signature=JSON.stringify([state?.state,state?.attributes,hass?.language,hass?.themes?.darkMode,this._themeChoice,hass?.user?.id]);
    if(signature===this._lastSignature) return;
    this._lastSignature=signature;
    this._renderView();
  }
  _xt(key) {
    const locale=String(this._hass?.language || 'en').replace('_','-');
    return (OSM_EXPLORER_I18N[locale] || OSM_EXPLORER_I18N[locale.split('-')[0]] || {})[key] ?? OSM_EXPLORER_I18N.en[key] ?? key;
  }
  _dark() { return this._themeChoice==='auto' ? (this._hass?.themes?.darkMode ?? this._media?.matches ?? false) : this._themeChoice==='dark'; }
  _styleURL() {
    const config=this._originalConfig;
    return (this._dark()?config.map_style_dark:config.map_style_light) || config.map_style || `https://tiles.openfreemap.org/styles/${this._dark()?'dark':'liberty'}`;
  }
  _restorePrefs() {
    const key=`osm-parking-explorer:v1:${this._hass?.user?.id || 'local'}:${this.config.entity}:${this.config.preference_key || this.config.title || ''}`;
    if(key===this._prefKey) return;
    this._prefKey=key;
    this._resultsExpanded=false; this._cancelResultReveal();
    this._selected=null; this._popup?.remove();
    this._ui=osmCleanPrefs({},this._originalConfig.sort_by || 'distance');
    if(this.config.remember_filters && this.config.show_filters!==false) {
      try { this._ui=osmCleanPrefs(JSON.parse(localStorage.getItem(key)||'{}'),this._originalConfig.sort_by || 'distance'); } catch(_) { /* Private browsing can deny storage. */ }
    }
    if(!OSM_EXPLORER_SORTS.includes(this._ui.sort)) this._ui.sort='distance';
  }
  _savePrefs() { if(this.config.remember_filters && this._prefKey) { try { localStorage.setItem(this._prefKey,JSON.stringify(this._ui)); } catch(_) {} } }
  _filterChanged() { this._savePrefs(); this._renderResults(); this._syncMarkers(); }
  _update() { this._renderView(); return Promise.resolve(); }
  _n(value) { return osmNumber(value); }
  _distance(value) {
    const n=osmNumber(value); if(n===null || n<0) return '—';
    return n>=1000 ? `${(n/1000).toLocaleString(this._hass?.language || 'en',{maximumFractionDigits:1})} km` : `${Math.round(n)} m`;
  }
  _url(value) {
    if(typeof value!=='string') return '';
    try { const url=new URL(value); return ['https:','http:','geo:'].includes(url.protocol)?url.href:''; } catch(_) { return ''; }
  }
  _renderShell() {
    super._renderShell();
    this.dataset.explorer='';
    const style=document.createElement('style'); style.textContent=OSM_EXPLORER_CSS; this.append(style);
    const card=this.querySelector('ha-card'); card.classList.add('parking-explorer');
    const header=this.querySelector('.header');
    const titleBlock=header.firstElementChild; titleBlock.className='header-text';
    const emblem=document.createElement('div');emblem.className='explorer-emblem';emblem.textContent='P';emblem.setAttribute('aria-hidden','true');header.prepend(emblem);
    this.querySelector('.headright').innerHTML='<button class="icon-button refresh" type="button"><ha-icon icon="mdi:refresh"></ha-icon></button><span class="version">v1.5.0</span>';
    const frame=document.createElement('section');frame.className='map-frame';this._els.map.before(frame);frame.append(this._els.map);
    const actions=document.createElement('div');actions.className='map-actions';actions.innerHTML='<button type="button" class="icon-button fit"><ha-icon icon="mdi:fit-to-screen"></ha-icon></button><button type="button" class="icon-button theme"><ha-icon icon="mdi:theme-light-dark"></ha-icon></button><button type="button" class="icon-button expand"><ha-icon icon="mdi:arrow-expand"></ha-icon></button>';frame.append(actions);
    const note=document.createElement('div');note.className='map-note';note.hidden=true;note.setAttribute('role','status');frame.append(note);
    const tools=document.createElement('section');tools.className='explorer-tools';tools.innerHTML=`
      <div class="search-line"><label class="search-box"><ha-icon icon="mdi:magnify"></ha-icon><input class="search" type="search" maxlength="160" autocomplete="off"></label><button class="filter-toggle" type="button" aria-expanded="false"><ha-icon icon="mdi:filter-variant"></ha-icon><span></span></button></div>
      <div class="filters-panel" hidden><div class="type-chips" role="group"></div><div class="filter-fields">
        <label><span class="cost-label"></span><select class="cost"></select></label><label><span class="quality-label"></span><select class="quality"></select></label>
        <label><span class="source-label"></span><select class="source"></select></label><label><span class="range-label"></span><input class="max-distance" type="number" min="1" max="10000" step="100" inputmode="numeric"></label>
      </div><label class="available-label"><input type="checkbox" class="available"><span></span></label></div>
      <div class="result-bar"><div class="result-count" role="status" aria-live="polite"></div><label class="sort-label"><ha-icon icon="mdi:sort-variant"></ha-icon><select class="sort"></select></label></div>
      <button type="button" class="reset-filters" hidden></button>`;
    frame.after(tools);
    const empty=document.createElement('div');empty.className='filter-empty';empty.hidden=true;this._els.list.before(empty);
    const results=document.createElement('section');results.className='results-panel';
    results.id=`osm-parking-results-${++osmResultsRegionId}`;results.hidden=true;
    const toggle=document.createElement('button');toggle.type='button';toggle.className='results-toggle';
    toggle.setAttribute('aria-controls',results.id);toggle.setAttribute('aria-expanded','false');
    const caption=document.createElement('span');caption.className='results-toggle-label';
    const chevron=document.createElement('span');chevron.className='results-chevron';chevron.setAttribute('aria-hidden','true');chevron.textContent='⌄';
    toggle.append(caption,chevron);empty.before(toggle,results);results.append(empty,this._els.list);
    this._els.results=results;this._els['results-toggle']=toggle;
    toggle.addEventListener('click',()=>this._setResultsExpanded(!this._resultsExpanded));
    this._els.frame=frame;this._els.tools=tools;this._els.note=note;this._els.empty=empty;
    for(const name of ['search','cost','quality','source','sort','max-distance','available','filter-toggle','filters-panel','type-chips','result-count','reset-filters','refresh','fit','theme','expand']) this._els[name]=this.querySelector('.'+name);
    this._els.search.addEventListener('input',()=>{this._ui.query=this._els.search.value;this._filterChanged();});
    for(const key of ['cost','quality','source','sort']) this._els[key].addEventListener('change',()=>{this._ui[key]=this._els[key].value;this._filterChanged();});
    this._els['max-distance'].addEventListener('input',()=>{const n=osmNumber(this._els['max-distance'].value);this._ui.maxDistance=n>0?Math.min(10000,n):null;this._filterChanged();});
    this._els.available.addEventListener('change',()=>{this._ui.available=this._els.available.checked;this._filterChanged();});
    this._els['filter-toggle'].addEventListener('click',()=>{const panel=this._els['filters-panel'];panel.hidden=!panel.hidden;this._els['filter-toggle'].setAttribute('aria-expanded',String(!panel.hidden));});
    this._els['reset-filters'].addEventListener('click',()=>this._resetFilters());
    this._els.refresh.addEventListener('click',async()=>{
      this._els.refresh.disabled=true;
      try { await this._retryNow(); } finally { if(this._els) this._els.refresh.disabled=false; }
    });
    this._els.fit.addEventListener('click',()=>this._fitVisible());
    this._els.theme.addEventListener('click',()=>{
      this._themeChoice=this._themeChoice==='auto'?(this._dark()?'light':'dark'):this._themeChoice==='dark'?'light':'auto';this._lastSignature=null;this._renderView();
    });
    this._els.expand.addEventListener('click',()=>{
      this._expanded=!this._expanded;this._els.map.style.height=`${this._expanded?Math.max(400,this.config.height):this.config.height}px`;
      this._els.expand.setAttribute('aria-pressed',String(this._expanded));this._map?.resize();
    });
  }
  _resetFilters() { const sort=this._ui.sort;this._ui=osmCleanPrefs({sort});this._filterChanged(); }
  _cancelResultReveal() {
    cancelAnimationFrame(this._revealFrame);this._revealFrame=null;
  }
  _syncResultsDisclosure() {
    const e=this._els;if(!e?.results) return;
    const allowed=this._contentVisible && this.config.show_list!==false;
    e.results.hidden=!allowed || !this._resultsExpanded;
    e['results-toggle'].hidden=!allowed;
    e['results-toggle'].setAttribute('aria-expanded',String(allowed && this._resultsExpanded));
    e['results-toggle'].querySelector('.results-toggle-label').textContent=
      `${this._xt(this._resultsExpanded?'hide_results':'show_results')} (${this._visible?.length || 0})`;
    e.results.setAttribute('aria-label',this._t('suggestions'));
  }
  _setResultsExpanded(expanded) {
    this._resultsExpanded=expanded && this.config.show_list!==false;
    if(!this._resultsExpanded) {
      this._cancelResultReveal();
      // Avoid leaving keyboard focus inside a section we are about to hide.
      const active=this.getRootNode().activeElement;
      if(active && this._els.results.contains(active)) this._els['results-toggle'].focus({preventScroll:true});
    }
    this._syncResultsDisclosure();
  }
  _revealResult(key, keyboard=false) {
    this._cancelResultReveal();
    if(this.config.show_list===false || !this._contentVisible) return;
    this._setResultsExpanded(true);
    const epoch=this._epoch;
    // Resolve by stable facility key, not marker number: sorting may change
    // before the formerly hidden panel participates in layout.
    this._revealFrame=requestAnimationFrame(()=>{
      this._revealFrame=null;
      if(epoch!==this._epoch || !this.isConnected || !this._contentVisible || !this._resultsExpanded || this._selected!==key) return;
      const row=this._rows.get(key);
      if(!row?.isConnected || !this._visible.some(item=>osmKey(item)===key)) return;
      if(keyboard) row.querySelector('.result-focus')?.focus({preventScroll:true});
      row.scrollIntoView({block:'nearest',inline:'nearest',behavior:
        window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    });
  }
  _setContentVisible(visible) {
    if(!this._els) return;
    this._contentVisible=visible;
    if(!visible) this._cancelResultReveal();
    this._syncResultsDisclosure();
    this._els.frame.hidden=!visible;
    this._els.tools.hidden=!visible || this.config.show_filters===false;
    this._els.list.hidden=!visible || this.config.show_list===false;
    if(!visible) {this._els.empty.hidden=true;this._visible=[];this._clearMapPins();}
  }
  _renderView() {
    if(!this._els || !this._hass) return;
    this.dataset.mode=this._dark()?'dark':'light';this.dataset.forced=String(this._themeChoice!=='auto');
    this.style.colorScheme=this._dark()?'dark':'light';
    this._els.title.textContent=this.config.title || this._t('title');
    this._els.refresh.title=this._st('retryNow');this._els.refresh.setAttribute('aria-label',this._st('retryNow'));
    this._els.fit.title=this._xt('fit');this._els.fit.setAttribute('aria-label',this._xt('fit'));
    this._els.theme.title=`${this._xt('theme')}: ${this._xt(this._themeChoice)}`;this._els.theme.setAttribute('aria-label',this._els.theme.title);
    this._els.expand.title=this._xt('expand');this._els.expand.setAttribute('aria-label',this._xt('expand'));
    const state=this._stateObj;
    this._hideStatus();
    if(!state) {this._setContentVisible(false);this._showStatus({title:this._st('entityMissingTitle'),message:this._st('entityMissingBody'),details:this.config.entity,actions:[{label:this._st('settings'),handler:()=>this._openSettings()}]});return;}
    const a=state.attributes || {};
    this._els.subtitle.textContent=a.destination_name || a.destination_entity || this._t('destination');
    this._els.subtitle.title=this._els.subtitle.textContent;
    if(!('destination_entity' in a) && !('destination_latitude' in a) && !Array.isArray(a.suggestions)) {this._setContentVisible(false);this._showStatus({title:this._st('wrongEntityTitle'),message:this._st('wrongEntityBody'),details:this.config.entity});return;}
    if(this._showBackendStatus(a)) {this._setContentVisible(false);return;}
    const lat=osmNumber(a.destination_latitude),lon=osmNumber(a.destination_longitude);
    if(lat===null || lon===null || Math.abs(lat)>90 || Math.abs(lon)>180) {this._setContentVisible(false);this._showStatus({tone:'warning',title:this._st('sourceCoordsTitle'),message:this._st('sourceCoordsBody'),actions:[{label:this._st('retryNow'),handler:()=>this._retryNow()}]});return;}
    this._setContentVisible(true);
    this._renderResults(); // Results and navigation remain usable even when maps fail.
    const epoch=this._epoch;
    if(this.isConnected) void this._ensureExplorerMap().then(()=>{
      if(!this._map || epoch!==this._epoch) return;
      const latest=this._stateObj?.attributes || {};
      this._syncStyle();this._syncMarkers();this._updateZoneOverlay(latest.parking_zones || []);
      const destination=`${latest.destination_latitude},${latest.destination_longitude}`;
      if(this._fitSignature!==destination) {this._fitSignature=destination;this._fitVisible();}
    }).catch(error=>{if(epoch===this._epoch)this._mapFailure(error);});
  }
  _activeFilters() {return this._ui.types.length+(this._ui.query?1:0)+['cost','quality','source'].filter(k=>this._ui[k]!=='all').length+(this._ui.available?1:0)+(this._ui.maxDistance!==null?1:0);}
  _selectOptions(element, options, value) {
    const signature=JSON.stringify(options);
    if(element.dataset.options!==signature) {
      element.replaceChildren(...options.map(([v,text])=>{const o=document.createElement('option');o.value=v;o.textContent=text;return o;}));element.dataset.options=signature;
    }
    element.value=value;
  }
  _renderResults() {
    const a=this._stateObj?.attributes || {};
    const all=(Array.isArray(a.suggestions)?a.suggestions:[]).filter(i=>i && typeof i==='object' && i.record_type!=='zone');
    this._allResults=all;
    this._visible=osmVisible(all,this._ui,this._hass?.language,i=>this._labelType(i));
    if(this._selected && !this._visible.some(i=>osmKey(i)===this._selected)) {this._selected=null;this._popup?.remove();}
    const e=this._els;
    if(e.search.value!==this._ui.query) e.search.value=this._ui.query;
    e.search.placeholder=this._xt('search');e.search.setAttribute('aria-label',this._xt('search'));
    e['filter-toggle'].querySelector(':scope > span').textContent=this._xt('filters')+(this._activeFilters()?` (${this._activeFilters()})`:'');
    const allOption=['all',this._xt('all')];
    this._selectOptions(e.cost,[allOption,['no',this._t('free')],['yes',this._t('paid')],['unknown',this._xt('unknown')]],this._ui.cost);
    this._selectOptions(e.quality,[allOption,...OSM_EXPLORER_KINDS.map(k=>[k,this._xt(k)])],this._ui.quality);
    const sources=new Map(all.map(item=>[item.provider || 'unknown',item.provider_name || item.provider || this._xt('unknown')]));
    if(this._ui.source!=='all' && !sources.has(this._ui.source)) sources.set(this._ui.source,this._ui.source);
    this._selectOptions(e.source,[allOption,...sources],this._ui.source);
    this._selectOptions(e.sort,OSM_EXPLORER_SORTS.map(k=>[k,this._xt('sort_'+k)]),this._ui.sort);
    e.sort.setAttribute('aria-label',this._xt('sort'));
    e.tools.querySelector('.cost-label').textContent=this._t('price');e.tools.querySelector('.quality-label').textContent=this._xt('data');
    e.tools.querySelector('.source-label').textContent=this._pt('source');e.tools.querySelector('.range-label').textContent=this._xt('max_distance');
    e.tools.querySelector('.available-label span').textContent=this._xt('available_only');
    e.available.checked=this._ui.available;
    e['max-distance'].placeholder=this._xt('all');if(document.activeElement!==e['max-distance']) e['max-distance'].value=this._ui.maxDistance ?? '';
    const chips=e['type-chips'],signature=JSON.stringify([this._hass?.language,this._ui.types,all.map(i=>i.category)]);
    if(chips.dataset.signature!==signature) {
      chips.replaceChildren();
      for(const type of ['all',...OSM_EXPLORER_TYPES]) {
        const count=type==='all'?all.length:all.filter(i=>i.category===type).length;
        if(type!=='all' && !count && !this._ui.types.includes(type)) continue;
        const button=document.createElement('button');button.type='button';button.className='type-chip';button.dataset.type=type;
        button.textContent=`${type==='all'?this._xt('all'):this._translations().categories[type]} · ${count}`;
        button.setAttribute('aria-pressed',String(type==='all'?!this._ui.types.length:this._ui.types.includes(type)));
        button.addEventListener('click',()=>{this._ui.types=type==='all'?[]:this._ui.types.includes(type)?this._ui.types.filter(t=>t!==type):[...this._ui.types,type];this._filterChanged();});chips.append(button);
      }
      chips.dataset.signature=signature;
    }
    const live=this._visible.filter(i=>osmKind(i)==='live' && osmFree(i)!==null).length;
    e['result-count'].textContent=`${this._visible.length} / ${all.length} ${this._t('suggestions')}${live?` · ${live} ${this._xt('live')}`:''}`;
    e['reset-filters'].hidden=!this._activeFilters();e['reset-filters'].textContent=this._xt('reset');
    e.empty.hidden=!!this._visible.length || this.config.show_list===false;
    if(!e.empty.hidden) {
      e.empty.replaceChildren();const title=document.createElement('strong');title.textContent=all.length?this._xt('no_matches'):this._st('noResultsTitle');
      const body=document.createElement('p');body.textContent=all.length?this._xt('clear_hint'):this._st('noResultsBody');
      const button=document.createElement('button');button.type='button';button.className='filter-toggle';button.textContent=all.length?this._xt('reset'):this._st('settings');button.onclick=()=>all.length?this._resetFilters():this._openSettings();e.empty.append(title,body,button);
    }
    this._renderList(this._visible);
    this._syncResultsDisclosure();
  }
  _qualityText(item) {
    const kind=osmKind(item),free=osmFree(item);
    if(kind==='live' || kind==='reported') return `${this._xt(kind)}${free===null?'':` · ${free} ${this._pt('available')}`}`;
    if(kind==='estimated') return `${this._xt('estimated')} ${this._estimatedOccupancyText(item)}`.trim();
    if(kind==='predicted') {const pct=osmNumber(item.predicted_occupancy_percent);return this._xt('predicted')+(pct!==null && pct>=0 && pct<=100?` · ${Math.round(pct)}%`:'');}
    return this._xt('static');
  }
  _safeItem(item) {const copy={...item,name:String(item.name || '').trim() || this._t('parking')};for(const k of ['navigation_url','provider_url','osm_url','geo_uri']) copy[k]=this._url(copy[k]);return copy;}
  _renderList(items) {
    if(this.config.show_list===false) {this._els.list.hidden=true;return;}
    const keep=new Set();
    items.forEach((item,index)=>{
      const key=osmKey(item);keep.add(key);
      let row=this._rows.get(key);
      if(!row) {row=document.createElement('article');row.className='result-card';row.dataset.key=key;this._rows.set(key,row);}
      const signature=JSON.stringify([item,this._hass?.language,this.config.show_price]);
      if(row.dataset.signature!==signature) {
        const open=row.querySelector('details')?.open || false;
        const safe=this._safeItem(item),price=this._displayPrice(item),quality=this._qualityText(item),kind=osmKind(item);
        row.innerHTML=`<button type="button" class="result-focus"><span class="result-icon" aria-hidden="true">${osmTypeIconMarkup(item)}</span><span class="result-body"><span class="result-title">${this._esc(item.name || this._t('parking'))}</span><span class="result-type">${this._esc(this._labelType(item))}</span></span><span class="result-distance">${this._esc(this._distance(item.distance_m))}</span></button>
          <div class="result-meta"><span class="quality-badge ${kind}" title="${this._esc(kind==='reported'?this._qt('reported'):quality)}">${this._esc(quality)}</span>${this.config.show_price!==false?`<span class="cost-badge">${this._esc(price || this._xt('price_unknown'))}</span>`:''}</div>
          <div class="result-footer"><span class="result-source" title="${this._esc((Array.isArray(item.data_sources)?item.data_sources:[]).join(', '))}">${this._esc(item.provider_name || item.provider || 'OpenStreetMap')}${Number(item.deduplicated_source_count)>1?` · ${Number(item.deduplicated_source_count)} ${this._esc(this._qt('sources'))}`:''}</span>${safe.navigation_url?`<a class="navigate" href="${this._esc(safe.navigation_url)}" target="_blank" rel="noopener noreferrer" aria-label="${this._esc(this._t('navigate')+': '+(item.name || ''))}"><ha-icon icon="mdi:directions"></ha-icon>${this._esc(this._t('navigate'))}</a>`:''}</div>
          <details class="result-details" ${open?'open':''}><summary>${this._esc(this._xt('details'))}</summary><div>${this._popupHtml(safe,index)}</div></details>`;
        row.querySelector('.result-focus').onclick=()=>this._focusItem(key);
        row.dataset.signature=signature;
      }
      // Display order is internal metadata. Selection uses the stable key.
      row.dataset.index=String(index);row.dataset.type=osmIconType(item);
      row.querySelector('.result-focus').setAttribute('aria-pressed',String(key===this._selected));row.classList.toggle('selected',key===this._selected);
      const atIndex=this._els.list.children[index];if(atIndex!==row) this._els.list.insertBefore(row,atIndex || null);
    });
    for(const [key,row] of this._rows) if(!keep.has(key)) {row.remove();this._rows.delete(key);}
  }
  _focusItem(key, {fromMap=false, keyboard=false}={}) {
    const item=this._visible.find(i=>osmKey(i)===key);
    if(!item) return;
    this._cancelResultReveal();this._selected=key;
    this._renderList(this._visible);this._syncMarkers();
    const pin=this._pins.get(key);
    if(fromMap && this.config.show_list!==false) {
      // Marker selection reveals the list, without competing popup/camera
      // movement. List selection retains the existing map-focus action.
      this._popup?.remove();this._popup=null;
      this._revealResult(key,keyboard);return;
    }
    if(!this._map || !pin) return;
    this._map.easeTo({center:[Number(item.longitude),Number(item.latitude)],zoom:Math.max(this._map.getZoom(),16),duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:250});
    this._popup?.remove();this._popup=pin.popup;this._popup.setLngLat([Number(item.longitude),Number(item.latitude)]).addTo(this._map);
  }
  async _ensureExplorerMap() {
    if(this._map) return this._map;
    if(this._mapPromise) return this._mapPromise;
    const epoch=this._epoch;
    this._mapPromise=(async()=>{
      let timer;
      try {await Promise.race([super._ensureMapLibre(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Map library timed out')),20000);})]);} finally {clearTimeout(timer);}
      if(epoch!==this._epoch || !this.isConnected) return null;
      const a=this._stateObj?.attributes || {},lat=osmNumber(a.destination_latitude),lon=osmNumber(a.destination_longitude);
      if(lat===null || lon===null) return null;
      this._style=this._styleURL();this._fallbackStyle=false;
      const map=new maplibregl.Map({container:this._els.map,style:this._style,center:[lon,lat],zoom:14,attributionControl:true});
      this._map=map;
      map.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-right');
      map.on('style.load',()=>{if(map!==this._map) return;clearTimeout(this._styleTimer);this._els.note.hidden=true;this._updateZoneOverlay(this._stateObj?.attributes?.parking_zones || []);});
      map.on('error',event=>{if(map===this._map) this._mapFailure(event?.error || new Error('Map resource unavailable'));});
      await new Promise((resolve)=>{
        const finish=()=>{clearTimeout(timer);map.off('load',finish);this._cancelMapWait=null;resolve();};
        this._cancelMapWait=finish;
        if(map.loaded()) finish();else {map.once('load',finish);timer=setTimeout(()=>{this._mapFailure(new Error('Map loading timed out'));finish();},18000);}
      });
      return epoch===this._epoch?map:null;
    })().finally(()=>{if(epoch===this._epoch) this._mapPromise=null;});
    return this._mapPromise;
  }
  _syncStyle() {
    if(!this._map) return;
    const style=this._styleURL();if(style===this._style) return;
    this._style=style;this._fallbackStyle=false;
    // A style diff can omit style.load while removing our custom zone layer.
    // Rebuild the stylesheet only, retaining the map, camera and HTML markers;
    // the existing style.load handler then restores zone sources reliably.
    this._map.setStyle(style, {diff:false});
    clearTimeout(this._styleTimer);this._styleTimer=setTimeout(()=>this._mapFailure(new Error('Map style timed out')),15000);
  }
  _mapFailure(error) {
    if(!this.isConnected || !this._els) return;
    const note=this._els.note;note.hidden=false;note.replaceChildren();
    const text=document.createElement('span');text.textContent=this._xt('map_unavailable');text.title=String(error?.message || error);
    const retry=document.createElement('button');retry.type='button';retry.className='icon-button';retry.setAttribute('aria-label',this._st('retryNow'));retry.textContent='↻';
    retry.onclick=()=>{this._dispose();this._pins=new Map();this.connectedCallback();this._renderView();};note.append(text,retry);
    // Keep the list/filters alive. Never destroy parking results over a tile error.
  }
  _clearMapPins() {for(const {marker} of this._pins?.values() || []) marker.remove();this._pins?.clear();this._destinationPin?.remove();this._destinationPin=null;this._popup?.remove();this._popup=null;}
  _syncMarkers() {
    if(!this._map) return;
    const a=this._stateObj?.attributes || {},lat=osmNumber(a.destination_latitude),lon=osmNumber(a.destination_longitude);
    if(lat===null || lon===null) return;
    if(this.config.show_destination!==false) {
      if(!this._destinationPin) {const button=document.createElement('div');button.className='osm-dest-marker';button.textContent='★';button.title=this._t('destination');this._destinationPin=new maplibregl.Marker({element:button}).setLngLat([lon,lat]).addTo(this._map);}
      this._destinationPin.setLngLat([lon,lat]);
    }
    const keep=new Set();
    (this._visible || []).forEach((item,index)=>{
      const ilat=osmNumber(item.latitude),ilon=osmNumber(item.longitude);if(ilat===null || ilon===null || Math.abs(ilat)>90 || Math.abs(ilon)>180) return;
      const key=osmKey(item);keep.add(key);let pin=this._pins.get(key);
      if(!pin) {const button=document.createElement('button');button.type='button';button.className='osm-park-marker';button.onclick=event=>{event.stopPropagation();this._focusItem(key,{fromMap:true,keyboard:event.detail===0});};
        const popup=new maplibregl.Popup({offset:20,maxWidth:'280px',focusAfterOpen:false});
        const marker=new maplibregl.Marker({element:button}).setLngLat([ilon,ilat]).addTo(this._map);pin={marker,button,popup};this._pins.set(key,pin);}
      const type=osmIconType(item);
      pin.marker.setLngLat([ilon,ilat]);
      // Reuse the actual button so type changes cannot lose keyboard focus.
      if(pin.button.dataset.type!==type) {
        pin.button.innerHTML=osmTypeIconMarkup(item);pin.button.dataset.type=type;
      }
      pin.button.dataset.key=key;pin.button.dataset.index=String(index);
      pin.marker._osmSuggestionIndex=index;
      const label=this._translations().categories[type] || this._t('parking');
      pin.button.title=`${label} · ${String(item.name || '').trim() || this._t('parking')}`;
      pin.button.setAttribute('aria-label',pin.button.title);
      pin.button.setAttribute('aria-pressed',String(key===this._selected));
      pin.button.classList.toggle('selected',key===this._selected);
      pin.button.dataset.kind=osmKind(item);pin.popup.setHTML(this._popupHtml(this._safeItem(item),index));
    });
    for(const [key,pin] of this._pins) if(!keep.has(key)) {pin.marker.remove();pin.popup.remove();this._pins.delete(key);}
  }
  _fitVisible() {
    if(!this._map) return;
    const a=this._stateObj?.attributes || {},bounds=new maplibregl.LngLatBounds();
    const add=(lat,lon)=>{lat=osmNumber(lat);lon=osmNumber(lon);if(lat!==null && lon!==null && Math.abs(lat)<=90 && Math.abs(lon)<=180) bounds.extend([lon,lat]);};
    add(a.destination_latitude,a.destination_longitude);for(const item of this._visible || []) add(item.latitude,item.longitude);
    if(!bounds.isEmpty()) this._map.fitBounds(bounds,{padding:40,maxZoom:16,duration:0});
  }
  _updateZoneOverlay(zones) {
    const map=this._map;if(!map) return;
    // style.load can arrive while GeoJSON sources are still loading. Retry
    // once at idle instead of losing overlays or repeatedly calling setData.
    if(!map.isStyleLoaded()) {
      if(!this._zoneIdlePending) {
        this._zoneIdlePending=true;
        map.once('idle',()=>{
          this._zoneIdlePending=false;
          if(map===this._map) this._updateZoneOverlay(this._stateObj?.attributes?.parking_zones || []);
        });
      }
      return;
    }
    const id='osm-parking-controlled-zones';
    const features=(this.config.show_zones!==false && Array.isArray(zones)?zones:[]).filter(z=>z?.type==='Feature' && ['Polygon','MultiPolygon'].includes(z?.geometry?.type) && z?.properties?.record_type==='zone');
    const data={type:'FeatureCollection',features};
    if(map.getSource(id)) map.getSource(id).setData(data);
    else if(features.length) {map.addSource(id,{type:'geojson',data});map.addLayer({id:id+'-fill',type:'fill',source:id,paint:{'fill-color':'#ce9b49','fill-opacity':0.16}});map.addLayer({id:id+'-border',type:'line',source:id,paint:{'line-color':'#ce9b49','line-width':2}});}
    if(!this._zoneEvents && features.length) {this._zoneEvents=true;map.on('click',id+'-fill',event=>{
      const p=event.features?.[0]?.properties;if(!p) return;
      const url=this._url(p.provider_url);this._popup?.remove();this._popup=new maplibregl.Popup({offset:10}).setLngLat(event.lngLat).setHTML(`<div class="popup-title">${this._esc(p.name || this._zt('zone'))}</div><div class="popup-line">${this._esc(this._zt('signage'))}</div>${url?`<a href="${this._esc(url)}" target="_blank" rel="noopener noreferrer">${this._esc(this._pt('source'))}</a>`:''}`).addTo(map);
    });}
  }
  getCardSize() { return Math.ceil((this.config.height+280)/50); }
  getGridOptions() { return {columns:12,min_columns:6,rows:'auto'}; }
}
