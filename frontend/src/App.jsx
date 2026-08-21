import React, { useState } from 'react';
import confetti from 'canvas-confetti';
import { AlertCircle } from 'lucide-react';

import Header from './components/Header';
import ImageUploader from './components/ImageUploader';
import Scorecard from './components/Scorecard';
import DiffViewer from './components/DiffViewer';
import FindingsList from './components/FindingsList';
import FindingModal from './components/FindingModal';
import DocumentationModal from './components/DocumentationModal';
import ReportExporter from './components/ReportExporter';
import AutodeskLogo from './components/AutodeskLogo';

export default function App() {
  const [englishImage, setEnglishImage] = useState(null);
  const [localizedImage, setLocalizedImage] = useState(null);
  
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isUrlAnalyzing, setIsUrlAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [activeModalFinding, setActiveModalFinding] = useState(null);
  const [isDocsOpen, setIsDocsOpen] = useState(false);

  // Handle Custom Upload Analysis
  const handleAnalyze = async () => {
    if (!englishImage || !localizedImage) return;

    setIsAnalyzing(true);
    setError(null);

    try {
      const formData = new FormData();
      
      if (englishImage.file) {
        formData.append('english_image', englishImage.file);
      } else if (englishImage.preview) {
        const enBlob = await fetch(englishImage.preview).then(r => r.blob());
        formData.append('english_image', enBlob, 'english.png');
      }

      if (localizedImage.file) {
        formData.append('localized_image', localizedImage.file);
      } else if (localizedImage.preview) {
        const locBlob = await fetch(localizedImage.preview).then(r => r.blob());
        formData.append('localized_image', locBlob, 'localized.png');
      }

      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned error ${res.status}`);
      }

      const data = await res.json();
      setResults(data);

      if (data.score === 100) {
        try {
          confetti({
            particleCount: 80,
            spread: 60,
            origin: { y: 0.6 }
          });
        } catch (e) {}
      }
    } catch (err) {
      console.error('Custom image analysis error:', err);
      setError(err.message || 'Image comparison failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Handle Live URL Auto-Capture Analysis
  const handleUrlAnalyze = async (englishUrl, localizedUrl) => {
    setIsUrlAnalyzing(true);
    setError(null);

    try {
      const res = await fetch('/api/capture-and-analyze-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          english_url: englishUrl,
          localized_url: localizedUrl,
          viewport_width: 1280,
          viewport_height: 800,
          wait_seconds: 1.5
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `URL Auto-Capture returned error ${res.status}`);
      }

      const data = await res.json();
      setResults(data);

      setEnglishImage({
        name: englishUrl,
        preview: data.images.baseline_image,
        isPreset: false
      });

      setLocalizedImage({
        name: localizedUrl,
        preview: data.images.localized_image,
        isPreset: false
      });

      if (data.score === 100) {
        try {
          confetti({
            particleCount: 80,
            spread: 60,
            origin: { y: 0.6 }
          });
        } catch (e) {}
      }
    } catch (err) {
      console.error('URL auto-capture error:', err);
      setError(err.message || 'Failed to auto-capture web pages');
    } finally {
      setIsUrlAnalyzing(false);
    }
  };

  const handleClear = () => {
    setEnglishImage(null);
    setLocalizedImage(null);
    setResults(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col selection:bg-sky-500 selection:text-white">
      
      {/* Global Header */}
      <Header
        onOpenDocs={() => setIsDocsOpen(true)}
        isAnalyzing={isAnalyzing || isUrlAnalyzing}
        onReset={handleClear}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        
        {/* 1. Drag & Drop Upload Zone + Live URL Auto-Capture (Demos removed) */}
        <ImageUploader
          englishImage={englishImage}
          localizedImage={localizedImage}
          onEnglishUpload={(file, preview) => {
            setEnglishImage(file ? { file, preview, name: file.name, isPreset: false } : null);
          }}
          onLocalizedUpload={(file, preview) => {
            setLocalizedImage(file ? { file, preview, name: file.name, isPreset: false } : null);
          }}
          onAnalyze={handleAnalyze}
          isAnalyzing={isAnalyzing}
          onClear={handleClear}
          onUrlAnalyze={handleUrlAnalyze}
          isUrlAnalyzing={isUrlAnalyzing}
        />

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <p className="font-bold text-rose-950">Analysis Error</p>
              <p className="text-rose-800">{error}</p>
            </div>
          </div>
        )}

        {/* 2. Results Section */}
        {results && (
          <div className="space-y-6 animate-in fade-in duration-300">
            
            {/* Scorecard */}
            <Scorecard results={results} />

            {/* Visual Diff Viewer */}
            <DiffViewer
              images={results.images}
              findings={results.findings}
              selectedFindingId={selectedFindingId}
              onSelectFinding={setSelectedFindingId}
            />

            {/* Findings List */}
            <FindingsList
              findings={results.findings}
              selectedFindingId={selectedFindingId}
              onSelectFinding={setSelectedFindingId}
              onOpenModal={setActiveModalFinding}
            />

            {/* Final Report Exporter (Consolidated with Embedded Diff Image) */}
            <ReportExporter results={results} />

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-5 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex items-center justify-center">
          <div className="flex items-center gap-2.5">
            <AutodeskLogo className="h-4 w-auto" />
            <span className="text-slate-300">|</span>
            <span className="font-semibold text-slate-600">UI Localization Quality Checker</span>
          </div>
        </div>
      </footer>

      {/* Modals */}
      {activeModalFinding && (
        <FindingModal
          finding={activeModalFinding}
          onClose={() => setActiveModalFinding(null)}
        />
      )}

      <DocumentationModal
        isOpen={isDocsOpen}
        onClose={() => setIsDocsOpen(false)}
      />

    </div>
  );
}
