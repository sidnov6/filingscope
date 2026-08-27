"use client";

import {
  geoGraticule10,
  geoNaturalEarth1,
  geoOrthographic,
  geoPath,
  type GeoProjection,
} from "d3-geo";
import type { FeatureCollection, Geometry } from "geojson";
import { useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import countriesTopology from "world-atlas/countries-110m.json";
import { StatusPanel } from "./StatusPanel";
import { useWorkspace } from "./WorkspaceProvider";

const MAP_WIDTH = 720;
const MAP_HEIGHT = 520;
const worldTopology = countriesTopology as unknown as Topology;
const countries = feature(
  worldTopology,
  worldTopology.objects.countries,
) as FeatureCollection<Geometry>;

function createProjection(
  kind: "globe" | "mercator",
  longitude: number,
  latitude: number,
  zoom: number,
): GeoProjection {
  if (kind === "globe") {
    return geoOrthographic()
      .translate([MAP_WIDTH / 2, MAP_HEIGHT / 2])
      .scale(225 * zoom)
      .clipAngle(90)
      .rotate([-longitude, -latitude]);
  }
  const projection = geoNaturalEarth1().fitExtent(
    [
      [18, 18],
      [MAP_WIDTH - 18, MAP_HEIGHT - 18],
    ],
    countries,
  );
  projection.scale(projection.scale() * zoom);
  return projection;
}

export function GeographyMap() {
  const { data } = useWorkspace();
  const [projectionKind, setProjectionKind] = useState<"globe" | "mercator">("globe");
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState(data.geography.locations[0]?.id);
  const selectedLocation =
    data.geography.locations.find((location) => location.id === selected) ??
    data.geography.locations[0];
  const focusLocation = selectedLocation ?? { longitude: 0, latitude: 20 };
  const projection = useMemo(
    () =>
      createProjection(
        projectionKind,
        focusLocation.longitude,
        focusLocation.latitude,
        zoom,
      ),
    [focusLocation.latitude, focusLocation.longitude, projectionKind, zoom],
  );
  const path = useMemo(() => geoPath(projection), [projection]);
  const markerPoint = selectedLocation
    ? projection([selectedLocation.longitude, selectedLocation.latitude])
    : null;

  function changeProjection(next: "globe" | "mercator") {
    setProjectionKind(next);
    setZoom(1);
  }

  return (
    <>
      <div className="map-toolbar" aria-label="Map display controls">
        <div>
          <button
            aria-pressed={projectionKind === "globe"}
            onClick={() => changeProjection("globe")}
          >
            Globe
          </button>
          <button
            aria-pressed={projectionKind === "mercator"}
            onClick={() => changeProjection("mercator")}
          >
            Flat map
          </button>
        </div>
        <span>
          {data.geography.locations.length} sourced location context
          {data.geography.locations.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="map-layout">
        <div
          className="world-map"
          role="application"
          aria-label={`Interactive world map for ${data.company.name}`}
        >
          <div className="map-zoom-controls" aria-label="Map zoom controls">
            <button
              aria-label="Zoom in"
              disabled={zoom >= 1.8}
              onClick={() => setZoom((current) => Math.min(1.8, current + 0.2))}
            >
              +
            </button>
            <button
              aria-label="Zoom out"
              disabled={zoom <= 0.8}
              onClick={() => setZoom((current) => Math.max(0.8, current - 0.2))}
            >
              −
            </button>
          </div>
          <svg viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}>
            <title>{`SEC-sourced registered-address map for ${data.company.name}`}</title>
            {projectionKind === "globe" ? (
              <circle
                className="map-ocean"
                cx={MAP_WIDTH / 2}
                cy={MAP_HEIGHT / 2}
                r={225 * zoom}
              />
            ) : (
              <rect className="map-ocean" width={MAP_WIDTH} height={MAP_HEIGHT} />
            )}
            <path className="map-graticule" d={path(geoGraticule10()) ?? undefined} />
            {countries.features.map((country, index) => (
              <path
                className="map-country"
                d={path(country) ?? undefined}
                key={String(country.id ?? index)}
              />
            ))}
            {markerPoint && selectedLocation ? (
              <g
                className="map-svg-marker"
                role="button"
                tabIndex={0}
                aria-label={selectedLocation.label}
                transform={`translate(${markerPoint[0]} ${markerPoint[1]})`}
                onClick={() => setSelected(selectedLocation.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    setSelected(selectedLocation.id);
                  }
                }}
              >
                <circle className="map-marker-ring" r="11" />
                <circle className="map-marker-core" r="6" />
                <title>{selectedLocation.label}</title>
              </g>
            ) : null}
          </svg>
        </div>
        <aside className="map-evidence" aria-label="Geographic evidence and limitations">
          <p className="eyebrow">Source-backed context</p>
          <h2>{selectedLocation?.label ?? "No geographic marker"}</h2>
          {selectedLocation ? (
            <>
              <p className="registered-address">{selectedLocation.address}</p>
              <dl>
                <div>
                  <dt>Display precision</dt>
                  <dd>Administrative-area centroid</dd>
                </div>
                <div>
                  <dt>Evidence role</dt>
                  <dd>Registered business address</dd>
                </div>
                <div>
                  <dt>Source hash</dt>
                  <dd className="mono">{selectedLocation.sourceHash.slice(0, 16)}…</dd>
                </div>
              </dl>
              <p className="map-limitation">{selectedLocation.limitation}</p>
              <a
                className="source-link"
                href={selectedLocation.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                Open SEC source
              </a>
            </>
          ) : (
            <p>
              Ingested SEC submissions do not contain a mappable registered-address context.
            </p>
          )}
        </aside>
      </div>
      {!data.geography.locations.length ? (
        <StatusPanel
          state="empty"
          title="No sourced map marker"
          detail="The map stays empty rather than inferring geographic exposure from company name, exchange, or filing text."
        />
      ) : null}
      <p className="map-notice">{data.geography.notice}</p>
    </>
  );
}
