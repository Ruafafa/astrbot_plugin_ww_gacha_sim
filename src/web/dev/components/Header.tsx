
import React, { useState, useRef, useEffect } from 'react';
import { Language } from '../types';
import { translations } from '../i18n';

interface HeaderProps {
  language: Language;
  setLanguage: (lang: Language) => void;
  onConfigDirChange?: (dir: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ language, setLanguage, onConfigDirChange }) => {
  const [showSettings, setShowSettings] = useState(false);
  const [configDir, setConfigDir] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const t = translations[language];

  // 初始化获取配置目录
  useEffect(() => {
    const fetchConfigDir = async () => {
      try {
        const response = await fetch('/api/configs/directory', { method: 'GET' });
        const data = await response.json();
        if (data.directory) {
          setConfigDir(data.directory);
        }
      } catch (error) {
        console.error('Failed to fetch config directory:', error);
      }
    };
    fetchConfigDir();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSettings(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleDirChange = async (newDir: string) => {
    setConfigDir(newDir);
    try {
      const response = await fetch('/api/configs/directory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: newDir })
      });
      const data = await response.json();
      if (data.success && onConfigDirChange) {
        onConfigDirChange(newDir);
      }
    } catch (error) {
      console.error('Failed to set config directory:', error);
    }
  };

  const handleDirSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      // 使用文件输入获取目录路径
      const file = e.target.files[0];
      let path = file.webkitRelativePath ? file.webkitRelativePath.split('/')[0] : '';
      
      // 在浏览器环境中，我们需要通过API来设置目录
      // 这里简化处理，直接使用输入框的值
      // 实际项目中可以考虑使用Electron或其他桌面框架来获取完整路径
    }
  };

  const triggerFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-center lg:justify-between px-6 lg:px-10 shrink-0 z-40">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-black text-slate-600 uppercase tracking-widest">{t.console_title}</h2>
      </div>
      
      <div className="flex items-center gap-4 relative" ref={dropdownRef}>
        <button 
          onClick={() => setShowSettings(!showSettings)}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all active:scale-95 group border-2 ${showSettings ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white border-slate-100 text-slate-500 hover:border-slate-200'}`}
        >
          <i className={`fas fa-pen-to-square text-lg transition-transform duration-500 ${showSettings ? 'scale-110' : 'group-hover:rotate-12'}`}></i>
          <span className="text-xs font-black uppercase tracking-tight">{t.settings}</span>
        </button>

        {showSettings && (
          <div className="absolute top-full right-0 mt-2 w-72 bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden animate-notification z-50">
            {/* Language Section */}
            <div className="p-4 bg-slate-50 border-b border-slate-100">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{t.language} / Language</span>
            </div>
            <div className="p-2 border-b border-slate-100">
              <button 
                onClick={() => { setLanguage('zh'); }}
                className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${language === 'zh' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                <span>简体中文</span>
                {language === 'zh' && <i className="fas fa-check text-xs"></i>}
              </button>
              <button 
                onClick={() => { setLanguage('en'); }}
                className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl text-sm font-bold transition-all mt-1 ${language === 'en' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                <span>English</span>
                {language === 'en' && <i className="fas fa-check text-xs"></i>}
              </button>
            </div>

            {/* Config Directory Section */}
            <div className="p-4 bg-slate-50 border-b border-slate-100">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{(t as any).config_dir} / CONFIG DIRECTORY</span>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex gap-2">
                <input 
                  type="text"
                  value={configDir}
                  placeholder="C:/Path/To/Configs"
                  onChange={(e) => setConfigDir(e.target.value)}
                  onBlur={(e) => handleDirChange(e.target.value)}
                  className="flex-1 min-w-0 bg-slate-50 border border-slate-200 px-3 py-2 rounded-lg text-xs font-bold text-slate-700 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50/50 transition-all"
                />
                <button 
                  onClick={triggerFileSelect}
                  className="w-10 h-10 shrink-0 flex items-center justify-center bg-white border border-slate-200 rounded-lg text-slate-400 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50 transition-all shadow-sm active:scale-90"
                  title={(t as any).select_dir}
                >
                  <i className="fas fa-folder-open text-sm"></i>
                </button>
              </div>
              <p className="text-[10px] font-bold text-slate-400 italic">
                {language === 'zh' ? '提示：该路径用于自动扫描配置文件' : 'Note: This path is used to scan config files automatically'}
              </p>
            </div>

            {/* Hidden Input for Directory Selection */}
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleDirSelect}
              style={{ display: 'none' }}
              // @ts-ignore
              webkitdirectory=""
              directory=""
            />
          </div>
        )}
      </div>
    </header>
  );
};
