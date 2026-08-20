import React, { useState } from 'react';
import { FileText, Check } from 'lucide-react';
import { jsPDF } from 'jspdf';

export default function ReportExporter({ results, activePresetTitle }) {
  const [downloading, setDownloading] = useState(false);
  const [exported, setExported] = useState(false);

  if (!results) return null;

  const exportPDF = () => {
    setDownloading(true);
    try {
      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
      });

      doc.setFillColor(6, 150, 215);
      doc.rect(0, 0, 210, 26, 'F');

      doc.setTextColor(255, 255, 255);
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.text('AUTODESK', 14, 12);

      doc.setFontSize(11);
      doc.text('Localization UI Quality Report', 14, 19);

      doc.setTextColor(15, 23, 42);
      doc.setFontSize(13);
      doc.setFont('helvetica', 'bold');
      doc.text('1. Quality Summary', 14, 38);

      doc.setFillColor(248, 250, 252);
      doc.roundedRect(14, 42, 182, 28, 3, 3, 'F');

      doc.setFontSize(20);
      doc.setTextColor(results.score >= 80 ? 16 : 220, results.score >= 80 ? 150 : 38, 38);
      doc.text(`${results.score} / 100`, 22, 58);

      doc.setFontSize(11);
      doc.setTextColor(15, 23, 42);
      doc.text(`Grade: ${results.grade} - ${results.grade_description}`, 65, 54);

      doc.setFontSize(9);
      doc.setTextColor(100, 116, 139);
      doc.text(`Total Defects: ${results.summary.total_defects} | Critical: ${results.summary.critical_count} | Major: ${results.summary.major_count} | Minor: ${results.summary.minor_count}`, 65, 62);

      doc.setTextColor(15, 23, 42);
      doc.setFontSize(13);
      doc.setFont('helvetica', 'bold');
      doc.text('2. Identified Issues & Recommendations', 14, 82);

      let yPos = 88;

      if (results.findings.length === 0) {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(22, 163, 74);
        doc.text('✓ ZERO DEFECTS DETECTED: Layout integrity 100% compliant.', 14, yPos);
      } else {
        results.findings.forEach((f) => {
          if (yPos > 250) {
            doc.addPage();
            yPos = 20;
          }

          doc.setFillColor(248, 250, 252);
          doc.roundedRect(14, yPos, 182, 38, 2, 2, 'F');

          doc.setFontSize(9.5);
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(f.severity === 'Critical' ? 220 : 180, 38, 38);
          doc.text(`[${f.severity.toUpperCase()}] ${f.id}: ${f.title}`, 18, yPos + 7);

          doc.setFontSize(8.5);
          doc.setFont('helvetica', 'normal');
          doc.setTextColor(51, 65, 85);
          
          const splitDesc = doc.splitTextToSize(f.description, 172);
          doc.text(splitDesc, 18, yPos + 14);

          doc.setFont('helvetica', 'bold');
          doc.setTextColor(6, 150, 215);
          doc.text('Fix: ' + f.remediation, 18, yPos + 32);

          yPos += 44;
        });
      }

      doc.save(`autodesk_localization_report_${Date.now()}.pdf`);
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
          Export Audit Results
        </h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Download a clean PDF quality report to share with development and localization teams
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
            <span>Download PDF Report</span>
          </>
        )}
      </button>
    </div>
  );
}
