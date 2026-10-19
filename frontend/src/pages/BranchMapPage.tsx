// فاز ۳۲ - B40 سند جامع: نقشه شعب + تصمیم D03 (سرویس نقشه پلاگین‌پذیر)
// پیش‌فرض OSM/Leaflet بدون کلید؛ برای نشنال/Map.ir در تولید از SDK رسمی
// استفاده می‌شود (کلید هرگز به کلاینت ارسال نمی‌شود).
// پذیرش سند: «مکان کاربر فقط برای مرتب‌سازی، ذخیره نمی‌شود» — مختصات
// مرورگر فقط به‌عنوان پارامتر کوئری nearby استفاده و نگهداری نمی‌شود.
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIconPng from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Branch,
  fetchMapConfig,
  fetchNearbyBranches,
} from "../api/branches";

// آیکون پیش‌فرض Leaflet در باندلر (مسیرهای نسبی CSS خراب می‌شوند)
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

export default function BranchMapPage() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const userRef = useRef<L.LayerGroup | null>(null);

  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);

  const mapCfg = useQuery({ queryKey: ["map-config"], queryFn: fetchMapConfig });
  const nearby = useQuery({
    queryKey: ["nearby-branches", coords?.lat, coords?.lng],
    queryFn: () => fetchNearbyBranches(coords ? { lat: coords.lat, lng: coords.lng, limit: 50 } : { limit: 50 }),
  });

  const branches: Branch[] = nearby.data?.items ?? [];
  const located = branches.filter((b) => b.latitude !== null && b.longitude !== null);

  // راه‌اندازی یک‌باره نقشه (مقاوم به StrictMode دوبار‌فراخوان)
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: IRAN_CENTER,
      zoom: 6,
      scrollWheelZoom: true,
    });
    mapRef.current = map;
    markersRef.current = L.layerGroup().addTo(map);
    userRef.current = L.layerGroup().addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
      tileRef.current = null;
      markersRef.current = null;
      userRef.current = null;
    };
  }, []);

  // لایه کاشی نقشه از پیکربندی D03 (سرویس فعال؛ OSM پیش‌فرض بدون کلید)
  useEffect(() => {
    const cfg = mapCfg.data;
    if (!cfg || !mapRef.current || tileRef.current) return;
    if (!cfg.provider.tile_url) return; // سرویس‌های دارای کلید: SDK رسمی در تولید
    const layer = L.tileLayer(cfg.provider.tile_url, {
      attribution: cfg.provider.attribution,
      maxZoom: 19,
    });
    layer.addTo(mapRef.current);
    tileRef.current = layer;
  }, [mapCfg.data]);

  // نشانگر شعب — فقط شعب منتشرشدهِ دارای مختصات
  useEffect(() => {
    const group = markersRef.current;
    if (!group) return;
    group.clearLayers();
    for (const b of located) {
      if (b.latitude === null || b.longitude === null) continue;
      const marker = L.marker([Number(b.latitude), Number(b.longitude)]);
      marker.bindPopup(
        `<div dir="rtl" style="font-family:inherit">
          <strong>${b.name}</strong><br/>${b.clinic_name ?? ""}<br/>
          ${b.city ?? ""} ${b.address ? `- ${b.address}` : ""}
          ${b.phone ? `<br/>تلفن: ${b.phone}` : ""}
          ${b.distance_km !== null && b.distance_km !== undefined ? `<br/>فاصله: ~${b.distance_km} کیلومتر` : ""}
        </div>`,
      );
      group.addLayer(marker);
    }
    if (located.length > 0) {
      const bounds = L.latLngBounds(
        located.map((b) => [Number(b.latitude), Number(b.longitude)] as L.LatLngTuple),
      );
      if (coords) bounds.extend([coords.lat, coords.lng]);
      mapRef.current?.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branches, coords]);

  const handleLocate = () => {
    setGeoError(null);
    if (!("geolocation" in navigator)) {
      setGeoError("مرورگر شما از تعیین موقعیت پشتیبانی نمی‌کند.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        setCoords({ lat: latitude, lng: longitude });
        const map = mapRef.current;
        if (map) {
          map.flyTo([latitude, longitude], 12, { duration: 0.8 });
          userRef.current?.clearLayers();
          // دایره موقعیت کاربر — صرفاً نمایشی؛ ذخیره نمی‌شود
          L.circle([latitude, longitude], {
            radius: 250,
            color: "#7c4dff",
            fillColor: "#7c4dff",
            fillOpacity: 0.15,
          })
            .bindPopup("مکان تقریبی شما — فقط برای مرتب‌سازی استفاده شد و ذخیره نمی‌شود")
            .addTo(userRef.current!);
        }
      },
      () => setGeoError("دسترسی به مکان رد شد یا ناموفق بود؛ می‌توانید فهرست شعب را ببینید."),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60000 },
    );
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap mb={2}>
        <Typography variant="h5" fontWeight={800}>
          نقشه شعب (B40)
        </Typography>
        {mapCfg.data && (
          <Chip size="small" variant="outlined" label={`سرویس نقشه: ${mapCfg.data.provider.title}`} />
        )}
        <Box flexGrow={1} />
        <Button variant="contained" onClick={handleLocate}>
          نزدیک‌ترین شعب به من
        </Button>
      </Stack>

      <Alert severity="success" sx={{ mb: 2 }}>
        {nearby.data?.privacy_note ??
          "مکان کاربر فقط برای مرتب‌سازی شعب استفاده می‌شود و ذخیره نمی‌شود."}
      </Alert>
      {geoError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {geoError}
        </Alert>
      )}
      {nearby.data?.sorted_by === "distance" && (
        <Alert severity="info" sx={{ mb: 2 }}>
          فهرست بر اساس فاصله شما (فاصله اقلیدسی-کروی هاروساین) مرتب شد.
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} md={7}>
          <Box
            ref={containerRef}
            sx={{
              height: 460,
              borderRadius: 2,
              overflow: "hidden",
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "#eef3f8",
            }}
          />
        </Grid>
        <Grid item xs={12} md={5}>
          <Stack spacing={1.5} sx={{ maxHeight: 460, overflowY: "auto", pr: 0.5 }}>
            {nearby.isLoading && <CircularProgress size={28} sx={{ mx: "auto", mt: 4 }} />}
            {branches.length === 0 && !nearby.isLoading && (
              <Typography color="text.secondary" textAlign="center" mt={4}>
                شعبه منتشرشده‌ای ثبت نشده است.
              </Typography>
            )}
            {branches.map((b) => (
              <Card key={b.id} variant="outlined">
                <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography fontWeight={700}>{b.name}</Typography>
                    <Box flexGrow={1} />
                    {b.distance_km !== null && b.distance_km !== undefined && (
                      <Chip size="small" color="primary" label={`~${b.distance_km} کیلومتر`} />
                    )}
                    {b.latitude === null && <Chip size="small" label="بدون مختصات" />}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {b.clinic_name ? `${b.clinic_name} — ` : ""}
                    {b.city ?? "—"}
                    {b.address ? `، ${b.address}` : ""}
                  </Typography>
                  {b.phone && (
                    <Typography variant="body2" color="text.secondary">
                      تلفن: {b.phone}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}
