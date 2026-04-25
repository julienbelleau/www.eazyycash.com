"use client";

import jsPDF from "jspdf";
import { computeProjectTakeoff } from "./takeoff";
import type { Project } from "./store";
import { MODELS } from "./moderco";

interface PdfOptions {
  project: Project;
  snapshots?: { wallId: string; dataUrl: string }[];
}

const ACCENT = "#d29c52";
const INK = "#1a1d22";
const MUTED = "#6b6f78";

export function generateQuotePdf({ project, snapshots = [] }: PdfOptions): jsPDF {
  const doc = new jsPDF({ unit: "pt", format: "letter", orientation: "portrait" });
  const pw = doc.internal.pageSize.getWidth();
  const ph = doc.internal.pageSize.getHeight();
  const margin = 36;
  const takeoff = computeProjectTakeoff(project);
  const formattedDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  // ===== Cover header
  doc.setFillColor(ACCENT);
  doc.rect(0, 0, pw, 6, "F");

  doc.setTextColor(INK);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.text("Moderco Studio", margin, 50);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(MUTED);
  doc.text("Operable Partition Quotation", margin, 66);

  doc.setFontSize(9);
  doc.text(formattedDate, pw - margin, 50, { align: "right" });
  doc.text(`Project ID: ${project.id}`, pw - margin, 64, { align: "right" });

  // ===== Project block
  let y = 100;
  doc.setDrawColor(220);
  doc.line(margin, y, pw - margin, y);
  y += 22;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(INK);
  doc.text(project.name, margin, y);
  y += 16;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(MUTED);
  doc.text(`Client: ${project.client}`, margin, y);
  y += 13;
  if (project.location) {
    doc.text(`Location: ${project.location}`, margin, y);
    y += 13;
  }
  doc.text(`Walls in scope: ${project.walls.length}`, margin, y);
  y += 24;

  // ===== Project totals
  drawSectionHeader(doc, margin, pw, y, "PROJECT TOTALS");
  y += 22;
  const tots = takeoff.totals;
  const summary: [string, string][] = [
    ["Panels", `${tots.panelCount}`],
    ["Track length", `${tots.trackLengthFt.toFixed(1)} ft`],
    ["Total area", `${Math.round(tots.totalAreaSqft)} sq.ft`],
    ["Estimated weight", `${Math.round(tots.estimatedWeightLb).toLocaleString()} lb`],
    ["Project total", formatCurrency(tots.cost)],
  ];
  summary.forEach(([k, v], i) => {
    const colWidth = (pw - margin * 2) / 5;
    const x = margin + colWidth * i;
    doc.setFontSize(8);
    doc.setTextColor(MUTED);
    doc.text(k.toUpperCase(), x, y);
    doc.setFontSize(13);
    doc.setTextColor(INK);
    doc.setFont("helvetica", "bold");
    doc.text(v, x, y + 16);
    doc.setFont("helvetica", "normal");
  });
  y += 44;

  // ===== Per-wall details
  for (let wi = 0; wi < takeoff.walls.length; wi++) {
    const w = takeoff.walls[wi];
    const wall = project.walls.find((x) => x.id === w.wallId)!;
    const model = MODELS[wall.modelId];

    if (y > ph - 280) {
      doc.addPage();
      y = margin + 14;
    }

    drawSectionHeader(doc, margin, pw, y, `WALL ${wi + 1} — ${w.wallName}`);
    y += 20;

    // Snapshot if available
    const snap = snapshots.find((s) => s.wallId === w.wallId);
    if (snap) {
      const imgW = pw - margin * 2;
      const imgH = imgW * 0.42;
      try {
        doc.addImage(snap.dataUrl, "PNG", margin, y, imgW, imgH, undefined, "FAST");
        y += imgH + 12;
      } catch {
        /* ignore snapshot errors */
      }
    }

    // Spec block
    doc.setFontSize(9);
    doc.setTextColor(INK);
    doc.setFont("helvetica", "bold");
    doc.text(`${model.name} (${model.shortName})`, margin, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(MUTED);
    doc.text(model.description, margin + 130, y, {
      maxWidth: pw - margin * 2 - 130,
    });
    y += 16;

    const specs: [string, string][] = [
      ["Configuration", capitalize(model.configuration.replace("-", " "))],
      ["Operation", capitalize(model.operation)],
      ["Panel thickness", `${model.thicknessIn}″`],
      ["Panel size", `${w.panelWidthIn}″ × ${w.panelHeightFt.toFixed(1)}′`],
      ["Panel count", `${w.panelCount}`],
      ["Carriers", `${w.carrierCount}`],
      ["Track", `${w.trackOption} · ${w.trackLengthFt.toFixed(1)} ft`],
      ["Stack", capitalize(wall.stack.replace("-", " "))],
      ["Finish", w.finish],
      ["STC", `${w.stcRange[0]}–${w.stcRange[1]}`],
      ["Weight", `${Math.round(w.estimatedWeightLb).toLocaleString()} lb`],
      ["Area", `${Math.round(w.totalAreaSqft)} sq.ft`],
    ];
    drawKeyValues(doc, margin, pw, y, specs);
    y += Math.ceil(specs.length / 4) * 26 + 8;

    // BOM table
    drawBomHeader(doc, margin, pw, y);
    y += 16;
    const lines: [string, string, string, number][] = [
      [`${model.name} panels (${w.finish})`, `${Math.round(w.totalAreaSqft)} sq.ft`, "Panel", w.cost.panels],
      [`Track ${w.trackOption}`, `${w.trackLengthFt.toFixed(1)} ft`, "Track", w.cost.track],
      ["Carriers", `${w.carrierCount} ea`, "Hardware", w.cost.carriers],
      ["Acoustic seals & sweeps", `${w.panelCount} ea`, "Hardware", w.cost.seals],
      ["Hardware pack", "1 ea", "Hardware", w.cost.hardware],
      ["Engineering & shop drawings", "1 lot", "Service", w.cost.engineering],
    ];
    if (w.cost.operationUplift > 0) {
      lines.push(["Electric operation uplift", "—", "System", w.cost.operationUplift]);
    }
    lines.forEach((row) => {
      doc.setDrawColor(240);
      doc.line(margin, y - 2, pw - margin, y - 2);
      drawBomRow(doc, margin, pw, y + 12, row);
      y += 16;
    });
    doc.setDrawColor(160);
    doc.setLineWidth(0.6);
    doc.line(margin, y, pw - margin, y);
    doc.setLineWidth(0.2);
    y += 16;

    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(INK);
    doc.text("Wall Subtotal", margin, y);
    doc.text(formatCurrency(w.cost.total), pw - margin, y, { align: "right" });
    doc.setFont("helvetica", "normal");
    y += 22;
  }

  // ===== Final total
  if (y > ph - 120) {
    doc.addPage();
    y = margin + 14;
  }
  doc.setFillColor(245, 240, 230);
  doc.rect(margin, y - 10, pw - margin * 2, 50, "F");
  doc.setTextColor(INK);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.text("ESTIMATED PROJECT TOTAL", margin + 16, y + 10);
  doc.setFontSize(20);
  doc.text(formatCurrency(tots.cost), pw - margin - 16, y + 18, {
    align: "right",
  });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(MUTED);
  doc.text(
    "Order-of-magnitude estimate based on Moderco product literature. Final quotation requires site survey and engineering review.",
    margin + 16,
    y + 32,
    { maxWidth: pw - margin * 2 - 32 },
  );

  // Footer
  const totalPages = (doc.internal as unknown as { pages: unknown[] }).pages.length - 1;
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    doc.setFontSize(8);
    doc.setTextColor(MUTED);
    doc.text("Generated with Moderco Studio · Configurator preview", margin, ph - 18);
    doc.text(`Page ${p} / ${totalPages}`, pw - margin, ph - 18, { align: "right" });
  }

  return doc;
}

function drawSectionHeader(
  doc: jsPDF,
  margin: number,
  pw: number,
  y: number,
  title: string,
) {
  doc.setFillColor(ACCENT);
  doc.rect(margin, y - 2, 3, 12, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(INK);
  doc.text(title, margin + 10, y + 8);
  doc.setDrawColor(230);
  doc.line(margin + 100, y + 6, pw - margin, y + 6);
}

function drawKeyValues(
  doc: jsPDF,
  margin: number,
  pw: number,
  y: number,
  items: [string, string][],
) {
  const colW = (pw - margin * 2) / 4;
  doc.setFont("helvetica", "normal");
  items.forEach((kv, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = margin + colW * col;
    const yy = y + row * 26;
    doc.setFontSize(7);
    doc.setTextColor(MUTED);
    doc.text(kv[0].toUpperCase(), x, yy);
    doc.setFontSize(10);
    doc.setTextColor(INK);
    doc.text(kv[1], x, yy + 12);
  });
}

function drawBomHeader(doc: jsPDF, margin: number, pw: number, y: number) {
  doc.setFontSize(8);
  doc.setTextColor(MUTED);
  doc.text("DESCRIPTION", margin, y + 8);
  doc.text("QUANTITY", margin + 280, y + 8);
  doc.text("CATEGORY", margin + 380, y + 8);
  doc.text("AMOUNT", pw - margin, y + 8, { align: "right" });
  doc.setDrawColor(180);
  doc.line(margin, y + 12, pw - margin, y + 12);
}

function drawBomRow(
  doc: jsPDF,
  margin: number,
  pw: number,
  y: number,
  row: [string, string, string, number],
) {
  doc.setFontSize(9);
  doc.setTextColor(INK);
  doc.text(row[0], margin, y);
  doc.text(row[1], margin + 280, y);
  doc.text(row[2], margin + 380, y);
  doc.text(formatCurrency(row[3]), pw - margin, y, { align: "right" });
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
