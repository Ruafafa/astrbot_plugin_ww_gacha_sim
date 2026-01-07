
import React, { useState, useMemo } from 'react';
import { PoolConfig, Language, GachaItem } from '../types';
import { translations } from '../i18n';

interface ConfigManagerProps {
  configs: PoolConfig[];
  items: GachaItem[];
  onEdit: (config: PoolConfig) => void;
  onCreate: () => void;
  onDelete: (idx: number) => void;
  selectedIdx: number | null;
  setSelectedIdx: (idx: number | null) => void;
  language: Language;
  selectedGroup: string;
  onSelectGroup: (group: string) => void;
}

export const ConfigManager: React.FC<ConfigManagerProps> = ({ 
  configs, items, onEdit, onCreate, onDelete, selectedIdx, setSelectedIdx, language, selectedGroup, onSelectGroup 
}) => {
  const t = translations[language];
  const [showGroupDropdown, setShowGroupDropdown] = useState(false);

  // 获取所有唯一的配置组
  const configGroups = useMemo(() => {
    const groups = new Set<string>();
    configs.forEach(config => {
      groups.add(config.config_group);
    });
    return Array.from(groups).sort();
  }, [configs]);

  // 根据选中的配置组过滤配置
  const filteredConfigs = useMemo(() => {
    return configs.filter(config => config.config_group === selectedGroup);
  }, [configs, selectedGroup]);

  return (
    <div className="space-y-10 animate-fadeIn">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <h1 className="text-4xl font-black text-slate-800 tracking-tight">{t.pool_configs}</h1>
            <p className="text-slate-500 font-medium">{t.pool_desc}</p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-50/50 border border-indigo-100 rounded-xl">
             <i className="fas fa-layer-group text-[10px] text-indigo-400"></i>
             <span className="text-[10px] font-black text-indigo-600 uppercase tracking-wider">{(t as any).current_group_hint}: <span className="text-indigo-800 font-black">{selectedGroup.toUpperCase()}</span></span>
          </div>
        </div>
        <div className="flex items-center gap-3 relative">
          <button 
            onClick={() => setShowGroupDropdown(!showGroupDropdown)}
            className="px-6 py-3 rounded-2xl font-bold flex items-center gap-2 transition-all border-2 bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 active:scale-95"
          >
            <i className="fas fa-layer-group"></i>
            {t.select_group}
          </button>
          
          {/* Group Dropdown */}
          {showGroupDropdown && (
            <div className="absolute top-full right-0 mt-3 w-64 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden z-50 animate-notification">
              <div className="p-4 bg-slate-50 border-b border-slate-100">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{t.select_group}</span>
              </div>
              <div className="max-h-64 overflow-y-auto custom-scrollbar">
                {configGroups.map((group, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      onSelectGroup(group);
                      setShowGroupDropdown(false);
                    }}
                    className={`w-full flex items-center justify-between px-6 py-3 text-left text-sm font-bold transition-all ${selectedGroup === group ? 'bg-indigo-50 text-indigo-600' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    <span className="uppercase tracking-wider">{group}</span>
                    {selectedGroup === group && (
                      <i className="fas fa-check text-indigo-500"></i>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button 
            onClick={onCreate}
            className="bg-indigo-600 text-white px-8 py-3 rounded-2xl font-bold hover:bg-indigo-700 shadow-2xl shadow-indigo-100 transition-all flex items-center gap-3 active:scale-95"
          >
            <i className="fas fa-plus-circle text-lg"></i>
            {t.new_config}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8">
        {filteredConfigs.map((config) => {
          // 使用原configs数组的索引
          const originalIndex = configs.indexOf(config);
          
          // 获取UP物品信息
          const upItemIds = config.rate_up_item_ids['5star'] || [];
          const upItems = upItemIds.map(id => items.find(i => i.id === id)).filter(Boolean) as GachaItem[];
          const upItemNames = upItems.map(i => i.name).join(', ');

          return (
            <div 
              key={originalIndex}
              onClick={() => setSelectedIdx(selectedIdx === originalIndex ? null : originalIndex)}
              className={`relative p-8 pt-10 rounded-[32px] border-4 transition-all cursor-pointer group bg-white ${selectedIdx === originalIndex ? 'border-white shadow-2xl scale-[1.01] z-10' : 'border-white hover:border-indigo-50 shadow-xl shadow-slate-200/50 hover:shadow-2xl'}`}
            >
              {/* Absolute Positioned Actions to avoid pushing content down */}
              <div className="absolute top-6 right-6 flex gap-2 z-20">
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(originalIndex);
                  }}
                  className="opacity-0 group-hover:opacity-100 w-9 h-9 flex items-center justify-center text-rose-500 bg-rose-50 rounded-xl transition-all hover:bg-rose-500 hover:text-white"
                >
                  <i className="fas fa-trash-can text-sm"></i>
                </button>
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(config);
                  }}
                  className="opacity-0 group-hover:opacity-100 w-9 h-9 flex items-center justify-center text-indigo-600 bg-indigo-50 rounded-xl transition-all hover:bg-indigo-600 hover:text-white"
                >
                  <i className="fas fa-pen-to-square text-sm"></i>
                </button>
              </div>
              
              <div className="space-y-1 mb-8">
                <h3 className="text-2xl font-black text-slate-800 truncate leading-tight">{config.name}</h3>
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[10px] font-black uppercase text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded tracking-tighter border border-indigo-100">
                    {config.config_group}
                  </span>
                </div>
              </div>

              <div className="space-y-5 p-6 bg-slate-50 rounded-2xl border border-slate-100 group-hover:bg-white group-hover:border-indigo-50 transition-colors">
                <div className="space-y-2.5">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-400">
                    <span>{language === 'zh' ? '5星 基础出率' : '5-Star Rate'}</span>
                    <span className="text-amber-500 font-black">{(config.probability_settings.base_5star_rate * 100).toFixed(2)}%</span>
                  </div>
                  <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
                    <div 
                      className="bg-amber-400 h-full rounded-full transition-all duration-700 ease-out" 
                      style={{ width: `${Math.min(config.probability_settings.base_5star_rate * 1000, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-200/50 space-y-1.5">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-slate-400">
                    <span>{language === 'zh' ? '5星 UP物品' : '5-Star UP Items'}</span>
                    <span className="text-indigo-500 font-black">{(config.probability_settings.up_5star_rate * 100).toFixed(0)}% UP</span>
                  </div>
                  <div className="text-xs font-bold text-slate-700 truncate" title={upItemNames}>
                    {upItemNames || (language === 'zh' ? '无' : 'None')}
                  </div>
                </div>
                
                <div className="flex justify-between items-center pt-3 border-t border-slate-200/50">
                  <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">{t.hard_pity}</span>
                  <span className="font-black text-slate-700 text-lg">{config.probability_progression['5star'].hard_pity_pull}</span>
                </div>
              </div>

              {selectedIdx === originalIndex && (
                <div className="absolute -top-3 -right-3 bg-indigo-600 text-white w-10 h-10 rounded-2xl flex items-center justify-center shadow-xl shadow-indigo-300 border-4 border-white animate-popIn">
                  <i className="fas fa-check"></i>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <style>{`
        .animate-fadeIn {
            animation: fadeIn 0.5s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes popIn {
          0% { transform: scale(0) rotate(-45deg); opacity: 0; }
          70% { transform: scale(1.2) rotate(10deg); opacity: 1; }
          100% { transform: scale(1) rotate(0); opacity: 1; }
        }
        .animate-popIn {
          animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        }
      `}</style>
    </div>
  );
};
