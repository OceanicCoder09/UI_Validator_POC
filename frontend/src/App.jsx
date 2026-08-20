import React, { useState, useEffect } from 'react';
import confetti from 'canvas-confetti';
import { AlertCircle } from 'lucide-react';

import Header from './components/Header';
import PresetSelector from './components/PresetSelector';
import ImageUploader from './components/ImageUploader';
import Scorecard from './components/Scorecard';
import DiffViewer from './components/DiffViewer';
import FindingsList from './components/FindingsList';
import FindingModal from './components/FindingModal';
import DocumentationModal from './components/DocumentationModal';
import ReportExporter from './components/ReportExporter';

export default function App() {
  const [presets, setPresets] = useState([]);
  const [activePresetId, setActivePresetId] = useState(null);
  
  const [englishImage, setEnglishImage] = useState(null);
  const [localizedImage, setLocalizedImage] = useState(null);
  
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isUrlAnalyzing, setIsUrlAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [activeModalFinding, setActiveModalFinding] = useState(null);
  const [isDocsOpen, setIsDocsOpen] = useState(false);

  // Fetch presets on mount
  useEffect(() => {
    fetch('/api/presets')
      .then(res => res.json())
      .then(data => {
        setPresets(data);
        if (data.length > 0) {
          handleSelectPreset(data[0].id);
        }
      })
      .catch(err => {
        console.error('Failed to fetch presets:', err);
      });
  }, []);

  // Handle Preset selection
  const handleSelectPreset = async (presetId) => {
    setActivePresetId(presetId);
    setError(null);
    setIsAnalyzing(true);

    try {
      const foundPreset = presets.find(p => p.id === presetId);
      const locFilename = foundPreset ? foundPreset.filename : `${presetId}.png`;

      setEnglishImage({
        name: 'en_baseline.png',
        preview: `/api/preset-image/en_baseline.png`,
        isPreset: true
      });

      setLocalizedImage({
        name: locFilename,
        preview: `/api/preset-image/${locFilename}`,
        isPreset: true
      });

      const formData = new FormData();
      formData.append('preset_id', presetId);

      const res = await fetch('/api/analyze-preset', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        throw new Error(`Analysis failed with status ${res.status}`);
      }

      const data = await res.json();
      setResults(data);

      if (data.score === 100) {
        try {
          confetti({
            particleCount: 60,
            spread: 60,
            origin: { y: 0.6 }
          });
        } catch (e) {
          // ignore confetti errors in restricted browsers
        }
      }
    } catch (err) {
      console.error('Preset analysis error:', err);
      setError(err.message || 'Failed to analyze preset');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Handle Custom Upload Analysis
  const handleAnalyze = async () => {
    if (!englishImage || !localizedImage) return;
    
    if (activePresetId && englishImage.isPreset && localizedImage.isPreset) {
      handleSelectPreset(activePresetId);
      return;
    }

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
      setActivePresetId(null);

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
      setActivePresetId(null);

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
    setActivePresetId(null);
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
        
        {/* 1. Quick Presets Bar */}
        {presets.length > 0 && (
          <PresetSelector
            presets={presets}
            activePresetId={activePresetId}
            onSelectPreset={handleSelectPreset}
            isAnalyzing={isAnalyzing || isUrlAnalyzing}
          />
        )}

        {/* 2. Drag & Drop Upload Zone + Live URL Auto-Capture */}
        <ImageUploader
          englishImage={englishImage}
          localizedImage={localizedImage}
          onEnglishUpload={(file, preview) => {
            setActivePresetId(null);
            setEnglishImage(file ? { file, preview, name: file.name, isPreset: false } : null);
          }}
          onLocalizedUpload={(file, preview) => {
            setActivePresetId(null);
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

        {/* 3. Results Section */}
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

            {/* Exporter */}
            <ReportExporter
              results={results}
              activePresetTitle={presets.find(p => p.id === activePresetId)?.title}
            />

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-5 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex items-center justify-center">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-[#0696D7] flex items-center justify-center">
              <svg viewBox="0 0 32 32" className="w-3 h-3 fill-white">
                <path d="M7 23 L15 7 L23 23 L18 23 L15 14 L12 23 Z" />
              </svg>
            </div>
            <span className="font-bold text-slate-700">Autodesk UI Localization Quality Checker</span>
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
