
import React, { useState, useEffect, useRef } from 'react';
import { PoolConfig, GachaItem, SoftPityInterval, Rarity, Language } from '../types';
import { translations } from '../i18n';

interface ConfigEditorProps {
  config: PoolConfig;
  items: GachaItem[];
  onSave: (config: PoolConfig) => void;
  onCancel: () => void;
  language: Language;
}

export const ConfigEditor: React.FC<ConfigEditorProps> = ({ config, items, onSave, onCancel, language }) => {
  const t = translations[language];
  const [formData, setFormData] = useState<PoolConfig>({ ...config });
  const [activeDropdown, setActiveDropdown] = useState<Rarity | null>(null);
  const [searchQueries, setSearchQueries] = useState<Record<string, string>>({});
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle automatic calculation of 3-star rate
  useEffect(() => {
    const s5 = formData.probability_settings.base_5star_rate;
    const s4 = formData.probability_settings.base_4star_rate;
    const s3 = Math.max(0, 1 - s5 - s4);
    
    if (Math.abs(formData.probability_settings.base_3star_rate - s3) > 0.00001) {
      setFormData(prev => ({
        ...prev,
        probability_settings: {
          ...prev.probability_settings,
          base_3star_rate: s3
        }
      }));
    }
  }, [formData.probability_settings.base_5star_rate, formData.probability_settings.base_4star_rate]);

  const handleToggleItem = (rarity: Rarity, itemId: number, isRateUp: boolean = false) => {
    if (isRateUp && rarity === '3star') return; // No 3-star rate up
    
    const collectionKey = isRateUp ? 'rate_up_item_ids' : 'included_item_ids';
    // @ts-ignore - dynamic key access
    const current = formData[collectionKey][rarity];
    const isIncluded = current.includes(itemId);
    const updated = isIncluded ? current.filter((id: number) => id !== itemId) : [...current, itemId];
    
    setFormData({
      ...formData,
      [collectionKey]: { ...formData[collectionKey as keyof PoolConfig], [rarity]: updated }
    });
  };

  const handleSelectAll = (rarity: Rarity, isRateUp: boolean = false) => {
    if (isRateUp && rarity === '3star') return;

    const allIds = items.filter(i => i.rarity === rarity).map(i => i.id);
    const collectionKey = isRateUp ? 'rate_up_item_ids' : 'included_item_ids';
    
    setFormData({
      ...formData,
      [collectionKey]: { ...formData[collectionKey as keyof PoolConfig], [rarity]: allIds }
    });
  };

  const handleDeselectAll = (rarity: Rarity, isRateUp: boolean = false) => {
    if (isRateUp && rarity === '3star') return;

    const collectionKey = isRateUp ? 'rate_up_item_ids' : 'included_item_ids';

    setFormData({
      ...formData,
      [collectionKey]: { ...formData[collectionKey as keyof PoolConfig], [rarity]: [] }
    });
  };

  const addSoftPityInterval = (rarity: '5star' | '4star') => {
    const progression = { ...formData.probability_progression };
    progression[rarity].soft_pity.push({ start_pull: 74, end_pull: 89, increment: 0.06 });
    setFormData({ ...formData, probability_progression: progression });
  };

  const removeSoftPityInterval = (rarity: '5star' | '4star', index: number) => {
    const progression = { ...formData.probability_progression };
    progression[rarity].soft_pity = progression[rarity].soft_pity.filter((_, i) => i !== index);
    setFormData({ ...formData, probability_progression: progression });
  };

  const updateSoftPityField = (rarity: '5star' | '4star', index: number, field: keyof SoftPityInterval, value: number) => {
    const progression = { ...formData.probability_progression };
    progression[rarity].soft_pity[index] = { ...progression[rarity].soft_pity[index], [field]: value };
    setFormData({ ...formData, probability_progression: progression });
  };

  const updatePityBaseField = (rarity: '5star' | '4star', field: 'hard_pity_pull' | 'hard_pity_rate', value: number) => {
    const progression = { ...formData.probability_progression };
    progression[rarity] = { ...progression[rarity], [field]: value };
    setFormData({ ...formData, probability_progression: progression });
  };

  const updateRate = (rarity: '5' | '4', value: string) => {
    let num = parseFloat(value);
    if (isNaN(num)) num = 0;
    // Convert to decimal
    num = num / 100;
    
    const otherKey = rarity === '5' ? 'base_4star_rate' : 'base_5star_rate';
    const currentOther = formData.probability_settings[otherKey];
    
    // Ensure total rate doesn't exceed 1
    if (num + currentOther > 1) {
      num = 1 - currentOther;
    }
    
    setFormData({
      ...formData,
      probability_settings: {
        ...formData.probability_settings,
        [rarity === '5' ? 'base_5star_rate' : 'base_4star_rate']: num
      }
    });
  };

  const renderItemManager = (rarity: Rarity, isRateUp: boolean = false) => {
    const collectionKey = isRateUp ? 'rate_up_item_ids' : 'included_item_ids';
    // @ts-ignore
    const included = formData[collectionKey][rarity] || [];
    
    // 直接过滤出对应稀有度的物品
    const rarityItems = items.filter(i => i.rarity === rarity);
    const includedItems = rarityItems.filter(i => included.includes(i.id));
    const availableItems = rarityItems.filter(i => !included.includes(i.id));
    
    const searchKey = `${rarity}-${isRateUp ? 'up' : 'pool'}`;
    const searchQuery = searchQueries[searchKey] || '';
    
    // First filter by search query
    const filteredAvailableItems = availableItems.filter(item => 
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      item.id.toString().includes(searchQuery)
    );
    
    const rarityLabel = rarity === '5star' ? (language === 'zh' ? '5星' : '5-Star') : 
                        rarity === '4star' ? (language === 'zh' ? '4星' : '4-Star') : (language === 'zh' ? '3星' : '3-Star');
    const colorClass = rarity === '5star' ? 'text-amber-500' : 
                       rarity === '4star' ? 'text-purple-500' : 'text-sky-500';
    const indicatorClass = rarity === '5star' ? 'bg-amber-400' : 
                          rarity === '4star' ? 'bg-purple-400' : 'bg-sky-400';
    
    const dropdownId = searchKey;

    return (
      <div className="space-y-2" key={searchKey}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-0.5 h-3 rounded-full ${indicatorClass}`}></div>
            <h4 className={`text-[11px] font-black tracking-tight ${colorClass}`}>
              {rarityLabel}
            </h4>
            <span className="text-[8px] font-bold text-slate-400 bg-slate-100 px-1 py-0.5 rounded-sm">{included.length}</span>
          </div>
          <div className="flex gap-1.5">
            <button 
              onClick={() => handleSelectAll(rarity, isRateUp)}
              className="text-[9px] font-bold text-indigo-400 hover:text-indigo-600 transition-colors"
              title="全选"
            >
              全选
            </button>
            <span className="text-slate-200 text-[8px] self-center">|</span>
            <button 
              onClick={() => handleDeselectAll(rarity, isRateUp)}
              className="text-[9px] font-bold text-rose-300 hover:text-rose-500 transition-colors"
              title="取消全选"
            >
              取消
            </button>
          </div>
        </div>

        <div className="relative">
          <div className="flex flex-wrap gap-1 p-1.5 bg-slate-50 border border-slate-200 rounded-lg min-h-[38px] max-h-[80px] overflow-y-auto custom-scrollbar transition-all cursor-text hover:border-slate-300 focus-within:border-indigo-300 focus-within:shadow-sm">
            {includedItems.map(item => (
              <div key={item.id} className="flex items-center gap-1 bg-white border border-slate-200 pl-1.5 pr-1 py-0.5 rounded-md shadow-sm animate-fadeIn group">
                <span className="text-[10px] font-black text-slate-700">{item.name} <span className="text-[8px] text-slate-400 font-normal">({item.id})</span></span>
                <button 
                  onClick={() => handleToggleItem(rarity, item.id, isRateUp)}
                  className="text-slate-300 hover:text-rose-500 transition-colors p-0.5"
                  title="移除物品"
                >
                  <i className="fas fa-times text-[8px]"></i>
                </button>
              </div>
            ))}
            {includedItems.length === 0 && (
              <span className="text-[10px] text-slate-300 italic self-center px-1">未添加物品</span>
            )}
            
            {/* Inline search input */}
            <input
              type="text"
              value={searchQueries[searchKey] || ''}
              onChange={(e) => {
                setSearchQueries(prev => ({ ...prev, [searchKey]: e.target.value }));
                // Show dropdown when user starts typing
                if (activeDropdown !== dropdownId) setActiveDropdown(dropdownId as any);
              }}
              onFocus={() => setActiveDropdown(dropdownId as any)}
              placeholder="搜索物品..."
              className="flex-1 min-w-[120px] p-0.5 text-[10px] font-bold text-slate-700 bg-transparent border-none outline-none"
            />
          </div>
          
          {/* Dropdown for available items */}
          <div className="mt-1" ref={activeDropdown === dropdownId as any ? dropdownRef : null}>
            {activeDropdown === dropdownId as any && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl z-50 max-h-36 overflow-y-auto custom-scrollbar animate-notification">
                {filteredAvailableItems.length > 0 ? (
                  filteredAvailableItems.map(item => (
                    <button 
                      key={item.id}
                      onClick={() => { 
                        handleToggleItem(rarity, item.id, isRateUp); 
                        // Clear search after selection
                        setSearchQueries(prev => ({ ...prev, [searchKey]: '' }));
                      }}
                      className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-indigo-50 transition-colors border-b border-slate-50 last:border-0"
                    >
                      <span className="font-bold text-slate-700 text-[9px]">{item.name} <span className="text-slate-400 font-normal">({item.id})</span></span>
                      <i className="fas fa-plus text-[7px] text-indigo-400"></i>
                    </button>
                  ))
                ) : (
                  <div className="px-3 py-2 text-center text-[9px] text-slate-400 font-bold">
                    {searchQuery ? '未找到匹配物品' : '没有更多可用物品'}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderPitySettings = (rarity: '5star' | '4star') => {
    const progression = formData.probability_progression[rarity];
    const colorClass = rarity === '5star' ? 'amber' : 'purple';
    const label = rarity === '5star' ? '5星 保底策略' : '4星 保底策略';

    return (
      <div className={`p-5 bg-white border border-slate-100 rounded-[24px] space-y-4 shadow-sm`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-lg bg-${colorClass}-50 text-${colorClass}-500 flex items-center justify-center`}>
              <i className="fas fa-shield-halved text-xs"></i>
            </div>
            <h4 className="text-xs font-black text-slate-800 tracking-tight">{label}</h4>
          </div>
          <div className="flex gap-2">
            <div className="space-y-0.5">
              <label className="text-[7px] font-black text-slate-400 uppercase tracking-widest block text-center">硬保底</label>
              <input 
                type="number" 
                value={progression.hard_pity_pull}
                onChange={e => updatePityBaseField(rarity, 'hard_pity_pull', parseInt(e.target.value) || 0)}
                className="w-12 px-1 py-0.5 bg-slate-50 border border-slate-200 rounded-md text-[10px] font-black text-center focus:border-indigo-400 outline-none"
              />
            </div>
            <div className="space-y-0.5">
              <label className="text-[7px] font-black text-slate-400 uppercase tracking-widest block text-center">硬保底率%</label>
              <input 
                type="number" 
                step="0.01"
                value={progression.hard_pity_rate * 100}
                onChange={e => updatePityBaseField(rarity, 'hard_pity_rate', (parseFloat(e.target.value) || 0) / 100)}
                className="w-12 px-1 py-0.5 bg-slate-50 border border-slate-200 rounded-md text-[10px] font-black text-center focus:border-indigo-400 outline-none"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between border-b border-slate-50 pb-1.5">
             <h5 className="text-[8px] font-black text-slate-400 uppercase tracking-widest">软保底细调</h5>
             <button 
                onClick={() => addSoftPityInterval(rarity)}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-indigo-50 text-indigo-600 text-[8px] font-black hover:bg-indigo-100 transition-all`}
             >
                <i className="fas fa-plus-circle"></i>
                添加
             </button>
          </div>
          
          {progression.soft_pity.length === 0 ? (
            <div className="py-4 text-center bg-slate-50/30 border border-dashed border-slate-100 rounded-xl">
              <p className="text-[8px] font-bold text-slate-300 italic">尚未配置软保底</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {progression.soft_pity.map((interval, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-1.5 items-center bg-slate-50/30 p-1.5 rounded-xl border border-slate-100 animate-fadeIn">
                  <div className="col-span-3">
                    <input 
                      type="number" 
                      value={interval.start_pull}
                      onChange={e => updateSoftPityField(rarity, idx, 'start_pull', parseInt(e.target.value) || 0)}
                      className="w-full px-1 py-0.5 bg-white border border-slate-200 rounded-md text-[9px] font-bold text-center"
                    />
                  </div>
                  <div className="col-span-1 text-center text-[9px] text-slate-200 font-bold">~</div>
                  <div className="col-span-3">
                    <input 
                      type="number" 
                      value={interval.end_pull}
                      onChange={e => updateSoftPityField(rarity, idx, 'end_pull', parseInt(e.target.value) || 0)}
                      className="w-full px-1 py-0.5 bg-white border border-slate-200 rounded-md text-[9px] font-bold text-center"
                    />
                  </div>
                  <div className="col-span-3">
                    <div className="relative">
                      <input 
                        type="number" 
                        step="0.01"
                        value={interval.increment * 100}
                        onChange={e => updateSoftPityField(rarity, idx, 'increment', (parseFloat(e.target.value) || 0) / 100)}
                        className="w-full pl-1 pr-3 py-0.5 bg-white border border-slate-200 rounded-md text-[9px] font-bold text-center"
                      />
                      <span className="absolute right-0.5 top-1/2 -translate-y-1/2 text-[7px] font-black text-slate-200">%</span>
                    </div>
                  </div>
                  <div className="col-span-2">
                    <button 
                      onClick={() => removeSoftPityInterval(rarity, idx)}
                      className="w-full py-0.5 rounded-md text-slate-300 hover:text-rose-500 transition-all text-[9px]"
                    >
                      <i className="fas fa-trash-can"></i>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* Header Area */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white text-lg shadow-md border-2 border-white shrink-0">
            <i className="fas fa-edit"></i>
          </div>
          <div className="flex items-center gap-6 flex-wrap">
            <h1 className="text-xl font-black text-slate-800 tracking-tight">{t.edit_config}</h1>
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-slate-400 font-semibold">{t.pool_name}:</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="px-3 py-1 bg-white border border-slate-200 rounded-lg text-sm font-bold text-indigo-600 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                placeholder={t.enter_pool_name}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-slate-400 font-semibold">{t.config_group}:</label>
              <input
                type="text"
                value={formData.config_group}
                onChange={(e) => setFormData({ ...formData, config_group: e.target.value })}
                className="px-3 py-1 bg-white border border-slate-200 rounded-lg text-sm font-bold text-indigo-600 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                placeholder="default"
              />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="px-4 py-1.5 rounded-lg font-bold text-slate-400 bg-white hover:bg-slate-50 transition-all border border-slate-200 shadow-sm text-[11px]">
            {t.cancel}
          </button>
          <button onClick={() => onSave(formData)} className="px-5 py-1.5 rounded-lg font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-md transition-all active:scale-95 flex items-center gap-1.5 text-[11px]">
            <i className="fas fa-save text-[9px]"></i>
            {t.save_changes}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-[32px] border border-slate-200 shadow-xl overflow-hidden">
        {/* TOP: Compact Item Selection */}
        <div className="p-5 border-b border-slate-100 space-y-4 bg-slate-50/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-sm">
              <i className="fas fa-shapes text-xs"></i>
            </div>
            <h3 className="text-sm font-black text-slate-800 tracking-tight">{t.pool_selection}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {renderItemManager('5star')}
            {renderItemManager('4star')}
            {renderItemManager('3star')}
          </div>
        </div>

        {/* UP Item Selection */}
        <div className="p-5 border-b border-slate-100 space-y-4 bg-slate-50/10">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-pink-600 text-white flex items-center justify-center shadow-sm">
              <i className="fas fa-star text-xs"></i>
            </div>
            <h3 className="text-sm font-black text-slate-800 tracking-tight">UP 物品选择</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {renderItemManager('5star', true)}
            {renderItemManager('4star', true)}
          </div>
        </div>

        {/* BOTTOM: Numerical Settings */}
        <div className="p-6 space-y-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Column: Probabilities */}
            <div className="lg:col-span-8 space-y-6">
              <h3 className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2 px-1">
                <i className="fas fa-chart-pie text-indigo-500"></i>
                基础出率配置
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="bg-slate-50/30 p-5 rounded-3xl border border-slate-100 space-y-3">
                  <label className="flex items-center justify-between text-[9px] font-black text-slate-400 uppercase tracking-widest">
                    <span>{t.five_star_rate}</span>
                    <span className="text-amber-500 font-black">{(formData.probability_settings.base_5star_rate * 100).toFixed(2)}%</span>
                  </label>
                  <div className="relative">
                    <input type="number" step="0.01" value={(formData.probability_settings.base_5star_rate * 100).toFixed(2)} onChange={e => updateRate('5', e.target.value)} className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl outline-none font-black text-base shadow-sm" />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-200 font-black text-sm">%</div>
                  </div>
                  <input type="range" min="0" max="100" step="0.01" value={(formData.probability_settings.base_5star_rate * 100).toFixed(2)} onChange={e => updateRate('5', e.target.value)} className="w-full h-1 bg-slate-200 rounded-full appearance-none cursor-pointer accent-amber-500" />
                </div>
                <div className="bg-slate-50/30 p-5 rounded-3xl border border-slate-100 space-y-3">
                  <label className="flex items-center justify-between text-[9px] font-black text-slate-400 uppercase tracking-widest">
                    <span>{t.four_star_rate}</span>
                    <span className="text-purple-500 font-black">{(formData.probability_settings.base_4star_rate * 100).toFixed(2)}%</span>
                  </label>
                  <div className="relative">
                    <input type="number" step="0.01" value={(formData.probability_settings.base_4star_rate * 100).toFixed(2)} onChange={e => updateRate('4', e.target.value)} className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl outline-none font-black text-base shadow-sm" />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-200 font-black text-sm">%</div>
                  </div>
                  <input type="range" min="0" max="100" step="0.01" value={(formData.probability_settings.base_4star_rate * 100).toFixed(2)} onChange={e => updateRate('4', e.target.value)} className="w-full h-1 bg-slate-200 rounded-full appearance-none cursor-pointer accent-purple-500" />
                </div>
                <div className="md:col-span-2 bg-indigo-600 p-6 rounded-[24px] flex flex-col md:flex-row md:items-center justify-between gap-3 text-white">
                  <div className="space-y-0.5">
                    <label className="text-[9px] font-black text-indigo-100 uppercase tracking-[0.2em] opacity-80">3星 基础出率 (动态平衡)</label>
                    <p className="text-indigo-50 font-bold text-[10px] opacity-60">自动推导 100% - 5星 - 4星，闭环逻辑</p>
                  </div>
                  <div className="text-4xl font-black tracking-tighter">
                    {(formData.probability_settings.base_3star_rate * 100).toFixed(2)}<span className="text-lg ml-1 opacity-50">%</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                 {renderPitySettings('5star')}
                 {renderPitySettings('4star')}
              </div>
            </div>

            {/* Right Column: Weights & Other Settings */}
            <div className="lg:col-span-4 space-y-6">
              <section className="bg-white rounded-[32px] p-7 border border-slate-100 space-y-6 shadow-sm">
                 <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
                       <i className="fas fa-bullseye text-lg"></i>
                    </div>
                    <h3 className="text-base font-black tracking-tight text-slate-800">UP权重设置</h3>
                 </div>
                 <div className="space-y-6">
                    <div className="space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">5星 UP {t.win_ratio_5}</span>
                        <span className="text-xl font-black text-indigo-600">{(formData.probability_settings.up_5star_rate * 100).toFixed(0)}%</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.01" value={formData.probability_settings.up_5star_rate} onChange={e => setFormData({...formData, probability_settings: {...formData.probability_settings, up_5star_rate: parseFloat(e.target.value)}})} className="w-full h-1.5 bg-slate-100 rounded-full appearance-none cursor-pointer accent-indigo-600" />
                    </div>
                    <div className="space-y-2.5 pt-4 border-t border-slate-50">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-400">4星 UP {t.win_ratio_4}</span>
                        <span className="text-xl font-black text-purple-600">{(formData.probability_settings.up_4star_rate * 100).toFixed(0)}%</span>
                      </div>
                      <input type="range" min="0" max="1" step="0.01" value={formData.probability_settings.up_4star_rate} onChange={e => setFormData({...formData, probability_settings: {...formData.probability_settings, up_4star_rate: parseFloat(e.target.value)}})} className="w-full h-1.5 bg-slate-100 rounded-full appearance-none cursor-pointer accent-purple-600" />
                    </div>
                 </div>
              </section>

              {/* Other Settings Section - Moved here from left column */}
              <section className="space-y-4">
                 <h3 className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2 px-1">
                  <i className="fas fa-screwdriver-wrench text-indigo-500"></i>
                  {t.other_settings}
                </h3>
                <div className="bg-white border border-slate-100 p-6 rounded-[32px] shadow-sm space-y-4">
                  <div className="space-y-1">
                    <span className="text-sm font-black text-slate-700 tracking-tight">{t.four_star_char_rate}</span>
                    <p className="text-[10px] text-slate-400 font-bold">配置 4星 触发时角色获取权重比例</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <input 
                      type="range" 
                      min="0" 
                      max="1" 
                      step="0.01" 
                      value={formData.probability_settings.four_star_character_rate} 
                      onChange={e => setFormData({...formData, probability_settings: {...formData.probability_settings, four_star_character_rate: parseFloat(e.target.value)}})} 
                      className="flex-1 h-1.5 bg-slate-100 rounded-full appearance-none cursor-pointer accent-indigo-600" 
                    />
                    <div className="w-12 text-right">
                      <span className="text-sm font-black text-indigo-600">{(formData.probability_settings.four_star_character_rate * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                </div>
              </section>

              <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
                <p className="text-[9px] font-bold text-slate-400 leading-relaxed italic">
                  * 说明: UP权重决定了当该稀有度触发时，属于UP列表中物品的概率分布。其余概率将分配给非UP物品。
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
