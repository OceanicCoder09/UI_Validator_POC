import React, { useState } from 'react';
import { FileText, Check } from 'lucide-react';
import { jsPDF } from 'jspdf';

// Helper to convert sharp Autodesk SVG logo to crisp PNG data URL for jsPDF
const getLogoDataUrl = () => {
  return new Promise((resolve) => {
    const svgStr = `<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 100 100'><rect width='100' height='100' fill='#000000'/><path d='M 18 69 L 18 51 L 54 28 L 78 28 L 78 69 L 55 69 C 55 61 58 56 74 47 L 55 47 L 18 69 Z' fill='#FFFFFF'/></svg>`;
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 160;
      canvas.height = 160;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => resolve(null);
  });
};

export default function ReportExporter({ results }) {
  const [downloading, setDownloading] = useState(false);
  const [exported, setExported] = useState(false);

  if (!results) return null;

  const exportPDF = async () => {
    setDownloading(true);
    try {
      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
      });

      // 1. Header Banner
      doc.setFillColor(0, 0, 0); // Sharp black Autodesk banner
      doc.rect(0, 0, 210, 24, 'F');

      // Add Sharp Autodesk Logo Icon to PDF Header
      try {
        const logoDataUrl = await getLogoDataUrl();
        if (logoDataUrl) {
          doc.addImage(logoDataUrl, 'PNG', 14, 5, 14, 14);
        }
      } catch (e) {
        console.warn('Could not render logo in PDF:', e);
      }

      doc.setTextColor(255, 255, 255);
      doc.setFontSize(15);
      doc.setFont('helvetica', 'bold');
      doc.text('AUTODESK', 32, 12);

      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(203, 213, 225);
      doc.text('Localization UI Quality Audit Report', 32, 18);

      // 2. Score Summary Box
      doc.setTextColor(15, 23, 42);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('1. Quality Summary', 14, 32);

      doc.setFillColor(248, 250, 252);
      doc.rect(14, 35, 182, 20, 'F');
      doc.setDrawColor(226, 232, 240);
      doc.rect(14, 35, 182, 20, 'S');

      doc.setFontSize(16);
      doc.setTextColor(results.score >= 80 ? 16 : 220, results.score >= 80 ? 150 : 38, 38);
      doc.text(`${results.score} / 100`, 20, 48);

      doc.setFontSize(9);
      doc.setTextColor(15, 23, 42);
      doc.setFont('helvetica', 'bold');
      doc.text(results.score === 100 ? 'Clean UI — Zero Visual Defects' : (results.grade_description || 'Analysis Completed'), 58, 43);

      doc.setFont('helvetica', 'normal');
      doc.setTextColor(100, 116, 139);
      doc.text(`Total Defects: ${results.summary.total_defects} | Critical: ${results.summary.critical_count} | Major: ${results.summary.major_count} | Minor: ${results.summary.minor_count}`, 58, 50);

      // 3. Visual Comparison: BOTH IMAGES (English Baseline + Localized Annotated Diff)
      let yPos = 61;
      doc.setTextColor(15, 23, 42);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('2. Visual Comparison (Baseline Reference vs Localized View)', 14, yPos);
      yPos += 4;

      const imgWidth = 88;
      const imgHeight = 55;

      // Left Image: English Baseline Reference
      if (results.images && results.images.baseline_image) {
        doc.setFontSize(8);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(37, 99, 235);
        doc.text('English Baseline Reference', 14, yPos + 3);
        try {
          doc.addImage(results.images.baseline_image, 'PNG', 14, yPos + 5, imgWidth, imgHeight);
        } catch (e1) {
          console.warn('Could not add baseline image:', e1);
        }
      }

      // Right Image: Localized Screenshot with Annotated Defects
      if (results.images && results.images.annotated_diff_image) {
        doc.setFontSize(8);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(220, 38, 38);
        doc.text('Localized View (Defects Marked)', 108, yPos + 3);
        try {
          doc.addImage(results.images.annotated_diff_image, 'PNG', 108, yPos + 5, imgWidth, imgHeight);
        } catch (e2) {
          console.warn('Could not add annotated image:', e2);
        }
      }

      yPos += imgHeight + 12;

      // 4. Identified Issues & Recommendations
      doc.setTextColor(15, 23, 42);
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.text('3. Identified Issues & Recommendations', 14, yPos);
      yPos += 5;

      if (results.findings.length === 0) {
        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(22, 163, 74);
        doc.text('✓ ZERO DEFECTS DETECTED: Visual layout integrity is 100% compliant.', 14, yPos);
      } else {
        results.findings.forEach((f) => {
          if (yPos > 255) {
            doc.addPage();
            yPos = 18;
          }

          doc.setFillColor(248, 250, 252);
          doc.rect(14, yPos, 182, 32, 'F');
          doc.setDrawColor(226, 232, 240);
          doc.rect(14, yPos, 182, 32, 'S');

          doc.setFontSize(8.5);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(f.severity === 'Critical' ? 220 : 180, 38, 38);
          doc.text(`[${f.severity.toUpperCase()}] ${f.id}: ${f.title}`, 18, yPos + 6);

          doc.setFontSize(7.5);
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(51, 65, 85);
          
          const splitDesc = doc.splitTextToSize(f.description, 172);
          doc.text(splitDesc, 18, yPos + 12);

          doc.setFont('helvetica', 'bold');
          doc.setTextColor(6, 150, 215);
          doc.text('Fix: ' + f.remediation, 18, yPos + 26);

          yPos += 36;
        });
      }

      doc.save(`autodesk_localization_audit_report_${Date.now()}.pdf`);
      setExported(true);
      setTimeout(() => setExported(false), 2500);
    } catch (e) {
      console.error('PDF export failed:', e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 card-shadow flex flex-col sm:flex-row items-center justify-between gap-4">
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
          Export Final Audit Summary
        </h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Download a comprehensive PDF audit report with side-by-side visual comparison screenshots and remediation steps
        </p>
      </div>

      <button
        onClick={exportPDF}
        disabled={downloading}
        className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sm transition active:scale-95 disabled:opacity-50"
      >
        {downloading ? (
          <>
            <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <span>Generating PDF...</span>
          </>
        ) : exported ? (
          <>
            <Check className="w-3.5 h-3.5 text-white" />
            <span>PDF Downloaded!</span>
          </>
        ) : (
          <>
            <FileText className="w-3.5 h-3.5" />
            <span>Download Audit Report (PDF)</span>
          </>
        )}
      </button>
    </div>
  );
}
