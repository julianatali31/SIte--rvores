"""Validation for zone polygons drawn in the admin or imported as GeoJSON."""
from typing import Any


class GeoJSONError(ValueError):
    pass


def _check_position(pos: Any) -> None:
    if not isinstance(pos, list | tuple) or len(pos) < 2:
        raise GeoJSONError("Cada ponto precisa ser [longitude, latitude].")
    lng, lat = pos[0], pos[1]
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in (lng, lat)):
        raise GeoJSONError("Coordenadas precisam ser números.")
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        raise GeoJSONError("Coordenada fora do intervalo válido (longitude, latitude).")


def _check_polygon(rings: Any) -> None:
    if not isinstance(rings, list) or not rings:
        raise GeoJSONError("Polígono sem anéis.")
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 4:
            raise GeoJSONError("Cada anel do polígono precisa de pelo menos 3 pontos distintos.")
        for pos in ring:
            _check_position(pos)
        if list(ring[0][:2]) != list(ring[-1][:2]):
            raise GeoJSONError("O polígono precisa ser fechado (último ponto igual ao primeiro).")


def extract_geometry(data: Any) -> dict[str, Any]:
    """Accepts a geometry, a Feature, or a FeatureCollection with exactly one feature.

    Returns a clean Polygon/MultiPolygon geometry (2D positions only).
    """
    if not isinstance(data, dict):
        raise GeoJSONError("GeoJSON inválido.")
    kind = data.get("type")
    if kind == "FeatureCollection":
        features = data.get("features") or []
        if len(features) != 1:
            raise GeoJSONError("O arquivo precisa ter exatamente um polígono (encontrado: %d)." % len(features))
        return extract_geometry(features[0])
    if kind == "Feature":
        return extract_geometry(data.get("geometry"))

    coords = data.get("coordinates")
    if kind == "Polygon":
        _check_polygon(coords)
        return {"type": "Polygon", "coordinates": [[list(p[:2]) for p in r] for r in coords]}
    if kind == "MultiPolygon":
        if not isinstance(coords, list) or not coords:
            raise GeoJSONError("MultiPolygon vazio.")
        for poly in coords:
            _check_polygon(poly)
        return {
            "type": "MultiPolygon",
            "coordinates": [[[list(p[:2]) for p in r] for r in poly] for poly in coords],
        }
    raise GeoJSONError(f"Tipo de geometria não suportado: {kind!r}. Use Polygon ou MultiPolygon.")
