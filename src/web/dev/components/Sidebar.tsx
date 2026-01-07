
import React from 'react';
import { ViewType, Language } from '../types';
import { translations } from '../i18n';
import logo from '../assets/logo.png';

interface SidebarProps {
  expanded: boolean;
  setExpanded: (expanded: boolean) => void;
  currentView: ViewType;
  setView: (view: ViewType) => void;
  language: Language;
}

export const Sidebar: React.FC<SidebarProps> = ({ expanded, setExpanded, currentView, setView, language }) => {
  const t = translations[language];
  const navItems = [
    { id: 'configs' as ViewType, icon: 'fa-folder-tree', label: t.nav_configs },
    { id: 'items' as ViewType, icon: 'fa-gift', label: t.nav_items },
    { id: 'editor' as ViewType, icon: 'fa-sliders', label: t.nav_editor },
  ];

  return (
    <aside 
      className={`bg-white text-slate-900 transition-all duration-300 ease-in-out flex flex-col z-50 shadow-sm border-r border-slate-200 overflow-hidden ${expanded ? 'w-64' : 'w-20'}`}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      role="navigation"
      aria-expanded={expanded}
    >
      {/* Branding Section - Purple background logo */}
      <div className="h-16 flex items-center shrink-0 px-5 gap-4">
        <div className="bg-indigo-600 w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-indigo-200 overflow-hidden">
          <img src={logo} alt="Logo" className="w-full h-full object-cover" />
        </div>
        <div className={`transition-all duration-300 flex flex-col justify-center ${expanded ? 'opacity-100 translate-x-0 ml-2' : 'opacity-0 -translate-x-4 w-0 pointer-events-none'}`}>
          <div className="bg-indigo-600 text-white text-[10px] font-black px-1.5 py-0.5 rounded leading-none mb-0.5 self-start tracking-wider">
            CARDPOOLMANAGER
          </div>
          <span className="font-black text-lg tracking-tight whitespace-nowrap text-green-500 leading-none">
            GachaMaster
          </span>
        </div>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 py-6 space-y-1">
        {navItems.map(item => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`w-full flex items-center px-5 py-4 transition-all group relative border-r-0 ${
                isActive 
                  ? 'bg-indigo-600 text-white' 
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
              aria-label={item.label}
            >
              <div className="w-10 flex justify-center shrink-0">
                <i className={`fas ${item.icon} text-lg transition-transform group-hover:scale-110`}></i>
              </div>
              <div className={`transition-all duration-300 overflow-hidden ${expanded ? 'opacity-100 ml-4' : 'opacity-0 w-0'}`}>
                <span className="font-bold whitespace-nowrap text-sm tracking-wide">{item.label}</span>
              </div>
              
              {!expanded && (
                <div className="absolute left-full ml-4 px-3 py-1.5 bg-slate-800 text-white text-[10px] font-black uppercase rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-all translate-x-[-10px] group-hover:translate-x-0 whitespace-nowrap z-[100] border border-slate-700 shadow-xl">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* GitHub Link */}
      <a
        href="https://github.com/Ruafafa/astrbot_plugin_ww_gacha_sim"
        target="_blank"
        rel="noopener noreferrer"
        className="w-full flex items-center px-5 py-4 transition-all group relative border-r-0 text-slate-400 hover:bg-slate-50 hover:text-slate-900 border-t border-slate-100"
        aria-label="GitHub"
      >
        <div className="w-10 flex justify-center shrink-0">
          <i className="fab fa-github text-xl transition-transform group-hover:scale-110"></i>
        </div>
        <div className={`transition-all duration-300 overflow-hidden ${expanded ? 'opacity-100 ml-4' : 'opacity-0 w-0'}`}>
          <span className="font-bold whitespace-nowrap text-sm tracking-wide">GitHub</span>
        </div>
        
        {!expanded && (
          <div className="absolute left-full ml-4 px-3 py-1.5 bg-slate-800 text-white text-[10px] font-black uppercase rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-all translate-x-[-10px] group-hover:translate-x-0 whitespace-nowrap z-[100] border border-slate-700 shadow-xl">
            GitHub
          </div>
        )}
      </a>
    </aside>
  );
};
