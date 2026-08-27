"use client";

import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, Marker, StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import countriesTopology from "world-atlas/countries-110m.json";
import { StatusPanel } from "./StatusPanel";
import { useWorkspace } from "./WorkspaceProvider";

const worldTopology = countriesTopology as unknown as Topology;
const countries = feature(worldTopology, worldTopology.objects.countries);
const LOCAL_WORLD_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    countries: {
      type: "geojson",
      data: countries,
    },
  },
  layers: [
    {
      id: "ocean",
      type: "background",
      paint: { "background-color": "#dcecf1" },
    },
    {
      id: "land",
      type: "fill",
      source: "countries",
      paint: { "fill-color": "#f3efe4", "fill-opacity": 1 },
    },
    {
      id: "country-borders",
      type: "line",
      source: "countries",
      paint: { "line-color": "#8ba2aa", "line-opacity": 0.7, "line-width": 0.7 },
    },
  ],
};

export function GeographyMap() {
  const { data } = useWorkspace();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [projection, setProjection] = useState<"globe" | "mercator">("globe");
  const [selected, setSelected] = useState(data.geography.locations[0]?.id);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({ container: container.current, style: LOCAL_WORLD_STYLE, center: [-20, 22], zoom: 1.1, attributionControl: false });
    instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    instance.addControl(new maplibregl.FullscreenControl(), "top-right");
    instance.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    instance.on("load", () => instance.setProjection({ type: "globe" }));
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    markers.current.forEach((marker) => marker.remove());
    markers.current = [];
    if (!map.current) return;
    for (const location of data.geography.locations) {
      const element = document.createElement("button");
      element.className = "map-marker";
      element.type = "button";
      element.setAttribute("aria-label", location.label);
      element.addEventListener("click", () => setSelected(location.id));
      const popupContent = document.createElement("div");
      const popupTitle = document.createElement("strong");
      const popupAddress = document.createElement("p");
      const popupPrecision = document.createElement("small");
      popupTitle.textContent = location.label;
      popupAddress.textContent = location.address;
      popupPrecision.textContent = "Approximate state centroid";
      popupContent.append(popupTitle, popupAddress, popupPrecision);
      const popup = new maplibregl.Popup({ offset: 18 }).setDOMContent(popupContent);
      const marker = new maplibregl.Marker({ element }).setLngLat([location.longitude, location.latitude]).setPopup(popup).addTo(map.current);
      markers.current.push(marker);
    }
    const first = data.geography.locations[0];
    if (first) map.current.flyTo({ center: [first.longitude, first.latitude], zoom: 3.4, duration: 900 });
  }, [data.company.cik, data.geography.locations]);

  const selectedLocation = data.geography.locations.find((location) => location.id === selected) ?? data.geography.locations[0];
  function changeProjection(next: "globe" | "mercator") {
    setProjection(next);
    map.current?.setProjection({ type: next });
  }
  return (
    <>
      <div className="map-toolbar" aria-label="Map display controls"><div><button aria-pressed={projection === "globe"} onClick={() => changeProjection("globe")}>Globe</button><button aria-pressed={projection === "mercator"} onClick={() => changeProjection("mercator")}>Flat map</button></div><span>{data.geography.locations.length} sourced location context{data.geography.locations.length === 1 ? "" : "s"}</span></div>
      <div className="map-layout">
        <div ref={container} className="world-map" role="application" aria-label={`Interactive world map for ${data.company.name}`} />
        <aside className="map-evidence" aria-label="Geographic evidence and limitations">
          <p className="eyebrow">Source-backed context</p><h2>{selectedLocation?.label ?? "No geographic marker"}</h2>
          {selectedLocation ? <><p className="registered-address">{selectedLocation.address}</p><dl><div><dt>Display precision</dt><dd>Administrative-area centroid</dd></div><div><dt>Evidence role</dt><dd>Registered business address</dd></div><div><dt>Source hash</dt><dd className="mono">{selectedLocation.sourceHash.slice(0, 16)}…</dd></div></dl><p className="map-limitation">{selectedLocation.limitation}</p><a className="source-link" href={selectedLocation.sourceUrl} target="_blank" rel="noreferrer">Open SEC source</a></> : <p>Ingested SEC submissions do not contain a mappable registered-address context.</p>}
        </aside>
      </div>
      {!data.geography.locations.length ? <StatusPanel state="empty" title="No sourced map marker" detail="The map stays empty rather than inferring geographic exposure from company name, exchange, or filing text." /> : null}
      <p className="map-notice">{data.geography.notice}</p>
    </>
  );
}
