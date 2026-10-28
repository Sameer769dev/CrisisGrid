"use client";
// Interactive HTML5 Canvas - sam-3.1 boxes (faithful overlay; live SAM mask
// payload is opaque vendor RLE, so boxes are the honest rendering), candidate
// corridors and landing zones coloured strictly by verification state.
// Green = verified/passable, Red = hazard/rejected, Yellow = unverified proposal.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { NormPoint, ScanDetection } from "@/lib/api";

export interface CanvasCorridor {
  id: string; name: string; points: NormPoint[];
  status: "verified" | "rejected" | "unverified";
  hazardRatio?: number | null; detail?: string;
}
export interface CanvasZone {
  id: string; name: string; center: NormPoint; radius: number;
  status: "verified" | "rejected" | "unverified";
  hazardRatio?: number | null; detail?: string;
}
export type InspectItem =
  | { kind: "detection"; detection: ScanDetection }
  | { kind: "corridor"; corridor: CanvasCorridor }
  | { kind: "zone"; zone: CanvasZone }
  | null;

interface Props {
  imageUrl: string | null;
  detections: ScanDetection[];
  corridors: CanvasCorridor[];
  zones: CanvasZone[];
  visibleConcepts: Set<string>;
  showCorridors: boolean;
  showZones: boolean;
  selected: InspectItem;
  onInspect: (item: InspectItem) => void;
}

const W = 960; const MAX_H = 620; const MIN_H = 360;

function statusColor(s: string) {
  return s === "verified" ? "#00C853" : s === "rejected" ? "#FF2D20" : "#FFD600";
}

export default function TacticalCanvas(p: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    if (!p.imageUrl) { imgRef.current = null; setImgSize(null); return; }
    const img = new Image();
    img.onload = () => { imgRef.current = img; setImgSize({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.src = p.imageUrl;
  }, [p.imageUrl]);

  const canvasH = useMemo(() => {
    if (!imgSize) return 420;
    return Math.max(MIN_H, Math.min(MAX_H, Math.round((W * imgSize.h) / Math.max(1, imgSize.w))));
  }, [imgSize]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    ctx.clearRect(0, 0, W, canvasH);
    // Background + optional source image (contain-fit, letterboxed on paper).
    ctx.fillStyle = "#FAFAF5"; ctx.fillRect(0, 0, W, canvasH);
    let ox = 0, oy = 0, dw = W, dh = canvasH;
    if (imgRef.current && imgSize) {
      const scale = Math.min(W / imgSize.w, canvasH / imgSize.h);
      dw = imgSize.w * scale; dh = imgSize.h * scale; ox = (W - dw) / 2; oy = (canvasH - dh) / 2;
      ctx.drawImage(imgRef.current, ox, oy, dw, dh);
      canvas.dataset.ox = String(ox); canvas.dataset.oy = String(oy);
      canvas.dataset.dw = String(dw); canvas.dataset.dh = String(dh);
    } else {
      ctx.strokeStyle = "#111"; ctx.lineWidth = 1;
      for (let x = 0; x <= W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvasH); ctx.stroke(); }
      for (let y = 0; y <= canvasH; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
      ctx.font = "bold 22px monospace"; ctx.fillStyle = "#111";
      ctx.fillText("NO IMAGE LOADED", 24, 52);
      ctx.font = "14px monospace";
      ctx.fillText("Upload aerial / drone / street imagery, then run STEP 1 - SCAN.", 24, 80);
      ctx.fillText("Hazards render RED, passable infrastructure GREEN,", 24, 102);
      ctx.fillText("unverified proposals YELLOW. Only the Python verifier turns a route green.", 24, 124);
    }
    const X = (n: number) => ox + n * dw; const Y = (n: number) => oy + n * dh;
    // Detections: translucent fill + thick border + label chip.
    for (const d of p.detections) {
      if (!p.visibleConcepts.has(d.concept)) continue;
      const x1 = X(d.bbox.x_min), y1 = Y(d.bbox.y_min), x2 = X(d.bbox.x_max), y2 = Y(d.bbox.y_max);
      const isSel = p.selected?.kind === "detection" && p.selected.detection === d;
      ctx.fillStyle = d.kind === "hazard" ? "rgba(255,45,32,0.28)" : "rgba(0,200,83,0.28)";
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
      ctx.strokeStyle = d.color || (d.kind === "hazard" ? "#FF2D20" : "#00C853");
      ctx.lineWidth = isSel ? 5 : 3; ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      if (isSel) { ctx.strokeStyle = "#111"; ctx.lineWidth = 1.5; ctx.strokeRect(x1 - 5, y1 - 5, x2 - x1 + 10, y2 - y1 + 10); }
      const label = `${d.concept.toUpperCase()} ${(d.area_fraction * 100).toFixed(1)}%`;
      ctx.font = "bold 11px monospace";
      const tw = ctx.measureText(label).width + 10;
      ctx.fillStyle = "#111"; ctx.fillRect(x1, Math.max(0, y1 - 18), tw, 18);
      ctx.fillStyle = "#fff"; ctx.fillText(label, x1 + 5, Math.max(13, y1 - 5));
    }
    // Landing zones: circle + crosshair.
    if (p.showZones) for (const z of p.zones) {
      const cx = X(z.center.x), cy = Y(z.center.y), r = Math.max(10, z.radius * dw);
      const col = statusColor(z.status);
      const isSel = p.selected?.kind === "zone" && p.selected.zone.id === z.id;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = z.status === "verified" ? "rgba(0,200,83,0.30)" : z.status === "rejected" ? "rgba(255,45,32,0.30)" : "rgba(255,214,0,0.35)";
      ctx.fill(); ctx.strokeStyle = col; ctx.lineWidth = isSel ? 5 : 3; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx - 8, cy); ctx.lineTo(cx + 8, cy); ctx.moveTo(cx, cy - 8); ctx.lineTo(cx, cy + 8);
      ctx.strokeStyle = "#111"; ctx.lineWidth = 2; ctx.stroke();
      ctx.font = "bold 11px monospace"; ctx.fillStyle = "#111";
      ctx.fillText(`${z.id.toUpperCase()} ${z.status.toUpperCase()}`, cx + r + 6, cy + 4);
      if (z.status === "rejected") { ctx.strokeStyle = "#FF2D20"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cx - r * 0.7, cy - r * 0.7); ctx.lineTo(cx + r * 0.7, cy + r * 0.7); ctx.moveTo(cx + r * 0.7, cy - r * 0.7); ctx.lineTo(cx - r * 0.7, cy + r * 0.7); ctx.stroke(); }
    }
    // Corridors: polyline with waypoint nodes.
    if (p.showCorridors) for (const c of p.corridors) {
      if (c.points.length < 2) continue;
      const col = statusColor(c.status);
      const isSel = p.selected?.kind === "corridor" && p.selected.corridor.id === c.id;
      ctx.beginPath();
      c.points.forEach((pt, i) => { const x = X(pt.x), y = Y(pt.y); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
      ctx.strokeStyle = "#111"; ctx.lineWidth = (isSel ? 9 : 7); ctx.stroke();
      ctx.strokeStyle = col; ctx.lineWidth = isSel ? 5 : 3.5;
      if (c.status === "unverified") ctx.setLineDash([10, 6]); else ctx.setLineDash([]);
      ctx.stroke(); ctx.setLineDash([]);
      for (const pt of c.points) { ctx.beginPath(); ctx.arc(X(pt.x), Y(pt.y), 5, 0, Math.PI * 2); ctx.fillStyle = col; ctx.fill(); ctx.strokeStyle = "#111"; ctx.lineWidth = 2; ctx.stroke(); }
      const mid = c.points[Math.floor(c.points.length / 2)];
      ctx.font = "bold 11px monospace"; ctx.fillStyle = "#111";
      ctx.fillText(`${c.id.toUpperCase()} ${c.status.toUpperCase()}`, X(mid.x) + 8, Y(mid.y) - 8);
      if (c.status === "rejected") { const a = c.points[0], b = c.points[c.points.length - 1]; ctx.strokeStyle = "#FF2D20"; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(X(a.x) - 8, Y(a.y) - 8); ctx.lineTo(X(a.x) + 8, Y(a.y) + 8); ctx.moveTo(X(a.x) + 8, Y(a.y) - 8); ctx.lineTo(X(a.x) - 8, Y(a.y) + 8); ctx.stroke(); void b; }
    }
    ctx.lineWidth = 3; ctx.strokeStyle = "#111"; ctx.strokeRect(2, 2, W - 4, canvasH - 4);
  }, [canvasH, imgSize, p.detections, p.corridors, p.zones, p.visibleConcepts, p.showCorridors, p.showZones, p.selected]);

  useEffect(() => { draw(); }, [draw]);

  function toNorm(e: React.MouseEvent<HTMLCanvasElement>): NormPoint | null {
    const canvas = canvasRef.current; if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * canvasH;
    const ox = Number(canvas.dataset.ox ?? 0), oy = Number(canvas.dataset.oy ?? 0);
    const dw = Number(canvas.dataset.dw ?? W), dh = Number(canvas.dataset.dh ?? canvasH);
    const x = (px - ox) / dw, y = (py - oy) / dh;
    return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x, y } : null;
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const n = toNorm(e); if (!n) { p.onInspect(null); return; }
    // Zones first (small targets), then corridors (near a waypoint/segment), then boxes (smallest containing).
    if (p.showZones) for (const z of p.zones) {
      if (Math.hypot(z.center.x - n.x, z.center.y - n.y) <= Math.max(z.radius, 0.03)) { p.onInspect({ kind: "zone", zone: z }); return; }
    }
    if (p.showCorridors) for (const c of p.corridors) {
      if (c.points.some((pt) => Math.hypot(pt.x - n.x, pt.y - n.y) < 0.03)) { p.onInspect({ kind: "corridor", corridor: c }); return; }
    }
    const hits = p.detections.filter((d) => p.visibleConcepts.has(d.concept) && n.x >= d.bbox.x_min && n.x <= d.bbox.x_max && n.y >= d.bbox.y_min && n.y <= d.bbox.y_max)
      .sort((a, b) => a.area_fraction - b.area_fraction);
    p.onInspect(hits[0] ? { kind: "detection", detection: hits[0] } : null);
  }

  function handleMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const n = toNorm(e);
    if (!n) { setHover(null); return; }
    const hit = p.detections.find((d) => p.visibleConcepts.has(d.concept) && n.x >= d.bbox.x_min && n.x <= d.bbox.x_max && n.y >= d.bbox.y_min && n.y <= d.bbox.y_max);
    setHover(hit ? `${hit.concept} - ${(hit.area_fraction * 100).toFixed(1)}% of frame - ${hit.kind === "hazard" ? "HAZARD" : "PASSABLE"}` : `x ${(n.x * 100).toFixed(0)}% / y ${(n.y * 100).toFixed(0)}%`);
  }

  const sel = p.selected;
  return (
    <section className="panel" aria-label="Tactical map canvas">
      <div className="panel-head"><span>TACTICAL MAP - SAM-3.1 OVERLAY</span>
        <span className="tag tag-yellow">{p.detections.length ? `${p.detections.length} DETECTIONS` : "AWAITING SCAN"}</span></div>
      <canvas ref={canvasRef} width={W} height={canvasH} className="tactical-canvas tactical-canvas-interactive"
        onClick={handleClick} onMouseMove={handleMove} onMouseLeave={() => setHover(null)}
        role="img" aria-label="Interactive tactical map. Click a coloured box, corridor or landing zone to inspect it." />
      <div className="canvas-status" aria-live="polite">{hover ?? (sel ? "Selected - details below. Click empty map to clear." : "Click any box, corridor line, or landing-zone circle to inspect it.")}</div>
      {sel?.kind === "detection" && (
        <div className="inspect-box"><strong>{sel.detection.concept.toUpperCase()}</strong> - {sel.detection.kind === "hazard" ? "CRITICAL HAZARD" : "PASSABLE INFRASTRUCTURE"} - area {(sel.detection.area_fraction * 100).toFixed(2)}% of frame - box x{sel.detection.bbox.x_min.toFixed(2)} y{sel.detection.bbox.y_min.toFixed(2)} to x{sel.detection.bbox.x_max.toFixed(2)} y{sel.detection.bbox.y_max.toFixed(2)} - mask: {sel.detection.has_mask ? "sam-3.1 RLE present (box is the faithful overlay)" : "bbox only"}</div>
      )}
      {sel?.kind === "corridor" && (
        <div className="inspect-box"><strong>{sel.corridor.id.toUpperCase()} - {sel.corridor.name}</strong> - status: {sel.corridor.status.toUpperCase()}{sel.corridor.hazardRatio != null ? ` - hazard intersection ${(sel.corridor.hazardRatio * 100).toFixed(1)}% (reject threshold 10%)` : ""}{sel.corridor.detail ? ` - ${sel.corridor.detail}` : ""}</div>
      )}
      {sel?.kind === "zone" && (
        <div className="inspect-box"><strong>{sel.zone.id.toUpperCase()} - {sel.zone.name}</strong> - status: {sel.zone.status.toUpperCase()} - centre x{sel.zone.center.x.toFixed(2)} y{sel.zone.center.y.toFixed(2)} radius {sel.zone.radius.toFixed(3)}{sel.zone.hazardRatio != null ? ` - hazard overlap ${(sel.zone.hazardRatio * 100).toFixed(1)}%` : ""}{sel.zone.detail ? ` - ${sel.zone.detail}` : ""}</div>
      )}
      <div className="legend">
        <span><i className="swatch sw-green" /> PASSABLE / VERIFIED</span>
        <span><i className="swatch sw-red" /> HAZARD / REJECTED</span>
        <span><i className="swatch sw-yellow" /> UNVERIFIED PROPOSAL</span>
      </div>
    </section>
  );
}
