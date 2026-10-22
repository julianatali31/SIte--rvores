// Minimal polygon editor on top of Leaflet: click to add vertices, drag to move,
// click a vertex to remove it. No plugin, so no script load-order issues.
import { L, ZONE_STYLE } from '../basemap.js';

export class PolygonEditor {
  constructor(map, onChange = () => {}) {
    this.map = map;
    this.onChange = onChange;
    this.points = []; // [lat, lng]
    this.markers = [];
    this.drawing = false;
    this.shape = L.polygon([], { ...ZONE_STYLE, dashArray: '6 4' }).addTo(map);
    this.handleClick = (e) => this.add([e.latlng.lat, e.latlng.lng]);
  }

  setDrawing(on) {
    this.drawing = on;
    this.map.getContainer().classList.toggle('drawing', on);
    if (on) this.map.on('click', this.handleClick);
    else this.map.off('click', this.handleClick);
  }

  load(geometry) {
    this.points = [];
    if (geometry?.type === 'Polygon') {
      const ring = geometry.coordinates[0].slice(0, -1); // drop closing point
      this.points = ring.map(([lng, lat]) => [lat, lng]);
    }
    this.redraw();
  }

  add(point) {
    this.points.push(point);
    this.redraw();
  }

  undo() {
    this.points.pop();
    this.redraw();
  }

  clear() {
    this.points = [];
    this.redraw();
  }

  redraw() {
    this.markers.forEach((m) => m.remove());
    this.markers = this.points.map((pt, index) => {
      const marker = L.marker(pt, {
        draggable: true,
        icon: L.divIcon({ className: 'vertex', iconSize: [22, 22] }),
        title: 'Arraste para mover, clique para remover',
      }).addTo(this.map);
      marker.on('drag', (e) => {
        this.points[index] = [e.latlng.lat, e.latlng.lng];
        this.shape.setLatLngs(this.points);
      });
      marker.on('dragend', () => this.onChange(this));
      marker.on('click', () => {
        this.points.splice(index, 1);
        this.redraw();
      });
      return marker;
    });
    this.shape.setLatLngs(this.points);
    this.onChange(this);
  }

  isValid() {
    return this.points.length >= 3;
  }

  toGeoJSON() {
    if (!this.isValid()) return null;
    const ring = this.points.map(([lat, lng]) => [Number(lng.toFixed(7)), Number(lat.toFixed(7))]);
    ring.push([...ring[0]]);
    return { type: 'Polygon', coordinates: [ring] };
  }

  fit() {
    if (this.points.length) this.map.fitBounds(this.shape.getBounds(), { padding: [30, 30], maxZoom: 20 });
  }
}
