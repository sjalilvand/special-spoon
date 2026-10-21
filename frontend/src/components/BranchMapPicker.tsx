// فاز ۴۹: نقشه انتخاب موقعیت شعبه — Leaflet/OSM (بدون کلید، مانند B40)
// کلیک روی نقشه یا کشیدن نشانگر، مختصات را برمی‌گرداند؛ مختصات ورودی
// موقعیت اولیه نشانگر است.
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIconPng from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { Box, Button, Stack, Typography } from "@mui/material";
import { useEffect, useRef } from "react";

const defaultIcon = L.icon({
  iconUrl: markerIconPng,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

const IRAN_CENTER: L.LatLngTuple = [35.715, 51.404];
const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIB = "© OpenStreetMap contributors";

export default function BranchMapPicker({
  lat, lng, onChange, height = 300,
}: {
  lat: number | null;
  lng: number | null;
  onChange: (lat: number | null, lng: number | null) => void;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  // ساخت نقشه یک‌بار (مقاوم به StrictMode)
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: IRAN_CENTER,
      zoom: 5,
      scrollWheelZoom: true,
    });
    L.tileLayer(TILE_URL, { attribution: ATTRIB, maxZoom: 19 }).addTo(map);
    map.on("click", (e: L.LeafletMouseEvent) => {
      onChange(Math.round(e.latlng.lat * 1e6) / 1e6, Math.round(e.latlng.lng * 1e6) / 1e6);
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // همگام‌سازی نشانگر با مختصات (فیلد دستی یا انتخاب استان یا کلیک نقشه)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (lat === null || lng === null) {
      if (markerRef.current) {
        map.removeLayer(markerRef.current);
        markerRef.current = null;
      }
      return;
    }
    const pos: L.LatLngTuple = [lat, lng];
    if (markerRef.current) {
      markerRef.current.setLatLng(pos);
    } else {
      const m = L.marker(pos, { draggable: true }).addTo(map);
      m.on("dragend", () => {
        const p = m.getLatLng();
        onChange(Math.round(p.lat * 1e6) / 1e6, Math.round(p.lng * 1e6) / 1e6);
      });
      markerRef.current = m;
    }
    map.setView(pos, Math.max(map.getZoom(), 10));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng]);

  return (
    <Box sx={{ width: "100%", minWidth: 0 }}>
      <Stack direction="row" alignItems="center" spacing={1} mb={0.75} flexWrap="wrap" useFlexGap>
        <Typography variant="caption" color="text.secondary">
          موقعیت روی نقشه — کلیک روی نقشه یا کشیدن نشانگر
        </Typography>
        <Box flexGrow={1} />
        <Button size="small" onClick={() => onChange(null, null)}>حذف مختصات</Button>
      </Stack>
      <Box
        ref={containerRef}
        sx={{
          height,
          width: "100%",
          maxWidth: "100%",
          borderRadius: 2,
          overflow: "hidden",
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "#eef3f8",
        }}
      />
    </Box>
  );
}
