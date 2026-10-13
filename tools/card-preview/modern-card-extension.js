/* OSM Parking: compact UI extension, beta source 2026-10-13.
 * Inserted before registration by apply_card_redesign.py. All original
 * provider code, setup flows, translations and recovery actions are retained.
 * No new dependencies, analytics, credentials or API calls are introduced.
 */
const OSM_PARKING_UI_LABEL_KEYS = [
  'search','filters','sort','allTypes','anyPrice','anyDistance','anyData','nearest',
  'farthest','byType','byName','mostSpaces','bestData','results','of','clear',
  'noMatches','reset','details','reported','static','estimated','predicted',
  'theme','auto','light','dark','fit','expand','collapse','mapLoading','mapFailed',
  'retryMap','showOnMap','mapHeight','settings','live','selected','mapLabel',
];
const OSM_PARKING_UI_LABEL_VALUES = {
 en:['Search parking','Filters','Sort by','All types','Any price','Any distance','Any data','Nearest first','Farthest first','Parking type','Name A–Z','Most free spaces','Best data','results','of','Clear','No results match these filters.','Reset filters','Details','Reported','Location data','Estimated','Predicted','Map theme','Auto','Light','Dark','Fit results','Expand map','Compact map','Loading map…','Map unavailable. Your parking results are still available.','Retry map','Show on map','Map height (px)','Card settings','Live','Selected','Parking map'],
 el:['Αναζήτηση στάθμευσης','Φίλτρα','Ταξινόμηση','Όλοι οι τύποι','Κάθε χρέωση','Κάθε απόσταση','Όλα τα δεδομένα','Πιο κοντά πρώτα','Πιο μακριά πρώτα','Τύπος στάθμευσης','Όνομα Α–Ω','Περισσότερες διαθέσιμες','Πιο αξιόπιστα δεδομένα','αποτελέσματα','από','Καθαρισμός','Κανένα αποτέλεσμα με αυτά τα φίλτρα.','Επαναφορά φίλτρων','Λεπτομέρειες','Αναφερόμενες','Στοιχεία χώρου','Εκτίμηση','Πρόβλεψη','Θέμα χάρτη','Αυτόματο','Φωτεινό','Σκοτεινό','Εμφάνιση όλων','Μεγαλύτερος χάρτης','Μικρότερος χάρτης','Φόρτωση χάρτη…','Ο χάρτης δεν είναι διαθέσιμος. Οι προτάσεις στάθμευσης παραμένουν διαθέσιμες.','Επανάληψη χάρτη','Εμφάνιση στον χάρτη','Ύψος χάρτη (px)','Ρυθμίσεις κάρτας','Ζωντανά','Επιλεγμένο','Χάρτης στάθμευσης'],
 de:['Parkplätze suchen','Filter','Sortieren','Alle Arten','Jeder Preis','Jede Entfernung','Alle Daten','Nächste zuerst','Entfernteste zuerst','Parkplatzart','Name A–Z','Meiste freie Plätze','Beste Daten','Ergebnisse','von','Löschen','Keine Ergebnisse für diese Filter.','Filter zurücksetzen','Details','Gemeldet','Standortdaten','Geschätzt','Prognose','Kartendesign','Automatisch','Hell','Dunkel','Ergebnisse zeigen','Karte vergrößern','Karte verkleinern','Karte lädt…','Karte nicht verfügbar. Die Parkvorschläge bleiben verfügbar.','Karte erneut laden','Auf Karte zeigen','Kartenhöhe (px)','Karteneinstellungen','Live','Ausgewählt','Parkplatzkarte'],
 fr:['Rechercher un parking','Filtres','Trier par','Tous les types','Tous les prix','Toute distance','Toutes les données','Plus proches','Plus éloignés','Type de parking','Nom A–Z','Plus de places libres','Meilleures données','résultats','sur','Effacer','Aucun résultat pour ces filtres.','Réinitialiser','Détails','Déclarées','Localisation','Estimation','Prévision','Thème de carte','Auto','Clair','Sombre','Voir les résultats','Agrandir la carte','Réduire la carte','Chargement…','Carte indisponible. Les résultats restent accessibles.','Réessayer la carte','Voir sur la carte','Hauteur (px)','Réglages de carte','En direct','Sélectionné','Carte des parkings'],
 es:['Buscar aparcamiento','Filtros','Ordenar','Todos los tipos','Cualquier precio','Cualquier distancia','Todos los datos','Más cercanos','Más lejanos','Tipo','Nombre A–Z','Más plazas libres','Mejores datos','resultados','de','Borrar','Ningún resultado con estos filtros.','Restablecer filtros','Detalles','Comunicadas','Ubicación','Estimación','Predicción','Tema del mapa','Auto','Claro','Oscuro','Ver resultados','Ampliar mapa','Reducir mapa','Cargando mapa…','Mapa no disponible. Los resultados siguen disponibles.','Reintentar mapa','Ver en mapa','Altura (px)','Ajustes de tarjeta','En directo','Seleccionado','Mapa de aparcamientos'],
 it:['Cerca parcheggio','Filtri','Ordina per','Tutti i tipi','Qualsiasi prezzo','Qualsiasi distanza','Tutti i dati','Più vicini','Più lontani','Tipo','Nome A–Z','Più posti liberi','Dati migliori','risultati','di','Cancella','Nessun risultato con questi filtri.','Reimposta filtri','Dettagli','Segnalati','Posizione','Stima','Previsione','Tema mappa','Auto','Chiaro','Scuro','Mostra risultati','Ingrandisci mappa','Riduci mappa','Caricamento…','Mappa non disponibile. I risultati restano disponibili.','Riprova mappa','Mostra sulla mappa','Altezza (px)','Impostazioni scheda','In diretta','Selezionato','Mappa parcheggi'],
 nl:['Parkeerplaatsen zoeken','Filters','Sorteren','Alle soorten','Elke prijs','Elke afstand','Alle gegevens','Dichtstbij eerst','Verste eerst','Parkeertype','Naam A–Z','Meeste vrije plekken','Beste gegevens','resultaten','van','Wissen','Geen resultaten met deze filters.','Filters wissen','Details','Gemeld','Locatiegegevens','Geschat','Voorspeld','Kaartthema','Auto','Licht','Donker','Toon resultaten','Kaart vergroten','Kaart verkleinen','Kaart laden…','Kaart niet beschikbaar. Parkeerresultaten blijven beschikbaar.','Kaart opnieuw laden','Toon op kaart','Kaarthoogte (px)','Kaartinstellingen','Live','Geselecteerd','Parkeerkaart'],
 pl:['Szukaj parkingu','Filtry','Sortuj','Wszystkie typy','Każda cena','Każda odległość','Wszystkie dane','Najbliższe','Najdalsze','Typ parkingu','Nazwa A–Z','Najwięcej wolnych','Najlepsze dane','wyników','z','Wyczyść','Brak wyników dla tych filtrów.','Resetuj filtry','Szczegóły','Zgłoszone','Lokalizacja','Szacowane','Prognoza','Motyw mapy','Auto','Jasny','Ciemny','Pokaż wyniki','Powiększ mapę','Zmniejsz mapę','Ładowanie mapy…','Mapa niedostępna. Wyniki pozostają dostępne.','Ponów mapę','Pokaż na mapie','Wysokość (px)','Ustawienia karty','Na żywo','Wybrano','Mapa parkingów'],
 pt:['Procurar estacionamento','Filtros','Ordenar','Todos os tipos','Qualquer preço','Qualquer distância','Todos os dados','Mais próximos','Mais distantes','Tipo','Nome A–Z','Mais lugares livres','Melhores dados','resultados','de','Limpar','Sem resultados com estes filtros.','Repor filtros','Detalhes','Comunicados','Localização','Estimativa','Previsão','Tema do mapa','Auto','Claro','Escuro','Mostrar resultados','Ampliar mapa','Reduzir mapa','A carregar mapa…','Mapa indisponível. Os resultados continuam disponíveis.','Tentar mapa','Mostrar no mapa','Altura (px)','Definições do cartão','Em direto','Selecionado','Mapa de estacionamento'],
 'pt-BR':['Buscar estacionamento','Filtros','Ordenar','Todos os tipos','Qualquer preço','Qualquer distância','Todos os dados','Mais próximos','Mais distantes','Tipo','Nome A–Z','Mais vagas livres','Melhores dados','resultados','de','Limpar','Nenhum resultado com estes filtros.','Redefinir filtros','Detalhes','Informadas','Localização','Estimativa','Previsão','Tema do mapa','Auto','Claro','Escuro','Mostrar resultados','Ampliar mapa','Reduzir mapa','Carregando mapa…','Mapa indisponível. Os resultados continuam disponíveis.','Tentar mapa','Mostrar no mapa','Altura (px)','Ajustes do cartão','Ao vivo','Selecionado','Mapa de estacionamento'],
 ru:['Поиск парковки','Фильтры','Сортировка','Все типы','Любая цена','Любое расстояние','Все данные','Ближайшие','Дальние','Тип парковки','Название А–Я','Больше свободных','Лучшие данные','результатов','из','Очистить','Нет результатов для этих фильтров.','Сбросить фильтры','Подробнее','Заявлено','Местоположение','Оценка','Прогноз','Тема карты','Авто','Светлая','Тёмная','Все результаты','Увеличить карту','Уменьшить карту','Загрузка карты…','Карта недоступна. Результаты парковки доступны.','Повторить загрузку','На карте','Высота (px)','Настройки карточки','Онлайн','Выбрано','Карта парковок'],
 tr:['Otopark ara','Filtreler','Sırala','Tüm türler','Tüm ücretler','Tüm mesafeler','Tüm veriler','En yakın','En uzak','Otopark türü','Ad A–Z','En çok boş yer','En iyi veri','sonuç','/','Temizle','Bu filtrelerle sonuç bulunamadı.','Filtreleri sıfırla','Ayrıntılar','Bildirilen','Konum bilgisi','Tahmini','Öngörü','Harita teması','Otomatik','Açık','Koyu','Sonuçları göster','Haritayı büyüt','Haritayı küçült','Harita yükleniyor…','Harita kullanılamıyor. Park sonuçları kullanılabilir.','Haritayı yeniden dene','Haritada göster','Harita yüksekliği (px)','Kart ayarları','Canlı','Seçili','Otopark haritası'],
 'zh-Hans':['搜索停车场','筛选','排序','所有类型','所有价格','所有距离','所有数据','最近优先','最远优先','停车类型','名称顺序','空位最多','数据质量','结果','共','清除','没有符合筛选条件的结果。','重置筛选','详情','报告数','位置数据','估计','预测','地图主题','自动','浅色','深色','显示结果','放大地图','缩小地图','正在加载地图…','地图不可用，停车结果仍然可用。','重试地图','在地图上显示','地图高度 (px)','卡片设置','实时','已选','停车地图'],
 ja:['駐車場を検索','絞り込み','並べ替え','すべての種類','すべての料金','すべての距離','すべてのデータ','近い順','遠い順','駐車場の種類','名前順','空きが多い順','データ品質','件','/','クリア','条件に一致する結果がありません。','条件をリセット','詳細','報告値','所在地データ','推定','予測','地図のテーマ','自動','ライト','ダーク','結果を表示','地図を拡大','地図を縮小','地図を読み込み中…','地図は利用できません。駐車場の結果は表示できます。','地図を再試行','地図に表示','高さ (px)','カード設定','リアルタイム','選択中','駐車場の地図'],
};
OSM_PARKING_UI_LABEL_KEYS.push(...["hours", "state", "open", "closed", "full", "unknown", "capacity", "entity", "title"]);
for (const [lang, values] of Object.entries({"en": ["Opening hours", "Status", "Open", "Closed", "Full", "Unknown", "Total spaces", "OSM Parking sensor", "Title"], "el": ["Ωράριο", "Κατάσταση", "Ανοιχτό", "Κλειστό", "Πλήρες", "Άγνωστο", "Συνολικές θέσεις", "Αισθητήρας OSM Parking", "Τίτλος"], "de": ["Öffnungszeiten", "Status", "Geöffnet", "Geschlossen", "Voll", "Unbekannt", "Gesamtplätze", "OSM-Parking-Sensor", "Titel"], "fr": ["Horaires", "État", "Ouvert", "Fermé", "Complet", "Inconnu", "Places totales", "Capteur OSM Parking", "Titre"], "es": ["Horario", "Estado", "Abierto", "Cerrado", "Completo", "Desconocido", "Plazas totales", "Sensor OSM Parking", "Título"], "it": ["Orari", "Stato", "Aperto", "Chiuso", "Completo", "Sconosciuto", "Posti totali", "Sensore OSM Parking", "Titolo"], "nl": ["Openingstijden", "Status", "Open", "Gesloten", "Vol", "Onbekend", "Totaal plekken", "OSM Parking-sensor", "Titel"], "pl": ["Godziny otwarcia", "Stan", "Otwarty", "Zamknięty", "Pełny", "Nieznany", "Wszystkie miejsca", "Czujnik OSM Parking", "Tytuł"], "pt": ["Horário", "Estado", "Aberto", "Fechado", "Completo", "Desconhecido", "Lugares totais", "Sensor OSM Parking", "Título"], "pt-BR": ["Horário", "Estado", "Aberto", "Fechado", "Lotado", "Desconhecido", "Vagas totais", "Sensor OSM Parking", "Título"], "ru": ["Часы работы", "Состояние", "Открыто", "Закрыто", "Заполнено", "Неизвестно", "Всего мест", "Датчик OSM Parking", "Заголовок"], "tr": ["Çalışma saatleri", "Durum", "Açık", "Kapalı", "Dolu", "Bilinmiyor", "Toplam yer", "OSM Parking sensörü", "Başlık"], "zh-Hans": ["开放时间", "状态", "开放", "关闭", "已满", "未知", "总车位", "OSM Parking 传感器", "标题"], "ja": ["営業時間", "状態", "営業中", "閉鎖", "満車", "不明", "総駐車台数", "OSM Parking センサー", "タイトル"]})) OSM_PARKING_UI_LABEL_VALUES[lang].push(...values);
function osmUiText(language, key) {
  const lang = String(language || 'en').replace('_', '-');
  const values = OSM_PARKING_UI_LABEL_VALUES[lang] || OSM_PARKING_UI_LABEL_VALUES[lang.split('-')[0]] || OSM_PARKING_UI_LABEL_VALUES.en;
  const index = OSM_PARKING_UI_LABEL_KEYS.indexOf(key);
  return values[index] ?? OSM_PARKING_UI_LABEL_VALUES.en[index] ?? key;
}
const OSM_UI_TYPES = ['paid','open','street','underground','multi_storey','park_and_ride','other'];
const OSM_UI_SORTS = ['distance','distance_desc','type','name','availability','quality'];
const OSM_UI_DEFAULTS = Object.freeze({query:'',type:'all',fee:'all',distance:'all',data:'all',sort:'distance'});
function osmUiNumber(value) {
  if (value == null || value === '' || typeof value === 'boolean') return null;
  const n = Number(value); return Number.isFinite(n) ? n : null;
}
function osmUiKind(item) {
  const value = item.availability_kind || (item.has_realtime_data ? 'live' : item.has_estimated_occupancy ? 'estimated' : 'static');
  return ['live','reported','estimated','predicted'].includes(value) ? value : 'static';
}
function osmUiFree(item) {
  if (!['live','reported'].includes(osmUiKind(item)) || ['closed','out_of_service'].includes(item.opening_status)) return null;
  const n = osmUiNumber(item.free_capacity), total = osmUiNumber(item.capacity);
  return n !== null && Number.isInteger(n) && n >= 0 && (total === null || n <= total) ? n : null;
}
function osmUiTypes(item) {
  const types = new Set([item.category || 'other']);
  const form = String(item.parking_type || '').toLowerCase();
  if (['underground','basement','souterrain'].some(x => form.includes(x))) types.add('underground');
  if (['street','on_kerb','lane'].some(x => form.includes(x))) types.add('street');
  if (['surface','off_street_parking_ground','carports','rooftop'].includes(form)) types.add('open');
  if (['multi_storey','multi-storey','multi_level','car_park'].includes(form)) types.add('multi_storey');
  if (form === 'park_and_ride') types.add('park_and_ride');
  return types;
}
function osmUiSelect(items, filters, language, typeLabel) {
  let collator; try { collator = new Intl.Collator(language || 'en', {sensitivity:'base',numeric:true}); } catch (_) { collator = new Intl.Collator('en'); }
  const compare = (a,b) => collator.compare(String(a || ''), String(b || ''));
  const query = String(filters.query || '').trim().toLocaleLowerCase();
  const numeric = (a,b,desc=false) => a === null ? (b === null ? 0 : 1) : b === null ? -1 : (desc ? b-a : a-b);
  return items.filter(item => item && typeof item === 'object' && item.record_type !== 'zone')
    .filter(item => !query || [item.name,item.address,item.provider_name].some(v => String(v || '').toLocaleLowerCase().includes(query)))
    .filter(item => filters.type === 'all' || osmUiTypes(item).has(filters.type))
    .filter(item => filters.fee === 'all' || String(item.fee).toLowerCase() === filters.fee)
    .filter(item => filters.distance === 'all' || (osmUiNumber(item.distance_m) !== null && Number(item.distance_m) <= Number(filters.distance)))
    .filter(item => filters.data === 'all' || (filters.data === 'available' ? osmUiFree(item) > 0 && item.opening_status !== 'closed' : osmUiKind(item) === filters.data))
    .map((item,index) => ({item,index})).sort((a,b) => {
      let order=0;
      switch (filters.sort) {
        case 'distance_desc': order=numeric(osmUiNumber(a.item.distance_m),osmUiNumber(b.item.distance_m),true); break;
        case 'type': order=compare(typeLabel(a.item),typeLabel(b.item)); break;
        case 'name': order=compare(a.item.name,b.item.name); break;
        case 'availability': order=numeric(osmUiFree(a.item),osmUiFree(b.item),true); break;
        case 'quality': {
          const rank={live:4,reported:3,estimated:2,predicted:1,static:0};
          order=rank[osmUiKind(b.item)]-rank[osmUiKind(a.item)]; break;
        }
        default: order=numeric(osmUiNumber(a.item.distance_m),osmUiNumber(b.item.distance_m));
      }
      return order || numeric(osmUiNumber(a.item.distance_m),osmUiNumber(b.item.distance_m)) || compare(a.item.name,b.item.name) || a.index-b.index;
    }).map(({item}) => item);
}
function osmUiSafeUrl(value) {
  try { const u=new URL(String(value)); return ['https:','http:','geo:'].includes(u.protocol) ? u.href : ''; } catch (_) { return ''; }
}
const OSM_UI_ICONS = {
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
 filters:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>',
 route:'<path d="m3 10 18-7-7 18-3-8-8-3Z"/>',
 fit:'<circle cx="12" cy="12" r="6"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/>',
 expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
 refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3"/>',
 chevron:'<path d="m9 5 7 7-7 7"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
};
function osmUiIcon(name) { return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${OSM_UI_ICONS[name] || OSM_UI_ICONS.chevron}</svg>`; }

class OsmParkingMapCardCompact extends OsmParkingMapCardV070 {
  static getStubConfig() { return {entity:'sensor.parking_suggestions',map_height:250,map_theme:'auto',show_list:true}; }
  static getConfigElement() { return document.createElement('osm-parking-compact-editor'); }
  setConfig(config) {
    if (!config?.entity) throw new Error('Please define an OSM Parking entity');
    this._disposeMap();
    const height=osmUiNumber(config.map_height ?? config.height);
    this.config={show_list:true,show_destination:true,show_zones:true,show_price:true,show_filters:true,remember_filters:true,map_theme:'auto',...config};
    this._height=height !== null ? Math.max(180,Math.min(600,height)) : 250;
    this._filters={...OSM_UI_DEFAULTS,sort:OSM_UI_SORTS.includes(config.sort_by) ? config.sort_by : 'distance'};
    this._theme=['auto','light','dark'].includes(this.config.map_theme) ? this.config.map_theme : 'auto';
    this._expanded=false; this._filterOpen=false; this._view=[]; this._items=[]; this._zones=[];
    this._selected=null; this._lastSignature=null; this._restoreKey=null; this._canMap=false;
    this._renderShell();
    if (this._hass) this.hass=this._hass;
    if (this.isConnected) this._watchSize();
  }
  connectedCallback() {
    this._watchSize();
    if (!this._media) {
      this._media=window.matchMedia('(prefers-color-scheme: dark)');
      this._mediaChange=() => { if (this._theme==='auto' && this._hass) this.hass=this._hass; };
      this._media.addEventListener?.('change',this._mediaChange);
    }
    if (this._canMap) void this._ensureCompactMap();
  }
  disconnectedCallback() {
    this._resizeObserver?.disconnect();
    this._media?.removeEventListener?.('change',this._mediaChange); this._media=null;
    this._disposeMap();
  }
  _watchSize() {
    this._resizeObserver?.disconnect();
    if (!this._els || !window.ResizeObserver) return;
    this._resizeObserver=new ResizeObserver(() => {
      cancelAnimationFrame(this._resizeFrame);
      this._resizeFrame=requestAnimationFrame(() => this._map?.resize());
    });
    this._resizeObserver.observe(this._els.map);
  }
  _disposeMap() {
    this._generation=(this._generation || 0)+1;
    clearTimeout(this._mapTimer); clearTimeout(this._searchTimer); cancelAnimationFrame(this._resizeFrame);
    this._mapPromise=null; this._mapIssue=false; this._mapReady=false; this._mapStyle=null;
    this._markers?.forEach(marker => marker.remove()); this._markers=[];
    try { this._map?.remove(); } catch (_) { /* partially constructed WebGL context */ }
    this._map=null; this._fitPending=true;
  }
  getCardSize() { return Math.max(5, Math.ceil((this._height+260)/50)); }
  getGridOptions() { return {columns:12,rows:'auto',min_columns:6}; }
  _u(key) { return osmUiText(this._hass?.language,key); }
  _n(value) { return osmUiNumber(value); }
  _dark() {
    if (this._theme!=='auto') return this._theme==='dark';
    return this._hassDark();
  }
  _hassDark() {
    if (typeof this._hass?.themes?.darkMode==='boolean') return this._hass.themes.darkMode;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  }
  _styleUrl() {
    const dark=this._dark();
    if (dark && this.config.map_style_dark) return this.config.map_style_dark;
    if (this.config.map_style) return this.config.map_style;
    return `https://tiles.openfreemap.org/styles/${dark ? 'dark' : 'positron'}`;
  }
  set hass(hass) {
    this._hass=hass;
    if (!this.config || !this._els) return;
    this._restoreFilters();
    this.setAttribute('data-dark',String(this._hassDark()));
    const state=hass?.states?.[this.config.entity];
    const signature=JSON.stringify({state:state?.state,a:state?.attributes,lang:hass?.language,user:hass?.user?.id,dark:this._dark()});
    if (signature===this._lastSignature) return;
    this._lastSignature=signature; this._stateObj=state;
    this._update();
  }
  _storageKey() { return `osm-parking-ui:v1:${this._hass?.user?.id || 'local'}:${location.pathname}:${this.config.entity}:${this.config.filter_key || this.config.title || ''}`; }
  _restoreFilters() {
    if (this.config.remember_filters===false) return;
    const key=this._storageKey(); if (key===this._restoreKey) return;
    this._restoreKey=key;
    this._filters={...OSM_UI_DEFAULTS,sort:OSM_UI_SORTS.includes(this.config.sort_by)?this.config.sort_by:'distance'};
    try {
      const saved=JSON.parse(sessionStorage.getItem(key) || 'null'); if (!saved || typeof saved!=='object') return;
      const enums={type:['all',...OSM_UI_TYPES],fee:['all','yes','no','unknown'],distance:['all','250','500','1000','2000','5000'],data:['all','live','reported','estimated','predicted','static','available'],sort:OSM_UI_SORTS};
      for (const [name,values] of Object.entries(enums)) if (values.includes(saved[name])) this._filters[name]=saved[name];
      if (typeof saved.query==='string') this._filters.query=saved.query.slice(0,200);
    } catch (_) { /* private browsing / storage disabled: controls still work */ }
  }
  _saveFilters() {
    if (this.config.remember_filters===false) return;
    try { sessionStorage.setItem(this._storageKey(),JSON.stringify(this._filters)); } catch (_) { /* not required */ }
  }
  _renderShell() {
    if (!this.shadowRoot) this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML=`<style>${OSM_PARKING_COMPACT_CSS}</style>
      <ha-card>
        <header class="header"><div class="brand" aria-hidden="true">P</div><div class="headtext"><h2 class="title"></h2><p class="subtitle"></p></div><button type="button" class="icon-button refresh">${osmUiIcon('refresh')}</button></header>
        <div class="status-panel" hidden><div class="status-head"><ha-icon class="status-icon"></ha-icon><div><div class="status-title"></div><div class="status-message"></div></div></div><div class="status-actions"></div><details class="status-details" hidden><summary></summary><pre></pre></details></div>
        <section class="map-section"><div class="map" style="height:${this._height}px"></div><div class="map-controls"><button type="button" class="map-button fit">${osmUiIcon('fit')}</button><button type="button" class="map-button expand">${osmUiIcon('expand')}</button><label class="theme-wrap">${osmUiIcon('sun')}<select class="theme"></select></label></div><div class="map-message" role="status"><span></span><button type="button" class="retry-map" hidden></button></div></section>
        <section class="results-section"><div class="toolbar"><label class="search-wrap">${osmUiIcon('search')}<input class="search" type="search" maxlength="200" autocomplete="off"></label><button type="button" class="filter-button" aria-controls="filter-panel" aria-expanded="false">${osmUiIcon('filters')}<span></span><b class="filter-count" hidden></b></button></div>
          <div id="filter-panel" class="filter-panel" hidden><label><span class="type-label"></span><select class="filter-type"></select></label><label><span class="fee-label"></span><select class="filter-fee"></select></label><label><span class="distance-label"></span><select class="filter-distance"></select></label><label><span class="data-label"></span><select class="filter-data"></select></label></div>
          <div class="results-bar"><span class="result-count" role="status" aria-live="polite" aria-atomic="true"></span><div class="result-tools"><button type="button" class="clear" hidden></button><label class="sort-wrap"><span></span><select class="sort"></select></label></div></div>
          <div class="list"></div><div class="empty" hidden><span></span><button type="button" class="reset"></button></div>
        </section>
        <footer><span class="footer-note"></span><span class="zone-note" hidden></span></footer>
      </ha-card>`;
    const q=s => this.shadowRoot.querySelector(s);
    this._els={title:q('.title'),subtitle:q('.subtitle'),map:q('.map'),list:q('.list'),status:q('.status-panel'),statusIcon:q('.status-icon'),statusTitle:q('.status-title'),statusMessage:q('.status-message'),statusActions:q('.status-actions'),statusDetails:q('.status-details'),statusDetailsSummary:q('.status-details summary'),statusDetailsPre:q('.status-details pre')};
    this._q=q;
    q('.refresh').onclick=() => void this._retryNow();
    q('.fit').onclick=() => this._fitMap();
    q('.expand').onclick=() => { this._expanded=!this._expanded; this._els.map.style.height=`${this._expanded ? Math.max(this._height,440) : this._height}px`; q('.expand').title=this._u(this._expanded?'collapse':'expand'); q('.expand').setAttribute('aria-label',q('.expand').title); q('.expand').setAttribute('aria-pressed',String(this._expanded)); this._map?.resize(); };
    q('.theme').onchange=e => { this._theme=e.target.value; this.setAttribute('data-dark',String(this._hassDark())); this._applyMapStyle(); };
    q('.retry-map').onclick=() => { this._disposeMap(); void this._ensureCompactMap(); };
    q('.filter-button').onclick=() => { this._filterOpen=!this._filterOpen; q('#filter-panel').hidden=!this._filterOpen; q('.filter-button').setAttribute('aria-expanded',String(this._filterOpen)); };
    q('.search').oninput=e => { this._filters.query=e.target.value; clearTimeout(this._searchTimer); this._searchTimer=setTimeout(() => this._filterChanged(),120); };
    for (const field of ['type','fee','distance','data']) q(`.filter-${field}`).onchange=e => { this._filters[field]=e.target.value; this._filterChanged(); };
    q('.sort').onchange=e => { this._filters.sort=e.target.value; this._filterChanged(); };
    q('.clear').onclick=q('.reset').onclick=() => { this._filters={...OSM_UI_DEFAULTS,sort:this._filters.sort}; this._labels(); this._filterChanged(); };
    this._labels();
  }
  _options(selector, choices, value) {
    const el=this._q(selector); const sig=JSON.stringify(choices);
    if (el.dataset.options!==sig) { el.innerHTML=choices.map(([v,label]) => `<option value="${this._esc(v)}">${this._esc(label)}</option>`).join(''); el.dataset.options=sig; }
    el.value=value;
  }
  _labels() {
    if (!this._q) return;
    const q=this._q, t=k=>this._u(k);
    q('.search').placeholder=t('search'); q('.search').setAttribute('aria-label',t('search')); q('.search').value=this._filters.query;
    q('.filter-button span').textContent=t('filters');
    q('.clear').textContent=t('clear'); q('.reset').textContent=t('reset');
    q('.sort-wrap span').textContent=t('sort'); q('.retry-map').textContent=t('retryMap');
    for (const [sel,key] of [['.refresh','retryNow'],['.fit','fit'],['.expand',this._expanded?'collapse':'expand']]) {
      const label=sel==='.refresh'?this._st(key):t(key); q(sel).title=label; q(sel).setAttribute('aria-label',label);
    }
    q('.map').setAttribute('aria-label',t('mapLabel')); q('.map').setAttribute('role','region');
    q('.theme').setAttribute('aria-label',t('theme'));
    q('.type-label').textContent=this._t('type'); q('.fee-label').textContent=this._t('price'); q('.distance-label').textContent=this._t('distance'); q('.data-label').textContent=t('anyData');
    this._options('.theme',[['auto',t('auto')],['light',t('light')],['dark',t('dark')]],this._theme);
    this._options('.filter-type',[['all',t('allTypes')],...OSM_UI_TYPES.map(type=>[type,this._translations().categories?.[type] || type])],this._filters.type);
    this._options('.filter-fee',[['all',t('anyPrice')],['no',this._t('free')],['yes',this._t('paid')],['unknown',t('unknown')]],this._filters.fee);
    this._options('.filter-distance',[['all',t('anyDistance')],...['250','500','1000','2000','5000'].map(n=>[n,`≤ ${Number(n)>=1000?`${Number(n)/1000} km`:`${n} m`}`])],this._filters.distance);
    this._options('.filter-data',[['all',t('anyData')],['available',`${this._pt('available')} > 0`],...['live','reported','estimated','predicted','static'].map(k=>[k,t(k)])],this._filters.data);
    this._options('.sort',[['distance',t('nearest')],['distance_desc',t('farthest')],['type',t('byType')],['name',t('byName')],['availability',t('mostSpaces')],['quality',t('bestData')]],this._filters.sort);
    q('.toolbar').hidden=this.config.show_filters===false;
    q('.list').hidden=this.config.show_list===false;
    q('.footer-note').textContent='OpenStreetMap · OSM Parking';
  }
  _setContentVisible(visible) {
    if (!this._q) return;
    this._q('.map-section').hidden=!visible; this._q('.results-section').hidden=!visible;
    this._q('.zone-note').hidden=!visible || !this._zones?.length || this.config.show_zones===false;
    this._canMap=visible;
    if (!visible) { this._view=[]; this._zones=[]; this._els.list.replaceChildren(); this._clearMarkers(); if (this._map?.isStyleLoaded()) this._syncZones(); }
  }
  _update() {
    this._labels(); this._hideStatus();
    this._els.title.textContent=this.config.title || this._t('title');
    const state=this._stateObj, a=state?.attributes || {};
    this._els.subtitle.textContent=a.destination_name || a.destination_entity || this.config.entity;
    if (!state || (!('destination_entity' in a) && !Array.isArray(a.suggestions))) {
      this._setContentVisible(false);
      this._showStatus({title:this._st(!state?'entityMissingTitle':'wrongEntityTitle'),message:this._st(!state?'entityMissingBody':'wrongEntityBody'),actions:[{label:this._st('settings'),handler:()=>this._openSettings()}]}); return;
    }
    this._items=Array.isArray(a.suggestions)?a.suggestions:[];
    this._zones=Array.isArray(a.parking_zones)?a.parking_zones:[];
    if (this._showBackendStatus(a)) { this._setContentVisible(false); return; }
    if (['unavailable','unknown','waiting'].includes(state.state) || this._n(a.destination_latitude)===null || this._n(a.destination_longitude)===null) {
      this._setContentVisible(false);
      this._showStatus({tone:'warning',title:this._st('sourceCoordsTitle'),message:this._st('sourceCoordsBody'),actions:[{label:this._st('openSource'),handler:()=>this._openSource(a.destination_entity)}]}); return;
    }
    this._setContentVisible(true);
    const dest=`${a.destination_latitude},${a.destination_longitude}`;
    if (dest!==this._destinationKey) { this._fitPending=true; this._destinationKey=dest; this._selected=null; }
    this._filterChanged(false);
    if (this._mapReady) this._syncZones();
    const zone=this._q('.zone-note'); zone.textContent=this._zt('signage'); zone.hidden=!this._zones.length || this.config.show_zones===false;
    if (!this._mapIssue) void this._ensureCompactMap();
    this._applyMapStyle();
  }
  _filterChanged(save=true) {
    if (save) this._saveFilters();
    this._view=osmUiSelect(this._items || [],this._filters,this._hass?.language,item=>this._labelType(item));
    const count=['query','type','fee','distance','data'].filter(k=>this._filters[k]!==OSM_UI_DEFAULTS[k]).length;
    const q=this._q; q('.filter-count').textContent=String(count); q('.filter-count').hidden=!count; q('.clear').hidden=!count;
    q('.result-count').textContent=`${this._view.length} ${this._u('of')} ${this._items.length} ${this._u('results')}`;
    q('.empty').hidden=this._view.length>0; q('.empty span').textContent=count?this._u('noMatches'):this._st('noResultsBody'); q('.reset').hidden=!count;
    this._renderList(this._view);
    if (this._map && this._mapReady) this._syncMarkers();
  }
  _identity(item) { return `${item.provider_id || item.osm_id || item.name || ''}:${item.latitude},${item.longitude}`; }
  _distance(item) { const d=this._n(item.distance_m); if (d===null || d<0) return '—'; return d>=1000?`${(d/1000).toLocaleString(this._hass?.language || 'en',{maximumFractionDigits:1})} km`:`${Math.round(d)} m`; }
  _availability(item) {
    const kind=osmUiKind(item), free=osmUiFree(item);
    if (item.opening_status==='closed') return {kind:'static',text:this._u('closed'),title:this._u('closed')};
    if (['live','reported'].includes(kind) && free!==null) return {kind,text:`${free} ${kind==='live'?this._pt('available'):this._u('reported')}`,title:kind==='reported'?this._qt('reported'):this._pt('live')};
    if (kind==='estimated') { const text=this._estimatedOccupancyText(item); if (text) return {kind,text:`${this._u('estimated')} · ${text}`,title:this._estimatedTranslations().label}; }
    if (kind==='predicted') { const p=this._n(item.predicted_occupancy_percent) ?? (this._n(item.predicted_occupancy_ratio)!==null?Number(item.predicted_occupancy_ratio)*100:null); if (p!==null && p>=0 && p<=100) return {kind,text:`${this._u('predicted')} · ${Math.round(p)}%`,title:this._u('predicted')}; }
    return {kind:'static',text:this._u('static'),title:this._u('static')};
  }
  _popupHtml(item,index) {
    const availability=this._availability(item), price=this._displayPrice(item), url=osmUiSafeUrl(item.navigation_url);
    return `<div class="popup-title">${index+1}. ${this._esc(item.name || this._t('parking'))}</div><div class="popup-line">${this._esc(this._distance(item))} · ${this._esc(this._labelType(item))}</div><div class="popup-line">${this._esc(availability.text)}</div>${price?`<div class="popup-line">${this._esc(price)}</div>`:''}${url?`<div class="popup-actions"><a href="${this._esc(url)}" target="_blank" rel="noopener noreferrer">${this._esc(this._t('navigate'))}</a></div>`:''}`;
  }
  _renderList(items) {
    if (!this._els || this.config.show_list===false) return;
    const root=this._els.list;
    const open=new Set([...root.querySelectorAll('details[open]')].map(el=>el.dataset.key));
    const active=this.shadowRoot.activeElement;
    const focusKey=active?.dataset?.focusKey;
    const fragment=document.createDocumentFragment();
    items.forEach((item,index) => {
      const identity=this._identity(item), price=this._displayPrice(item), data=this._availability(item);
      const row=document.createElement('article'); row.className='parking-row'; row.dataset.key=identity;
      row.classList.toggle('selected',identity===this._selected);
      const nav=osmUiSafeUrl(item.navigation_url), source=osmUiSafeUrl(item.provider_url), osm=osmUiSafeUrl(item.osm_url);
      row.innerHTML=`<div class="row-main"><button type="button" class="row-select" data-focus-key="${this._esc(identity)}:select" aria-label="${this._esc(this._u('showOnMap'))}: ${this._esc(item.name)}"><span class="number">${index+1}</span><span class="row-body"><span class="row-title">${this._esc(item.name || this._t('parking'))}</span><span class="row-meta"><strong>${this._esc(this._distance(item))}</strong><span>·</span>${this._esc(this._labelType(item))}</span></span></button><div class="row-right"><span class="row-price ${item.fee==='no'?'free':''}">${this._esc(price || '—')}</span>${nav?`<a class="navigate" data-focus-key="${this._esc(identity)}:nav" href="${this._esc(nav)}" target="_blank" rel="noopener noreferrer" aria-label="${this._esc(this._t('navigate'))}: ${this._esc(item.name)}">${osmUiIcon('route')}</a>`:''}</div></div><div class="row-bottom"><span class="data-chip ${data.kind}" title="${this._esc(data.title)}"><span class="data-dot" aria-hidden="true"></span>${this._esc(data.text)}</span><details data-key="${this._esc(identity)}"><summary data-focus-key="${this._esc(identity)}:details">${this._esc(this._u('details'))}</summary><div class="detail-content"></div></details></div>`;
      const detail=row.querySelector('.detail-content');
      const add=(label,value) => { if (value===null || value===undefined || value==='' || value==='unknown') return; const line=document.createElement('div'); const strong=document.createElement('strong'); strong.textContent=label+': '; line.append(strong,document.createTextNode(String(value))); detail.append(line); };
      add(this._pt('source'),item.provider_name || item.provider);
      add(this._t('access'),item.access); add(this._t('type'),item.parking_type);
      if (data.kind==='reported') { const note=document.createElement('div'); note.textContent=this._qt('reported'); detail.append(note); add(this._qt('checked'),this._formatProviderTime(item.availability_checked_at) || '—'); }
      if (data.kind==='live') add(this._pt('updated'),this._formatProviderTime(item.realtime_updated_at));
      if (item.address) add(this._t('destination'),item.address);
      if (item.opening_hours) add(this._u('hours'),item.opening_hours);
      if (item.opening_status) add(this._u('state'),['open','closed','full','unknown'].includes(item.opening_status)?this._u(item.opening_status):item.opening_status);
      if (this._n(item.capacity)!==null) add(this._u('capacity'),item.capacity);
      if (Array.isArray(item.data_sources) && item.data_sources.length>1) add(this._qt('sources'),item.data_sources.join(' · '));
      const links=document.createElement('div'); links.className='detail-links';
      for (const [url,label] of [[source,this._pt('source')],[osm,'OSM']]) if (url) { const a=document.createElement('a'); a.href=url; a.textContent=label; a.target='_blank'; a.rel='noopener noreferrer'; links.append(a); }
      detail.append(links); row.querySelector('details').open=open.has(identity);
      row.querySelector('.row-select').onclick=() => this._selectItem(item,index);
      fragment.append(row);
    });
    root.replaceChildren(fragment);
    if (focusKey) [...root.querySelectorAll('[data-focus-key]')].find(el=>el.dataset.focusKey===focusKey)?.focus({preventScroll:true});
  }
  _selectItem(item,index) {
    this._selected=this._identity(item);
    for (const row of this._els.list.querySelectorAll('.parking-row')) row.classList.toggle('selected',row.dataset.key===this._selected);
    for (const marker of this._markers) if (marker._itemKey) marker.getElement().classList.toggle('active',marker._itemKey===this._selected);
    if (!this._map || !this._mapReady) return;
    const lat=this._n(item.latitude),lon=this._n(item.longitude); if (lat===null || lon===null) return;
    this._map.easeTo({center:[lon,lat],zoom:Math.max(this._map.getZoom(),15),duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:250});
    this._markers.find(marker=>marker._osmSuggestionIndex===index)?.togglePopup();
  }
  _message(text,failed=false) {
    this._q('.map-message').hidden=!text; this._q('.map-message span').textContent=text || '';
    this._q('.retry-map').hidden=!failed;
  }
  async _ensureCompactMap() {
    if (!this._canMap || !this.isConnected || this._mapIssue) return;
    if (this._map) return;
    if (this._mapPromise) return this._mapPromise;
    const generation=this._generation;
    this._message(this._u('mapLoading'));
    this._mapPromise=(async () => {
      try {
        const timeout=new Promise((_,reject)=>{ this._mapTimer=setTimeout(()=>reject(new Error('Map dependency timeout')),12000); });
        await Promise.race([this._ensureMapLibre(),timeout]); clearTimeout(this._mapTimer);
        if (generation!==this._generation || !this.isConnected || !this._canMap) return;
        const a=this._stateObj?.attributes || {}, maplib=window.maplibregl;
        const map=new maplib.Map({container:this._els.map,style:this._styleUrl(),center:[Number(a.destination_longitude),Number(a.destination_latitude)],zoom:14,attributionControl:true,cooperativeGestures:true});
        this._map=map; this._mapStyle=this._styleUrl();
        const ready=()=> {
          if (this._map!==map) return;
          clearTimeout(this._mapTimer); this._mapIssue=false; this._mapReady=true; this._message('');
          this._syncZones(); this._syncMarkers(); this._applyMapStyle();
        };
        map.on('style.load',ready);
        map.on('error',()=>{ if (!this._mapReady && this._map===map) this._mapFailure(); });
        this._bindZoneClicks(map);
        this._mapTimer=setTimeout(()=>{ if (!this._mapReady && this._map===map) this._mapFailure(); },12000);
        if (map.isStyleLoaded()) ready();
      } catch (_) { if (generation===this._generation) { if (!window.maplibregl) window.__osmParkingMapLibrePromise=null; this._mapFailure(); } }
    })().finally(()=>{ if (generation===this._generation) this._mapPromise=null; });
    return this._mapPromise;
  }
  _mapFailure() { clearTimeout(this._mapTimer); this._mapIssue=true; this._mapReady=false; this._message(this._u('mapFailed'),true); }
  _applyMapStyle() {
    if (!this._map || this._mapIssue) return;
    const target=this._styleUrl(); if (target===this._mapStyle) return;
    this._mapStyle=target; this._mapReady=false; this._message(this._u('mapLoading'));
    clearTimeout(this._mapTimer); this._mapTimer=setTimeout(()=>this._mapFailure(),12000);
    try { this._map.setStyle(target); } catch (_) { this._mapFailure(); }
  }
  _syncMarkers() {
    if (!this._canMap || !this._map || !this._mapReady) return;
    this._clearMarkers(); const maplib=window.maplibregl;
    const a=this._stateObj?.attributes || {};
    const marker=(item,index,destination=false)=> {
      const lat=this._n(item.latitude),lon=this._n(item.longitude);
      if (lat===null || lon===null || Math.abs(lat)>90 || Math.abs(lon)>180) return;
      const element=document.createElement('button'); element.type='button';
      element.className=destination?'osm-dest-marker':'osm-park-marker'; element.textContent=destination?'★':String(index+1);
      element.setAttribute('aria-label',destination?`${this._t('destination')}: ${item.name}`:`${index+1}. ${item.name}`);
      const popup=new maplib.Popup({offset:20,maxWidth:'260px'}).setHTML(destination?`<div class="popup-title">${this._esc(item.name)}</div>`:this._popupHtml(item,index));
      const m=new maplib.Marker({element}).setLngLat([lon,lat]).setPopup(popup).addTo(this._map);
      m._osmSuggestionIndex=destination?-1:index;
      if (!destination) {
        m._itemKey=this._identity(item); element.classList.toggle('active',m._itemKey===this._selected);
        element.addEventListener('click',()=> { this._selected=m._itemKey; for (const row of this._els.list.querySelectorAll('.parking-row')) row.classList.toggle('selected',row.dataset.key===this._selected); for (const other of this._markers) if (other._itemKey) other.getElement().classList.toggle('active',other._itemKey===this._selected); });
      }
      this._markers.push(m);
    };
    if (this.config.show_destination!==false) marker({latitude:a.destination_latitude,longitude:a.destination_longitude,name:a.destination_name || this._t('destination')},-1,true);
    this._view.forEach((item,index)=>marker(item,index));
    if (this._fitPending) { this._fitPending=false; this._fitMap(); }
  }
  _fitMap() {
    if (!this._map || !this._mapReady) { this._fitPending=true; return; }
    const bounds=new window.maplibregl.LngLatBounds();
    const a=this._stateObj?.attributes || {};
    const extend=(lat,lon)=>{ lat=this._n(lat);lon=this._n(lon);if(lat!==null && lon!==null && Math.abs(lat)<=90 && Math.abs(lon)<=180) bounds.extend([lon,lat]); };
    extend(a.destination_latitude,a.destination_longitude);
    this._view.forEach(item=>extend(item.latitude,item.longitude));
    if (!bounds.isEmpty()) this._map.fitBounds(bounds,{padding:{top:66,right:40,bottom:36,left:40},maxZoom:15.5,duration:0});
  }
  _syncZones() {
    if (!this._map?.isStyleLoaded()) return;
    const id='osm-parking-controlled-zones';
    const features=(this.config.show_zones!==false?this._zones:[]).filter(zone=>zone?.type==='Feature' && ['Polygon','MultiPolygon'].includes(zone.geometry?.type) && zone.properties?.record_type==='zone');
    const data={type:'FeatureCollection',features}; const source=this._map.getSource(id);
    if (source) { source.setData(data); return; } if (!features.length) return;
    this._map.addSource(id,{type:'geojson',data});
    this._map.addLayer({id:`${id}-fill`,type:'fill',source:id,paint:{'fill-color':'#d39d45','fill-opacity':0.17}});
    this._map.addLayer({id:`${id}-border`,type:'line',source:id,paint:{'line-color':'#d39d45','line-width':1.5}});
  }
  _bindZoneClicks(map) {
    map.on('click','osm-parking-controlled-zones-fill',event=> {
      const p=event.features?.[0]?.properties;if(!p)return;
      new window.maplibregl.Popup({maxWidth:'260px'}).setLngLat(event.lngLat).setHTML(`<div class="popup-title">${this._esc(p.name || this._zt('zone'))}</div><div class="popup-line">${this._esc(this._zt('signage'))}</div>`).addTo(map);
    });
  }
}

const OSM_PARKING_COMPACT_CSS = `
:host{display:block;min-width:0;--ui-bg:var(--ha-card-background,var(--card-background-color,#fff));--ui-panel:var(--secondary-background-color,#f4f6f7);--ui-text:var(--primary-text-color,#17242d);--ui-muted:var(--secondary-text-color,#667781);--ui-line:var(--divider-color,#dfe5e7);--ui-accent:#087e73;--ui-chip:#e7f5f0;color:var(--ui-text);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);container-type:inline-size}
:host([data-dark="true"]){--ui-accent:#69dfc4;--ui-chip:#183d37}
*{box-sizing:border-box} [hidden]{display:none!important} ha-card{display:block;border:1px solid var(--ui-line);border-radius:var(--ha-card-border-radius,20px);background:var(--ui-bg);overflow:hidden;box-shadow:var(--ha-card-box-shadow,0 3px 18px #00000006)}
button,input,select{font:inherit;color:inherit}button,a,select,input,summary{-webkit-tap-highlight-color:transparent}button,select,summary{cursor:pointer}button{border:0}button:disabled{opacity:.5;cursor:default}a{color:var(--ui-accent);text-decoration:none}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--ui-accent);outline-offset:3px}button svg, label svg{flex-shrink:0}button{background:transparent} .header{display:flex;gap:12px;align-items:center;padding:19px 18px 16px}.brand{width:39px;height:39px;flex-shrink:0;display:grid;place-items:center;border-radius:12px;font-size:22px;font-weight:750;background:var(--ui-chip);color:var(--ui-accent)}.headtext{flex:1;min-width:0}.title{font-size:17px;line-height:1.3;font-weight:650;letter-spacing:-.25px;margin:0;overflow-wrap:anywhere}.subtitle{font-size:12px;line-height:1.5;color:var(--ui-muted);margin:3px 0 0;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.icon-button{display:grid;place-items:center;width:40px;height:40px;flex-shrink:0;color:var(--ui-muted);border-radius:12px}.icon-button:hover{background:var(--ui-panel)}
.map-section{position:relative;isolation:isolate;margin:0 12px;border-radius:13px;overflow:hidden;border:1px solid var(--ui-line)}.map{width:100%;position:relative;overflow:hidden;contain:layout paint;background:var(--ui-panel);isolation:isolate}.map-controls{position:absolute;top:10px;right:10px;display:flex;gap:5px;z-index:5}.map-button,.theme-wrap{background:var(--ui-bg);border:1px solid var(--ui-line);box-shadow:0 2px 8px #0002;border-radius:9px;min-width:34px;height:34px;display:flex;align-items:center;justify-content:center;gap:3px;color:var(--ui-text)}.theme-wrap{padding:0 4px 0 7px}.theme-wrap svg{width:15px}.theme{font-size:11px;border:0;background:transparent;max-width:94px;min-height:30px;padding:0 2px}.theme option,select option{color:var(--ui-text);background:var(--ui-bg)}.map-message{position:absolute;inset:52px 14px 28px;z-index:6;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;border-radius:10px;background:var(--ui-bg);color:var(--ui-muted);padding:16px;text-align:center;font-size:13px;line-height:1.5}.retry-map{min-height:40px;background:var(--ui-chip);color:var(--ui-accent);border-radius:9px;padding:8px 16px;font-weight:600}
.results-section{padding:16px 16px 4px}.toolbar{display:flex;gap:8px}.search-wrap{flex:1;min-width:0;display:flex;align-items:center;gap:7px;border:1px solid var(--ui-line);border-radius:11px;padding:0 10px;min-height:42px;color:var(--ui-muted);background:var(--ui-bg)}.search-wrap svg{width:17px}.search{border:0;outline:0!important;width:100%;min-width:0;font-size:13px;background:transparent;color:var(--ui-text);min-height:40px}.search-wrap:focus-within{outline:2px solid var(--ui-accent);outline-offset:1px}.search::placeholder{color:var(--ui-muted)}.filter-button{display:flex;align-items:center;gap:6px;border:1px solid var(--ui-line);border-radius:11px;padding:0 10px;min-height:42px;font-size:12px;font-weight:600;flex-shrink:0}.filter-button[aria-expanded="true"]{border-color:var(--ui-accent);background:var(--ui-chip);color:var(--ui-accent)}.filter-count{min-width:18px;height:18px;display:grid;place-items:center;background:var(--ui-accent);color:var(--ui-bg);border-radius:5px;font-size:10px}.filter-panel{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px 0 2px}.filter-panel label{display:flex;flex-direction:column;gap:5px;min-width:0;color:var(--ui-muted);font-size:11px}.filter-panel select{width:100%;min-height:40px;border:1px solid var(--ui-line);border-radius:8px;background:var(--ui-bg);padding:0 8px;color:var(--ui-text);font-size:12px}.results-bar{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 0 10px;flex-wrap:wrap}.result-count{font-size:11px;color:var(--ui-muted)}.result-tools{display:flex;align-items:center;gap:9px;margin-left:auto}.sort-wrap{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--ui-muted)}.sort{min-height:32px;font-size:11px;border:0;background:transparent;max-width:155px;color:var(--ui-text);padding:0 3px}.clear{min-height:32px;font-size:11px;padding:0 5px;color:var(--ui-accent)}
.list{display:grid;gap:8px}.parking-row{border:1px solid var(--ui-line);border-radius:13px;padding:11px 12px 8px;background:var(--ui-bg);min-width:0}.parking-row.selected{border-color:var(--ui-accent);box-shadow:inset 3px 0 var(--ui-accent)}.row-main{display:flex;align-items:flex-start;gap:10px}.row-select{display:flex;align-items:center;gap:11px;min-height:44px;min-width:0;flex:1;text-align:left;padding:0;color:var(--ui-text)}.number{width:30px;height:32px;flex-shrink:0;border-radius:9px;display:grid;place-items:center;font-weight:700;font-size:13px;background:var(--ui-panel);color:var(--ui-text)}.row-body{display:block;min-width:0}.row-title{display:block;font-size:14px;font-weight:600;line-height:1.4;overflow-wrap:anywhere}.row-meta{display:flex;flex-wrap:wrap;align-items:baseline;gap:5px;color:var(--ui-muted);font-size:11px;line-height:1.5;margin-top:3px}.row-meta strong{font-weight:650;color:var(--ui-text);white-space:nowrap}.row-right{display:flex;align-items:center;gap:9px;max-width:42%;min-width:0;flex-shrink:0}.row-price{font-size:11px;font-weight:600;max-width:135px;overflow-wrap:anywhere;line-height:1.5;text-align:right}.row-price.free{color:var(--ui-accent)}.navigate{display:grid;place-items:center;width:36px;height:38px;flex-shrink:0;border-radius:10px;background:var(--ui-chip);color:var(--ui-accent)}.row-bottom{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding-top:7px;padding-left:41px;flex-wrap:wrap}.data-chip{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:500;line-height:1.5;max-width:100%;color:var(--ui-muted)}.data-dot{height:5px;width:5px;flex-shrink:0;border-radius:50%;background:currentColor}.data-chip.live{color:var(--ui-accent)}.data-chip.reported,.data-chip.estimated,.data-chip.predicted{color:#98651c}:host([data-dark="true"]) .data-chip.reported,:host([data-dark="true"]) .data-chip.estimated,:host([data-dark="true"]) .data-chip.predicted{color:#e8b969}.row-bottom details{margin-left:auto;font-size:11px;color:var(--ui-muted);min-width:0;max-width:100%}.row-bottom details[open]{flex-basis:100%}.row-bottom summary{min-height:24px;text-align:right;list-style:none}.row-bottom summary::after{content:'⌄';padding-left:6px}.detail-content{font-size:11px;line-height:1.8;text-align:left;color:var(--ui-muted);overflow-wrap:anywhere;border-top:1px solid var(--ui-line);margin-top:7px;padding-top:8px}.detail-content strong{font-weight:550}.detail-links{display:flex;gap:15px;margin-top:5px}.detail-links a{display:inline-flex;align-items:center;min-height:28px}.empty{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:var(--ui-muted);font-size:13px;text-align:center;line-height:1.5;padding:28px 12px}.reset{min-height:40px;padding:9px 15px;background:var(--ui-chip);color:var(--ui-accent);border-radius:10px}footer{font-size:10px;color:var(--ui-muted);padding:12px 18px 14px;display:flex;flex-wrap:wrap;gap:8px;opacity:.9}.zone-note{flex-basis:100%;line-height:1.5}
.status-panel{margin:0 16px 14px;padding:12px;border-radius:11px;border:1px solid var(--ui-line);background:var(--ui-panel);font-size:12px}.status-head{display:flex;align-items:flex-start;gap:9px}.status-icon{--mdc-icon-size:22px}.status-title{font-weight:650}.status-message{line-height:1.6;color:var(--ui-muted);margin-top:4px}.status-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.status-button{min-height:36px;border:1px solid var(--ui-line);border-radius:8px;padding:5px 10px}.status-button.primary{color:var(--ui-accent);background:var(--ui-chip);border-color:transparent}.status-details{margin-top:8px}.status-details summary{min-height:28px}.status-details pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}.status-panel.error{border-color:var(--error-color,#d46262)}
/* MapLibre structural CSS stays inside this card's shadow root. */
.map.maplibregl-map{overflow:hidden;-webkit-tap-highlight-color:transparent}.maplibregl-canvas-container{position:absolute;inset:0}.maplibregl-canvas{position:absolute;left:0;top:0;display:block;outline:none}.maplibregl-marker{position:absolute;left:0;top:0;will-change:transform;z-index:2}.osm-dest-marker,.osm-park-marker{width:30px;height:32px;border:2px solid var(--ui-bg);border-radius:9px;display:grid;place-items:center;padding:0;background:#1b786a;color:white;box-shadow:0 2px 7px #0004;font-size:12px;font-weight:750}.osm-dest-marker{background:#a75035;border-radius:50%;width:33px;height:33px}.osm-park-marker.active{background:#103d37;box-shadow:0 0 0 3px #59ceb280}.maplibregl-popup{position:absolute;top:0;left:0;display:flex;will-change:transform;pointer-events:none;z-index:7}.maplibregl-popup-content{pointer-events:auto;position:relative;background:var(--ui-bg);color:var(--ui-text);border-radius:10px;padding:13px;box-shadow:0 3px 20px #0003;font-size:12px}.maplibregl-popup-close-button{position:absolute;right:1px;top:1px;width:25px;height:25px;padding:0;border:0;background:transparent;font-size:18px}.popup-title{font-weight:650;padding-right:18px;margin-bottom:6px}.popup-line{line-height:1.6;color:var(--ui-muted)}.popup-actions{margin-top:6px}.popup-actions a{display:inline-block;min-height:28px;padding-top:5px}.maplibregl-popup-anchor-bottom,.maplibregl-popup-anchor-bottom-left,.maplibregl-popup-anchor-bottom-right{flex-direction:column-reverse}.maplibregl-popup-anchor-top,.maplibregl-popup-anchor-top-left,.maplibregl-popup-anchor-top-right{flex-direction:column}.maplibregl-popup-tip{display:none}.maplibregl-control-container{position:absolute;inset:0;pointer-events:none;z-index:4}.maplibregl-ctrl-top-left,.maplibregl-ctrl-top-right,.maplibregl-ctrl-bottom-left,.maplibregl-ctrl-bottom-right{position:absolute;pointer-events:none;z-index:4}.maplibregl-ctrl-bottom-right{bottom:0;right:0}.maplibregl-ctrl-bottom-left{bottom:0;left:0}.maplibregl-ctrl-top-right{top:0;right:0}.maplibregl-ctrl-top-left{top:0;left:0}.maplibregl-ctrl{pointer-events:auto;clear:both;margin:4px}.maplibregl-ctrl-attrib{font-size:9px;line-height:1.4;padding:3px 5px;background:var(--ui-bg);color:var(--ui-text);border-radius:4px;max-width:100%}.maplibregl-ctrl-attrib-inner a{color:inherit}.maplibregl-ctrl-attrib-button{display:none}.maplibregl-ctrl-logo{display:none}.maplibregl-cooperative-gesture-screen{position:absolute;inset:0;background:#0008;color:white;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;text-align:center}.maplibregl-cooperative-gesture-screen-show{opacity:1}
@container (max-width:380px){.header{padding:15px 12px 12px;gap:9px}.title{font-size:15px}.subtitle{font-size:11px}.results-section{padding:12px 10px 3px}.parking-row{padding:9px 9px 6px}.row-select{gap:8px}.row-title{font-size:13px}.row-meta{font-size:10px}.row-right{max-width:36%;gap:5px}.row-price{font-size:10px;max-width:76px}.navigate{width:31px;height:38px}.row-bottom{padding-left:38px}.filter-button{padding:0 8px}.map-section{margin:0 8px}.theme{max-width:80px}.sort{max-width:145px}.sort-wrap span{max-width:70px}.map-controls{top:7px;right:7px}.brand{width:34px;height:34px;font-size:20px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
`;

class OsmParkingCompactEditor extends HTMLElement {
  setConfig(config) { this._config={...config}; this._render(); }
  set hass(hass) { const changed=this._hass?.language!==hass?.language; this._hass=hass; if (!this._rendered || changed) this._render(); }
  _render() {
    if (!this._config) return; if (!this.shadowRoot) this.attachShadow({mode:'open'});
    const u=k=>osmUiText(this._hass?.language,k);
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const lang=this._hass?.language || 'en', dict=typeof OSM_PARKING_I18N!=='undefined'?(OSM_PARKING_I18N[lang]||OSM_PARKING_I18N.en):{};
    this.shadowRoot.innerHTML=`<style>:host{display:block;color:var(--primary-text-color);font:14px Roboto,Arial,sans-serif}label{display:grid;gap:7px;margin:14px 0}input,select{font:inherit;color:inherit;background:var(--card-background-color);min-height:44px;padding:8px;border:1px solid var(--divider-color);border-radius:9px;width:100%;box-sizing:border-box}</style><label>${esc(u('entity'))}<input name="entity" value="${esc(this._config.entity)}"></label><label>${esc(u('title'))}<input name="title" value="${esc(this._config.title||'')}"></label><label>${esc(u('mapHeight'))}<input name="map_height" type="number" min="180" max="600" step="10" value="${Number(this._config.map_height??this._config.height)||250}"></label><label>${esc(u('theme'))}<select name="map_theme">${['auto','light','dark'].map(k=>`<option value="${k}" ${k===(this._config.map_theme||'auto')?'selected':''}>${esc(u(k))}</option>`).join('')}</select></label>`;
    this._rendered=true;
    for(const input of this.shadowRoot.querySelectorAll('input,select')) input.addEventListener('change',()=>{
      const config={...this._config};
      if(input.name==='map_height'){const n=Number(input.value);if(!Number.isFinite(n)||n<180||n>600)return;config.map_height=n;}
      else config[input.name]=input.value;
      this._config=config; this.dispatchEvent(new CustomEvent('config-changed',{detail:{config},bubbles:true,composed:true}));
    });
  }
}
if (!customElements.get('osm-parking-compact-editor')) customElements.define('osm-parking-compact-editor',OsmParkingCompactEditor);
