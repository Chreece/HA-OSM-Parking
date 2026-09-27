class OsmParkingMapCardV022 extends HTMLElement {
  static getStubConfig() {
    return { entity: 'sensor.parking_suggestions', height: 430, show_list: true };
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error('Please define an entity');
    this.config = {
      title: 'Parking suggestions',
      height: 430,
      show_list: true,
      show_destination: true,
      show_price: true,
      map_style: 'https://tiles.openfreemap.org/styles/liberty',
      ...config,
    };
    this._lastSignature = null;
    this._map = null;
    this._markers = [];
    this._renderShell();
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass?.states?.[this.config.entity];
    if (!state) {
      this._showError(`Entity not found: ${this.config.entity}`);
      return;
    }
    const a = state.attributes || {};
    const source = a.destination_entity ? hass?.states?.[a.destination_entity] : null;
    const signature = JSON.stringify({
      state: state.state,
      destination_name: a.destination_name,
      destination_latitude: a.destination_latitude,
      destination_longitude: a.destination_longitude,
      source_state: source?.state,
      source_display_name: source?.attributes?.display_name,
      source_lat: source?.attributes?.lat ?? source?.attributes?.latitude,
      source_lon: source?.attributes?.lon ?? source?.attributes?.longitude,
      suggestions: a.suggestions,
    });
    if (signature === this._lastSignature) return;
    this._lastSignature = signature;
    this._stateObj = state;
    void this._update();
  }

  getCardSize() {
    return 6;
  }

  _renderShell() {
    this.innerHTML = `
      <ha-card>
        <div class="header">
          <div>
            <div class="title"></div>
            <div class="subtitle"></div>
          </div>
          <div class="headright"><span class="version">v0.2.2</span><ha-icon icon="mdi:parking"></ha-icon></div>
        </div>
        <div class="error" hidden></div>
        <div class="map" style="height:${Number(this.config.height) || 430}px"></div>
        <div class="list" ${this.config.show_list === false ? 'hidden' : ''}></div>
      </ha-card>
      <style>
        ha-card { overflow:hidden; }
        .header { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:16px 16px 12px; }
        .title { font-size:1.15rem; font-weight:600; color:var(--primary-text-color); }
        .subtitle { margin-top:4px; color:var(--secondary-text-color); font-size:.9rem; line-height:1.35; }
        .headright { display:flex; align-items:center; gap:8px; }
        .version { font-size:.68rem; color:var(--secondary-text-color); opacity:.72; }
        .header ha-icon { color:var(--state-icon-color); --mdc-icon-size:28px; flex:0 0 auto; }
        .map {
          width:100%;
          position:relative;
          overflow:hidden;
          contain:layout paint;
          isolation:isolate;
          background:var(--secondary-background-color);
        }
        /*
         * MapLibre's CDN stylesheet lives outside Home Assistant's shadow-DOM
         * boundaries, so its structural positioning rules are not guaranteed to
         * reach a custom card. Keep the critical layout rules local to the card.
         */
        .map.maplibregl-map { position:relative; overflow:hidden; -webkit-tap-highlight-color:rgb(0 0 0 / 0%); }
        .map .maplibregl-canvas-container { position:absolute; inset:0; width:100%; height:100%; }
        .map .maplibregl-canvas { position:absolute; left:0; top:0; display:block; }
        .map .maplibregl-marker {
          position:absolute;
          left:0;
          top:0;
          will-change:transform;
          z-index:2;
        }
        .map .maplibregl-popup {
          position:absolute;
          left:0;
          top:0;
          display:flex;
          will-change:transform;
          pointer-events:none;
          z-index:3;
        }
        .map .maplibregl-popup-content { position:relative; pointer-events:auto; }
        .map .maplibregl-popup-close-button { position:absolute; right:0; top:0; border:0; background:transparent; cursor:pointer; }
        .map .maplibregl-control-container { position:absolute; inset:0; pointer-events:none; z-index:4; }
        .map .maplibregl-ctrl-top-left,
        .map .maplibregl-ctrl-top-right,
        .map .maplibregl-ctrl-bottom-left,
        .map .maplibregl-ctrl-bottom-right { position:absolute; pointer-events:none; z-index:4; }
        .map .maplibregl-ctrl-top-left { top:0; left:0; }
        .map .maplibregl-ctrl-top-right { top:0; right:0; }
        .map .maplibregl-ctrl-bottom-left { bottom:0; left:0; }
        .map .maplibregl-ctrl-bottom-right { right:0; bottom:0; }
        .map .maplibregl-ctrl { clear:both; pointer-events:auto; transform:translate(0); }
        .error { margin:0 16px 16px; padding:12px; color:var(--error-color); background:color-mix(in srgb,var(--error-color) 10%,transparent); border-radius:10px; }
        .list { padding:8px 12px 12px; display:grid; gap:8px; }
        .parking-row { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:10px; padding:10px; border-radius:12px; background:var(--secondary-background-color); cursor:pointer; }
        .parking-row:hover { filter:brightness(1.04); }
        .badge { min-width:34px; height:34px; border-radius:50%; display:grid; place-items:center; background:var(--primary-color); color:#fff; font-weight:700; }
        .row-title { font-weight:600; color:var(--primary-text-color); }
        .row-meta { margin-top:2px; color:var(--secondary-text-color); font-size:.84rem; }
        .row-price { font-weight:600; white-space:nowrap; color:var(--primary-text-color); }
        .osm-dest-marker,.osm-park-marker { width:32px; height:32px; border-radius:50%; display:grid; place-items:center; border:3px solid #fff; box-shadow:0 1px 5px rgba(0,0,0,.45); color:#fff; font-weight:800; box-sizing:border-box; }
        .osm-dest-marker { background:#d32f2f; }
        .osm-park-marker { background:#1976d2; }
        .maplibregl-popup-content { background:var(--card-background-color,#fff); color:var(--primary-text-color,#111); border-radius:10px; padding:12px 14px; min-width:190px; }
        .maplibregl-popup-tip { border-top-color:var(--card-background-color,#fff) !important; }
        .maplibregl-popup-close-button { color:var(--primary-text-color,#111); font-size:20px; }
        .popup-title { font-weight:700; margin-bottom:6px; padding-right:12px; }
        .popup-line { margin:3px 0; }
        .popup-actions { display:flex; gap:12px; margin-top:9px; }
        .popup-actions a { color:var(--primary-color); text-decoration:none; font-weight:600; }
      </style>`;
    this._els = {
      title: this.querySelector('.title'),
      subtitle: this.querySelector('.subtitle'),
      map: this.querySelector('.map'),
      list: this.querySelector('.list'),
      error: this.querySelector('.error'),
    };
  }

  _showError(message) {
    if (!this._els) this._renderShell();
    this._els.error.hidden = false;
    this._els.error.textContent = message;
  }

  _hideError() {
    if (this._els) this._els.error.hidden = true;
  }

  async _ensureMapLibre() {
    if (window.maplibregl) return;

    if (!document.querySelector('link[data-osm-parking-maplibre]')) {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.css';
      css.dataset.osmParkingMaplibre = '1';
      document.head.appendChild(css);
    }

    if (!window.__osmParkingMapLibrePromise) {
      window.__osmParkingMapLibrePromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.js';
        script.onload = resolve;
        script.onerror = () => reject(new Error('Could not load MapLibre GL JS'));
        document.head.appendChild(script);
      });
    }

    await window.__osmParkingMapLibrePromise;
  }

  _n(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  _esc(value) {
    return String(value ?? '').replace(
      /[&<>'"]/g,
      char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;',
      }[char]),
    );
  }

  _displayPrice(suggestion) {
    if (!this.config.show_price) return '';
    if (suggestion.price) return String(suggestion.price);
    if (suggestion.charge) return String(suggestion.charge);
    if (suggestion.pricing?.charge) return String(suggestion.pricing.charge);
    if (String(suggestion.fee).toLowerCase() === 'no') return 'Free';
    if (String(suggestion.fee).toLowerCase() === 'yes') return 'Paid';
    return '';
  }

  _labelType(suggestion) {
    return suggestion.category || suggestion.parking_type || 'parking';
  }

  _popupHtml(suggestion, index) {
    const price = this._displayPrice(suggestion);
    const distance = suggestion.distance_m != null
      ? `${Math.round(Number(suggestion.distance_m))} m`
      : '';
    const access = suggestion.access && suggestion.access !== 'unknown'
      ? suggestion.access
      : '';

    const lines = [
      distance && `<div class="popup-line">Distance: ${this._esc(distance)}</div>`,
      `<div class="popup-line">Type: ${this._esc(this._labelType(suggestion))}</div>`,
      price && `<div class="popup-line">Price: ${this._esc(price)}</div>`,
      access && `<div class="popup-line">Access: ${this._esc(access)}</div>`,
    ].filter(Boolean).join('');

    const actions = [
      suggestion.navigation_url && `<a href="${this._esc(suggestion.navigation_url)}" target="_blank" rel="noopener">Navigate</a>`,
      suggestion.osm_url && `<a href="${this._esc(suggestion.osm_url)}" target="_blank" rel="noopener">OSM</a>`,
    ].filter(Boolean).join('');

    return `<div class="popup-title">${this._esc(suggestion.name || `Parking ${index + 1}`)}</div>${lines}${actions ? `<div class="popup-actions">${actions}</div>` : ''}`;
  }

  _clearMarkers() {
    for (const marker of this._markers) marker.remove();
    this._markers = [];
  }

  async _update() {
    this._hideError();

    const attributes = this._stateObj?.attributes || {};
    const source = attributes.destination_entity
      ? this._hass?.states?.[attributes.destination_entity]
      : null;
    const sourceState = String(source?.state ?? '').trim();
    const sourceUsable = sourceState
      && !['unknown', 'unavailable', 'none', 'null'].includes(sourceState.toLowerCase());
    const sourceDisplayName = String(source?.attributes?.display_name ?? '').trim();
    const sourceLat = this._n(source?.attributes?.lat ?? source?.attributes?.latitude);
    const sourceLon = this._n(source?.attributes?.lon ?? source?.attributes?.longitude);
    const destinationLat = sourceLat ?? this._n(attributes.destination_latitude);
    const destinationLon = sourceLon ?? this._n(attributes.destination_longitude);
    const destinationName = sourceDisplayName
      || (sourceUsable ? sourceState : '')
      || attributes.destination_name
      || attributes.destination_entity
      || 'Destination';
    const suggestions = Array.isArray(attributes.suggestions)
      ? attributes.suggestions
      : [];

    this._els.title.textContent = this.config.title || 'Parking suggestions';
    const subtitle = [];
    if (destinationName) subtitle.push(String(destinationName));
    if (suggestions.length) {
      subtitle.push(
        `${suggestions.length} suggestion${suggestions.length === 1 ? '' : 's'}`,
      );
    } else if (this._stateObj?.state === 'stale') {
      subtitle.push('using last known results');
    } else {
      subtitle.push('no suggestions returned');
    }
    this._els.subtitle.textContent = subtitle.join(' · ');

    if (destinationLat == null || destinationLon == null) {
      this._showError('Destination coordinates are missing from the entity attributes.');
      return;
    }

    try {
      await this._ensureMapLibre();
    } catch (error) {
      this._showError(error.message);
      return;
    }

    if (!this._map) {
      this._map = new maplibregl.Map({
        container: this._els.map,
        style: this.config.map_style,
        center: [destinationLon, destinationLat],
        zoom: 15,
        attributionControl: true,
      });
      this._map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        'top-right',
      );

      await new Promise((resolve, reject) => {
        if (this._map.loaded()) {
          resolve();
          return;
        }
        this._map.once('load', resolve);
        this._map.once(
          'error',
          event => reject(event?.error || new Error('Map failed to load')),
        );
      });
    }

    this._clearMarkers();
    const bounds = new maplibregl.LngLatBounds();

    if (this.config.show_destination !== false) {
      const element = document.createElement('div');
      element.className = 'osm-dest-marker';
      element.textContent = '★';

      const popup = new maplibregl.Popup({ offset: 18 }).setHTML(
        `<div class="popup-title">${this._esc(destinationName)}</div><div class="popup-line">Destination</div>`,
      );
      const marker = new maplibregl.Marker({ element })
        .setLngLat([destinationLon, destinationLat])
        .setPopup(popup)
        .addTo(this._map);
      this._markers.push(marker);
      bounds.extend([destinationLon, destinationLat]);
    }

    suggestions.forEach((suggestion, index) => {
      const lat = this._n(suggestion.latitude);
      const lon = this._n(suggestion.longitude);
      if (lat == null || lon == null) return;

      const element = document.createElement('div');
      element.className = 'osm-park-marker';
      element.textContent = String(index + 1);

      const popup = new maplibregl.Popup({ offset: 18 })
        .setHTML(this._popupHtml(suggestion, index));
      const marker = new maplibregl.Marker({ element })
        .setLngLat([lon, lat])
        .setPopup(popup)
        .addTo(this._map);
      marker._osmSuggestionIndex = index;
      this._markers.push(marker);
      bounds.extend([lon, lat]);
    });

    if (!bounds.isEmpty()) {
      const southWest = bounds.getSouthWest();
      const northEast = bounds.getNorthEast();
      if (
        southWest.lng === northEast.lng
        && southWest.lat === northEast.lat
      ) {
        this._map.jumpTo({
          center: [destinationLon, destinationLat],
          zoom: 16,
        });
      } else {
        this._map.fitBounds(bounds, {
          padding: 40,
          maxZoom: 17,
          duration: 0,
        });
      }
    }

    setTimeout(() => this._map?.resize(), 0);
    this._renderList(suggestions);
  }

  _renderList(suggestions) {
    if (this.config.show_list === false) return;

    this._els.list.innerHTML = '';

    suggestions.forEach((suggestion, index) => {
      const row = document.createElement('div');
      row.className = 'parking-row';

      const price = this._displayPrice(suggestion);
      const distance = suggestion.distance_m != null
        ? `${Math.round(Number(suggestion.distance_m))} m`
        : '';
      const type = this._labelType(suggestion);

      row.innerHTML = `
        <div class="badge">${index + 1}</div>
        <div>
          <div class="row-title">${this._esc(suggestion.name || `Parking ${index + 1}`)}</div>
          <div class="row-meta">${this._esc([distance, type].filter(Boolean).join(' · '))}</div>
        </div>
        <div class="row-price">${this._esc(price)}</div>
      `;

      row.addEventListener('click', () => {
        const lat = this._n(suggestion.latitude);
        const lon = this._n(suggestion.longitude);
        if (lat == null || lon == null || !this._map) return;

        this._map.easeTo({
          center: [lon, lat],
          zoom: Math.max(this._map.getZoom(), 17),
          duration: 350,
        });
        const marker = this._markers.find(
          candidate => candidate._osmSuggestionIndex === index,
        );
        marker?.togglePopup();
        this._els.map.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      });

      this._els.list.appendChild(row);
    });
  }
}

if (!customElements.get('osm-parking-map-card')) {
  customElements.define('osm-parking-map-card', OsmParkingMapCardV022);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'osm-parking-map-card',
    name: 'OSM Parking Map Card',
    description: 'Destination and OSM parking suggestions on OpenFreeMap.',
    preview: true,
  });
}
