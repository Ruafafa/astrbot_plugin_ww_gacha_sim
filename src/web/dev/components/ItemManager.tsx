
import React, { useState, useRef, useEffect } from 'react';
import { GachaItem, Rarity, Language } from '../types';
import { translations } from '../i18n';

interface ItemManagerProps {
  items: GachaItem[];
  onAdd: (item: Omit<GachaItem, 'id'>) => void;
  onAddItems?: (items: Omit<GachaItem, 'id'>[]) => void;
  onUpdate?: (item: GachaItem) => void; 
  onDelete: (id: number) => void;
  language: Language;
  configGroups: string[];
  selectedConfigGroup: string;
  onConfigGroupChange: (group: string) => void;
}

export const ItemManager: React.FC<ItemManagerProps> = ({ 
  items, 
  onAdd, 
  onAddItems,
  onUpdate, 
  onDelete, 
  language, 
  configGroups, 
  selectedConfigGroup, 
  onConfigGroupChange 
}) => {
  const t = translations[language];
  const [showModal, setShowModal] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<GachaItem | null>(null);
  const [showGroupDropdown, setShowGroupDropdown] = useState(false);
  const [showImportProgress, setShowImportProgress] = useState(false);
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0 });
  const [showPathModal, setShowPathModal] = useState(false);
  const [currentPath, setCurrentPath] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sortConfig, setSortConfig] = useState<{ key: keyof GachaItem | null; direction: 'asc' | 'desc' }>({ key: null, direction: 'asc' });
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // 根据当前选择的配置组过滤物品
  const filteredItems = items.filter(item => item.config_group === selectedConfigGroup);
  
  // 根据搜索词过滤物品
  const searchedItems = searchTerm 
    ? filteredItems.filter(item => 
        item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.affiliated_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.rarity.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : filteredItems;
  
  // 排序逻辑
  const sortedItems = [...searchedItems].sort((a, b) => {
    if (sortConfig.key === null) return 0;
    
    const aValue = a[sortConfig.key];
    const bValue = b[sortConfig.key];
    
    // 使用localeCompare确保中文按拼音排序
    const comparison = typeof aValue === 'string' && typeof bValue === 'string' 
      ? aValue.localeCompare(bValue, 'zh-CN', { sensitivity: 'base' })
      : aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    
    return sortConfig.direction === 'asc' ? comparison : -comparison;
  });
  
  // 处理排序点击
  const handleSort = (key: keyof GachaItem) => {
    setSortConfig(prev => {
      if (prev.key === key) {
        return {
          key,
          direction: prev.direction === 'asc' ? 'desc' : 'asc'
        };
      } else {
        return {
          key,
          direction: 'asc'
        };
      }
    });
  };
  
  const [formData, setFormData] = useState<Omit<GachaItem, 'id'>>({
    name: '',
    rarity: '4star',
    type: 'Character',
    affiliated_type: '',
    config_group: selectedConfigGroup,
    portrait_path: 'https://picsum.photos/400/400'
  });
  
  // 当selectedConfigGroup变化时，更新formData中的config_group
  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      config_group: selectedConfigGroup
    }));
  }, [selectedConfigGroup]);

  const getRarityUI = (rarity: Rarity) => {
    // 直接使用数据库中的{number}star格式稀有度
    switch (rarity) {
      case '5star': return { 
          color: 'text-amber-500', 
          bg: 'bg-amber-50', 
          border: 'border-amber-200', 
          accent: 'bg-amber-400',
          label: '★★★★★'
      };
      case '4star': return { 
          color: 'text-purple-500', 
          bg: 'bg-purple-50', 
          border: 'border-purple-200', 
          accent: 'bg-purple-400',
          label: '★★★★'
      };
      case '3star': return { 
          color: 'text-sky-500', 
          bg: 'bg-sky-50', 
          border: 'border-sky-200', 
          accent: 'bg-sky-400',
          label: '★★★'
      };
      default: return { 
          color: 'text-gray-500', 
          bg: 'bg-gray-50', 
          border: 'border-gray-200', 
          accent: 'bg-gray-400',
          label: '?'
      };
    }
  };

  const handleOpenAdd = () => {
    setEditingItem(null);
    setFormData({ name: '', rarity: '4star', type: 'Character', affiliated_type: '', config_group: selectedConfigGroup, portrait_path: 'https://picsum.photos/400/400' });
    setShowModal(true);
  };

  const handleOpenEdit = (item: GachaItem) => {
    setEditingItem(item);
    setFormData({ ...item });
    setShowModal(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingItem && onUpdate) {
      onUpdate({ ...formData, id: editingItem.id });
    } else {
      onAdd(formData);
    }
    setShowModal(false);
  };

  const handleShowFullPath = (path: string) => {
    setCurrentPath(path);
    setShowPathModal(true);
  };

  const getShortPath = (url?: string) => {
    if (!url) return '.../empty';
    try {
      const parts = url.split('/');
      const last = parts[parts.length - 1];
      return `.../${last.length > 20 ? last.substring(0, 18) + '...' : last}`;
    } catch {
      return '.../path';
    }
  };

  const handleExportCSV = () => {
    const headers = ['name', 'rarity', 'type', 'affiliated_type', 'portrait_path'];
    const rows = sortedItems.map(item => [
      item.name,
      item.rarity,
      item.type,
      item.affiliated_type,
      item.portrait_path
    ].map(field => `"${String(field || '').replace(/"/g, '""')}"`).join(','));
    
    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([new Uint8Array([0xEF, 0xBB, 0xBF]), csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `items_export_${selectedConfigGroup}_${Date.now()}.csv`);
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleImportCSV = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log('CSV import started');
    const file = e.target.files?.[0];
    if (!file) {
      console.log('No file selected');
      return;
    }
    console.log('Selected file:', file.name);

    const reader = new FileReader();
    reader.onload = async (event) => {
      console.log('File reading completed');
      const text = event.target?.result as string;
      const lines = text.split(/\r?\n/);
      if (lines.length < 2) {
        console.log('Not enough lines in CSV:', lines.length);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }

      const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
      console.log('CSV headers:', headers);
      const importedData = lines.slice(1).filter(line => line.trim()).map(line => {
        const values = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map(v => v.trim().replace(/^"|"$/g, '').replace(/""/g, '"'));
        const entry: any = {};
        headers.forEach((header, index) => {
          entry[header] = values[index];
        });
        
        // 支持将config_group表头映射到affiliated_type字段，确保兼容旧格式的CSV文件
        if (entry.config_group && !entry.affiliated_type) {
          entry.affiliated_type = entry.config_group;
        }
        
        return entry;
      });
      console.log('Parsed CSV data:', importedData);

      // 准备数据
      const itemsToAdd = importedData.map(item => {
        let rarity: Rarity = '4star'; // 默认值
        if (item.rarity) {
          const rarityStr = String(item.rarity).trim();
          if (['3', '4', '5', '3star', '4star', '5star'].includes(rarityStr)) {
            rarity = rarityStr as Rarity;
          }
        }
        
        return {
          name: item.name || 'Imported Item',
          rarity: rarity,
          type: item.type || 'Character',
          affiliated_type: item.affiliated_type || '',
          config_group: selectedConfigGroup, // 使用当前选中的配置组
          portrait_path: item.portrait_path || 'https://picsum.photos/400/400'
        };
      });

      // 显示进度弹窗
      setImportProgress({ current: 0, total: itemsToAdd.length });
      setShowImportProgress(true);

      try {
        // 导入前先清空表数据，实现覆盖功能
        console.log('Clearing existing items before import...');
        await fetch(`/api/db/items?config_group=${selectedConfigGroup}&clear_all=true`, {
          method: 'DELETE'
        });
        console.log('Existing items cleared successfully');

        if (onAddItems) {
            console.log('Using batch import...');
            // 批量添加
            await onAddItems(itemsToAdd);
            setImportProgress({ current: itemsToAdd.length, total: itemsToAdd.length });
        } else {
            console.log('Using sequential import...');
            // 逐个添加物品，显示进度
            for (let index = 0; index < itemsToAdd.length; index++) {
              const item = itemsToAdd[index];
              console.log(`Processing item ${index + 1}:`, item);
              
              // 添加物品
              await onAdd(item);
              
              // 更新进度
              setImportProgress({ current: index + 1, total: itemsToAdd.length });
              
              // 短暂延迟，让进度条有机会更新
              await new Promise(resolve => setTimeout(resolve, 10));
            }
        }
        
        console.log('CSV import completed');
      } catch (error) {
        console.error('CSV import failed:', error);
      } finally {
        // 关闭进度弹窗
        setShowImportProgress(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.onerror = (error) => {
      console.error('File reading error:', error);
      setShowImportProgress(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    };
    reader.readAsText(file);
    console.log('File reading started');
  };

  return (
    <div className="space-y-10 animate-fadeIn">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <h1 className="text-4xl font-black text-slate-800 tracking-tight">{t.items_library}</h1>
            <p className="text-slate-500 font-medium">{t.items_desc}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-50/50 border border-indigo-100 rounded-xl">
               <i className="fas fa-layer-group text-[10px] text-indigo-400"></i>
               <span className="text-[10px] font-black text-indigo-600 uppercase tracking-wider">{(t as any).current_group_hint}: <span className="text-indigo-800 font-black">{selectedConfigGroup.toUpperCase()}</span></span>
            </div>
            
            <div className="flex items-center gap-2">
              <button 
                onClick={handleExportCSV}
                className="px-4 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-500 text-[10px] font-black uppercase hover:bg-slate-50 hover:border-slate-300 transition-all flex items-center gap-2 shadow-sm"
              >
                <i className="fas fa-file-export"></i>
                {(t as any).export_csv}
              </button>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-500 text-[10px] font-black uppercase hover:bg-slate-50 hover:border-slate-300 transition-all flex items-center gap-2 shadow-sm"
              >
                <i className="fas fa-file-import"></i>
                {(t as any).import_csv}
              </button>
              <input type="file" accept=".csv" ref={fileInputRef} onChange={handleImportCSV} className="hidden" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 relative">
          {/* 搜索框 */}
          <div className="relative mr-3 flex-1 max-w-md">
            <i className="fas fa-search absolute left-4 top-1/2 transform -translate-y-1/2 text-slate-400 text-sm"></i>
            <input
              type="text"
              placeholder={language === 'zh' ? '搜索物品名称、类型、稀有度...' : 'Search items by name, type, rarity...'}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white border-2 border-slate-300 rounded-2xl focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none font-medium transition-all shadow-sm"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-4 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-slate-700 transition-colors"
              >
                <i className="fas fa-times-circle text-lg"></i>
              </button>
            )}
          </div>
          
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
                      onConfigGroupChange(group);
                      setShowGroupDropdown(false);
                    }}
                    className={`w-full flex items-center justify-between px-6 py-3 text-left text-sm font-bold transition-all ${selectedConfigGroup === group ? 'bg-indigo-50 text-indigo-600' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    <span className="uppercase tracking-wider">{group}</span>
                    {selectedConfigGroup === group && (
                      <i className="fas fa-check text-indigo-500"></i>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button 
            onClick={handleOpenAdd}
            className="bg-indigo-600 text-white px-8 py-3 rounded-2xl font-bold hover:bg-indigo-700 shadow-2xl shadow-indigo-100 transition-all flex items-center gap-3 active:scale-95"
          >
            <i className="fas fa-plus text-lg"></i>
            {t.register_item}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-[32px] overflow-hidden border border-slate-100 shadow-xl shadow-slate-200/50">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-slate-50/50 border-b-2 border-slate-200">
              <th className="px-8 py-5 text-left text-[11px] font-black text-slate-600 uppercase tracking-widest">
                <button 
                  onClick={() => handleSort('name')}
                  className="flex items-center gap-2 hover:text-indigo-600 transition-colors p-2 -m-2 rounded-lg hover:bg-indigo-50/50"
                >
                  {t.item_name}
                  {sortConfig.key === 'name' ? (
                    <i className={`fas fa-sort-${sortConfig.direction === 'asc' ? 'up' : 'down'} text-indigo-500 font-bold`}></i>
                  ) : (
                    <i className="fas fa-sort text-slate-400"></i>
                  )}
                </button>
              </th>
              <th className="px-8 py-5 text-left text-[11px] font-black text-slate-600 uppercase tracking-widest">
                <button 
                  onClick={() => handleSort('rarity')}
                  className="flex items-center gap-2 hover:text-indigo-600 transition-colors p-2 -m-2 rounded-lg hover:bg-indigo-50/50"
                >
                  {t.item_rarity}
                  {sortConfig.key === 'rarity' ? (
                    <i className={`fas fa-sort-${sortConfig.direction === 'asc' ? 'up' : 'down'} text-indigo-500 font-bold`}></i>
                  ) : (
                    <i className="fas fa-sort text-slate-400"></i>
                  )}
                </button>
              </th>
              <th className="px-8 py-5 text-left text-[11px] font-black text-slate-600 uppercase tracking-widest">
                <button 
                  onClick={() => handleSort('type')}
                  className="flex items-center gap-2 hover:text-indigo-600 transition-colors p-2 -m-2 rounded-lg hover:bg-indigo-50/50"
                >
                  {t.item_type}
                  {sortConfig.key === 'type' ? (
                    <i className={`fas fa-sort-${sortConfig.direction === 'asc' ? 'up' : 'down'} text-indigo-500 font-bold`}></i>
                  ) : (
                    <i className="fas fa-sort text-slate-400"></i>
                  )}
                </button>
              </th>
              <th className="px-8 py-5 text-left text-[11px] font-black text-slate-600 uppercase tracking-widest">
                <button 
                  onClick={() => handleSort('affiliated_type')}
                  className="flex items-center gap-2 hover:text-indigo-600 transition-colors p-2 -m-2 rounded-lg hover:bg-indigo-50/50"
                >
                  {language === 'zh' ? '附属类型' : 'Affiliated Type'}
                  {sortConfig.key === 'affiliated_type' ? (
                    <i className={`fas fa-sort-${sortConfig.direction === 'asc' ? 'up' : 'down'} text-indigo-500 font-bold`}></i>
                  ) : (
                    <i className="fas fa-sort text-slate-400"></i>
                  )}
                </button>
              </th>
              <th className="px-8 py-5 text-left text-[11px] font-black text-slate-600 uppercase tracking-widest">
                <button 
                  onClick={() => handleSort('portrait_path')}
                  className="flex items-center gap-2 hover:text-indigo-600 transition-colors p-2 -m-2 rounded-lg hover:bg-indigo-50/50"
                >
                  {t.item_illustration}
                  {sortConfig.key === 'portrait_path' ? (
                    <i className={`fas fa-sort-${sortConfig.direction === 'asc' ? 'up' : 'down'} text-indigo-500 font-bold`}></i>
                  ) : (
                    <i className="fas fa-sort text-slate-400"></i>
                  )}
                </button>
              </th>
              <th className="px-8 py-5 text-right text-[11px] font-black text-slate-400 uppercase tracking-widest">{t.item_actions}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sortedItems.map(item => {
              const ui = getRarityUI(item.rarity);
              return (
                <tr key={item.id} className="group hover:bg-slate-50 transition-colors">
                  <td className="px-8 py-6">
                    <span className="font-bold text-slate-800 text-lg">{item.name}</span>
                  </td>
                  <td className="px-8 py-6">
                    <span className={`px-3 py-1 rounded-lg text-[10px] font-black border-2 tracking-widest ${ui.bg} ${ui.color} ${ui.border}`}>
                      {ui.label}
                    </span>
                  </td>
                  <td className="px-8 py-6">
                    <span className="text-sm font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded-lg">
                      {item.type}
                    </span>
                  </td>
                  <td className="px-8 py-6">
                    <span className="text-sm font-bold text-amber-500 bg-amber-50 px-3 py-1 rounded-lg border border-amber-100">
                      {item.affiliated_type || '-'} {/* 只显示非空值，否则显示 '-' */}
                    </span>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded border border-slate-100 max-w-[120px] truncate">
                        {getShortPath(item.portrait_path)}
                      </span>
                      <button 
                        onClick={() => handleShowFullPath(item.portrait_path)}
                        title={language === 'zh' ? '显示完整路径' : 'Show full path'}
                        className={`w-8 h-8 rounded-lg border transition-all flex items-center justify-center shadow-sm active:scale-90 bg-white border-slate-200 text-slate-400 hover:text-indigo-600 hover:border-indigo-200`}
                      >
                        <i className="fas fa-eye text-[10px]"></i>
                      </button>
                    </div>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <div className="flex justify-end gap-2">
                      <button 
                        onClick={() => handleOpenEdit(item)}
                        className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-500 hover:bg-indigo-600 hover:text-white flex items-center justify-center transition-all shadow-sm active:scale-90"
                      >
                        <i className="fas fa-pen text-sm"></i>
                      </button>
                      <button 
                        onClick={() => onDelete(item.id)}
                        className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-100 text-rose-500 hover:bg-rose-500 hover:text-white flex items-center justify-center transition-all shadow-sm active:scale-90"
                      >
                        <i className="fas fa-trash-can text-sm"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sortedItems.length === 0 && (
          <div className="p-20 text-center">
            <div className="w-20 h-20 rounded-full bg-slate-50 flex items-center justify-center mx-auto mb-4 border-2 border-dashed border-slate-200">
              <i className="fas fa-box-open text-slate-300 text-2xl"></i>
            </div>
            <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">
              {searchTerm 
                ? (language === 'zh' ? '未找到匹配的物品' : 'No matching items found')
                : (language === 'zh' ? '暂无物品记录' : 'No items found')
              }
            </p>
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="mt-4 text-indigo-600 font-medium text-sm hover:underline"
              >
                {language === 'zh' ? '清除搜索' : 'Clear search'}
              </button>
            )}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-[40px] w-full max-w-xl shadow-2xl overflow-hidden animate-notification border border-white/20">
            <div className="p-8 pb-4 flex justify-between items-center">
              <div>
                <h3 className="text-3xl font-black text-slate-800 tracking-tight">
                  {editingItem ? (language === 'zh' ? '编辑物品' : 'Edit Item') : t.register_item}
                </h3>
                <p className="text-slate-500 font-medium">{t.items_desc}</p>
              </div>
              <button onClick={() => setShowModal(false)} className="w-12 h-12 rounded-full flex items-center justify-center text-slate-300 hover:text-slate-600 hover:bg-slate-100 transition-all"><i className="fas fa-times text-2xl"></i></button>
            </div>
            <form onSubmit={handleSubmit} className="p-8 space-y-6">
              <div className="space-y-2">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest px-1">{t.item_name}</label>
                <input 
                  required
                  type="text" 
                  value={formData.name} 
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none font-bold transition-all"
                />
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest px-1">{t.language === 'zh' ? '品质等级' : 'Quality Level'}</label>
                  <select 
                      value={formData.rarity} 
                      onChange={e => setFormData({...formData, rarity: e.target.value as any})}
                      className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl appearance-none font-bold outline-none cursor-pointer focus:border-indigo-500"
                  >
                      <option value="5star">5</option>
                      <option value="4star">4</option>
                      <option value="3star">3</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest px-1">{t.item_type}</label>
                  <select 
                      value={formData.type} 
                      onChange={e => setFormData({...formData, type: e.target.value})}
                      className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl appearance-none font-bold outline-none cursor-pointer focus:border-indigo-500"
                  >
                      <option value="Character">{t.hero}</option>
                      <option value="Weapon">{t.weapon}</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest px-1">
                  {language === 'zh' ? '附属类型' : 'Affiliated Type'}
                </label>
                <input 
                  type="text" 
                  value={formData.affiliated_type} 
                  onChange={e => setFormData({...formData, affiliated_type: e.target.value})}
                  placeholder={language === 'zh' ? '例如：限定角色' : 'e.g. Limited Character'}
                  className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none font-bold transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest px-1">{t.item_illustration} URL</label>
                <input 
                  type="text" 
                  value={formData.portrait_path} 
                  onChange={e => setFormData({...formData, portrait_path: e.target.value})}
                  className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none font-bold transition-all"
                />
              </div>
              <div className="pt-6 flex gap-4">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 px-6 py-4 rounded-2xl font-black text-slate-500 hover:bg-slate-50 transition-all">{t.dismiss}</button>
                <button type="submit" className="flex-1 px-6 py-4 bg-indigo-600 text-white rounded-2xl font-black hover:bg-indigo-700 shadow-xl shadow-indigo-100 transition-all active:scale-95">
                  {editingItem ? (language === 'zh' ? '保存更改' : 'Save Changes') : t.complete_reg}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Import Progress Modal */}
      {showImportProgress && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-[40px] w-full max-w-lg shadow-2xl overflow-hidden animate-notification border border-white/20">
            <div className="p-8 pb-4">
              <h3 className="text-3xl font-black text-slate-800 tracking-tight">
                {language === 'zh' ? '导入物品' : 'Import Items'}
              </h3>
              <p className="text-slate-500 font-medium mt-2">
                {language === 'zh' ? '正在导入物品，请稍候...' : 'Importing items, please wait...'}
              </p>
            </div>
            <div className="p-8 space-y-6">
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="font-black text-slate-600">{language === 'zh' ? '当前进度' : 'Progress'}</span>
                  <span className="font-black text-indigo-600">
                    {importProgress.current} / {importProgress.total}
                  </span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-4 overflow-hidden">
                  <div 
                    className="bg-indigo-600 h-full rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${(importProgress.current / importProgress.total) * 100}%` }}
                  ></div>
                </div>
                <div className="w-full bg-slate-50 rounded-xl p-4 border border-slate-100">
                  <div className="text-center text-sm font-black text-slate-500">
                    {Math.round((importProgress.current / importProgress.total) * 100)}%
                  </div>
                </div>
              </div>
              <div className="pt-4 text-center">
                <div className="inline-flex items-center gap-2 text-sm text-slate-500">
                  <i className="fas fa-circle-notch fa-spin text-indigo-500"></i>
                  <span>{language === 'zh' ? '导入中...' : 'Importing...'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Full Path Modal */}
      {showPathModal && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-[40px] w-full max-w-lg shadow-2xl overflow-hidden animate-notification border border-white/20">
            <div className="p-8 pb-4 flex justify-between items-center">
              <div>
                <h3 className="text-3xl font-black text-slate-800 tracking-tight">
                  {language === 'zh' ? '立绘完整路径' : 'Full Portrait Path'}
                </h3>
                <p className="text-slate-500 font-medium mt-2">
                  {language === 'zh' ? '以下是立绘的完整路径，可以复制使用' : 'Below is the full path of the portrait, you can copy it for use'}
                </p>
              </div>
              <button 
                onClick={() => setShowPathModal(false)}
                className="w-12 h-12 rounded-full flex items-center justify-center text-slate-300 hover:text-slate-600 hover:bg-slate-100 transition-all"
              >
                <i className="fas fa-times text-2xl"></i>
              </button>
            </div>
            <div className="p-8 space-y-6">
              <div className="space-y-4">
                <div className="w-full bg-slate-50 rounded-xl p-6 border-2 border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-mono text-slate-700 break-all">
                      {currentPath}
                    </span>
                    <button 
                      onClick={() => {
                        navigator.clipboard.writeText(currentPath);
                        // 可以添加一个复制成功的提示
                      }}
                      className="ml-4 px-3 py-1.5 bg-indigo-600 text-white text-xs font-black rounded-lg hover:bg-indigo-700 transition-all active:scale-95"
                      title={language === 'zh' ? '复制路径' : 'Copy Path'}
                    >
                      <i className="fas fa-copy mr-1"></i>
                      {language === 'zh' ? '复制' : 'Copy'}
                    </button>
                  </div>
                </div>
              </div>
              <div className="pt-4">
                <button 
                  onClick={() => setShowPathModal(false)}
                  className="w-full py-4 bg-slate-100 text-slate-700 rounded-2xl font-black hover:bg-slate-200 transition-all active:scale-95"
                >
                  {language === 'zh' ? '关闭' : 'Close'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
