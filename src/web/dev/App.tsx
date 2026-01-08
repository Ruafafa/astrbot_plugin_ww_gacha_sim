
import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ConfigManager } from './components/ConfigManager';
import { ItemManager } from './components/ItemManager';
import { ConfigEditor } from './components/ConfigEditor';
import { ViewType, PoolConfig, GachaItem, Language, Rarity } from './types';
import { translations } from './i18n';

const DEFAULT_CONFIG: PoolConfig = {
  name: 'Standard Pool',
  config_group: 'default',
  probability_settings: {
    base_5star_rate: 0.008,
    base_4star_rate: 0.06,
    base_3star_rate: 0.932,
    up_5star_rate: 0.5,
    up_4star_rate: 0.5,
    four_star_character_rate: 0.5,
  },
  rate_up_item_ids: { '5star': [], '4star': [] },
  included_item_ids: { '5star': [], '4star': [], '3star': [] },
  probability_progression: {
    '5star': { hard_pity_pull: 80, hard_pity_rate: 1.0, soft_pity: [{ start_pull: 74, end_pull: 79, increment: 0.06 }] },
    '4star': { hard_pity_pull: 10, hard_pity_rate: 1.0, soft_pity: [] },
  },
};

// API调用函数
const fetchConfigs = async (): Promise<PoolConfig[]> => {
  try {
    const response = await fetch('/api/configs/list');
    const data = await response.json();
    if (data.success) {
      return data.configs.map((config: any) => {
        // 处理配置内容，确保字段名正确
        const content = config.content;
        // 如果返回的是configGroup，转换为config_group
        if (content.configGroup && !content.config_group) {
          content.config_group = content.configGroup;
          delete content.configGroup;
        }
        return {
          filename: config.filename,
          ...content
        };
      });
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch configs:', error);
    return [];
  }
};

const saveConfig = async (config: PoolConfig): Promise<boolean> => {
  try {
    // 生成新的文件名
    const newFilename = `${config.name.toLowerCase().replace(/\s+/g, '_')}.json`;
    
    if (config.filename && config.filename !== newFilename) {
      // 如果文件名发生变化，先删除原配置文件
      const deleteResponse = await fetch(`/api/configs/${config.filename}`, { method: 'DELETE' });
      const deleteData = await deleteResponse.json();
      
      if (!deleteData.success) {
        console.error('Failed to delete old config file:', config.filename);
        return false;
      }
    }
    
    // 保存新配置文件，移除filename字段
    const { filename, ...configWithoutFilename } = config;
    const response = await fetch(`/api/configs/${newFilename}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: configWithoutFilename })
    });
    const data = await response.json();
    return data.success;
  } catch (error) {
    console.error('Failed to save config:', error);
    return false;
  }
};

const deleteConfig = async (filename: string): Promise<boolean> => {
  try {
    const response = await fetch(`/api/configs/${filename}`, { method: 'DELETE' });
    const data = await response.json();
    return data.success;
  } catch (error) {
    console.error('Failed to delete config:', error);
    return false;
  }
};

const fetchItems = async (configGroup: string = 'default'): Promise<GachaItem[]> => {
  try {
    console.log('Fetching items for config group:', configGroup);
    const response = await fetch(`/api/db/items?config_group=${configGroup}`);
    const data = await response.json();
    console.log('Fetched items data:', data);
    if (data.success) {
      // 将后端返回的数据转换为前端使用的GachaItem类型，并确保物品唯一
      const uniqueItems: GachaItem[] = [];
      const seenIds = new Set<number>();
      
      data.items.forEach((item: any) => {
        if (!seenIds.has(item.id)) {
          seenIds.add(item.id);
          
          // 统一稀有度格式为{number}star
          let formattedRarity: Rarity;
          if (typeof item.rarity === 'number') {
            formattedRarity = `${item.rarity}star` as Rarity;
          } else if (item.rarity === '3' || item.rarity === '4' || item.rarity === '5') {
            formattedRarity = `${item.rarity}star` as Rarity;
          } else {
            formattedRarity = item.rarity as Rarity;
          }
          
          uniqueItems.push({
            id: item.id,
            name: item.name,
            rarity: formattedRarity,
            type: item.type,
            affiliated_type: item.affiliated_type, // 保留affiliated_type字段
            config_group: configGroup, // 使用请求的config_group作为config_group
            portrait_path: item.portrait_path
          });
        }
      });
      
      return uniqueItems;
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch items:', error);
    return [];
  }
};

const addItem = async (item: Omit<GachaItem, 'id'>): Promise<number | null> => {
  console.log('addItem function called with:', item);
  try {
    // 转换为后端需要的数据结构
    const backendItem = {
      name: item.name,
      rarity: item.rarity,
      type: item.type,
      affiliated_type: item.affiliated_type, // 使用前端的affiliated_type字段
      portrait_path: item.portrait_path,
      config_group: item.config_group // 传递config_group参数，用于确定表名
    };
    console.log('Converted to backend item:', backendItem);
    console.log('Sending POST request to /api/db/items');
    const response = await fetch('/api/db/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendItem)
    });
    console.log('Received response:', response);
    const data = await response.json();
    console.log('Response data:', data);
    if (data.success) {
      console.log('Item added successfully, ID:', data.item_id);
      return data.item_id;
    }
    console.log('Item addition failed:', data);
    return null;
  } catch (error) {
    console.error('Failed to add item:', error);
    return null;
  }
};

const addItems = async (items: Omit<GachaItem, 'id'>[]): Promise<boolean> => {
  console.log('addItems function called with:', items.length, 'items');
  try {
    // 转换为后端需要的数据结构
    const backendItems = items.map(item => ({
      name: item.name,
      rarity: item.rarity,
      type: item.type,
      affiliated_type: item.affiliated_type, // 使用前端的affiliated_type字段
      portrait_path: item.portrait_path,
      config_group: item.config_group // 传递config_group参数，用于确定表名
    }));
    
    console.log('Sending batch POST request to /api/db/items');
    const response = await fetch('/api/db/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendItems)
    });
    
    const data = await response.json();
    console.log('Response data:', data);
    if (data.success) {
      console.log('Batch items added successfully');
      return true;
    }
    console.log('Batch items addition failed:', data);
    return false;
  } catch (error) {
    console.error('Failed to add items:', error);
    return false;
  }
};

const updateItem = async (item: GachaItem): Promise<boolean> => {
  try {
    // 转换为后端需要的数据结构
    const backendItem = {
      id: item.id,
      name: item.name,
      rarity: item.rarity,
      type: item.type,
      affiliated_type: item.affiliated_type, // 使用前端的affiliated_type字段
      portrait_path: item.portrait_path,
      config_group: item.config_group // 传递config_group参数，用于确定表名
    };
    console.log('Updating item with:', backendItem);
    const response = await fetch('/api/db/items', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendItem)
    });
    const data = await response.json();
    console.log('Update response:', data);
    return data.success;
  } catch (error) {
    console.error('Failed to update item:', error);
    return false;
  }
};

const deleteItem = async (id: number, config_group: string): Promise<boolean> => {
  try {
    const response = await fetch(`/api/db/items?id=${id}&config_group=${config_group}`, { method: 'DELETE' });
    const data = await response.json();
    return data.success;
  } catch (error) {
    console.error('Failed to delete item:', error);
    return false;
  }
};

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<ViewType>('configs');
  const [language, setLanguage] = useState<Language>('zh');
  const [items, setItems] = useState<GachaItem[]>([]);
  const [configs, setConfigs] = useState<PoolConfig[]>([]);
  const [editingConfig, setEditingConfig] = useState<PoolConfig | null>(null);
  const [selectedConfigIdx, setSelectedConfigIdx] = useState<number | null>(null);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [notifications, setNotifications] = useState<{ id: number; text: string; type: 'success' | 'error' | 'info' }[]>([]);
  const [configToDeleteIdx, setConfigToDeleteIdx] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedConfigGroup, setSelectedConfigGroup] = useState<string>('default');

  const t = translations[language];

  const addNotification = (text: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, text, type }]);
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 3000);
  };

  // 获取所有配置组
  const configGroups = Array.from(new Set(configs.map(config => config.config_group)));

  // 初始化数据
  useEffect(() => {
    const initData = async () => {
      setLoading(true);
      try {
        const [fetchedConfigs, fetchedItems] = await Promise.all([
          fetchConfigs(),
          fetchItems(selectedConfigGroup)
        ]);
        setConfigs(fetchedConfigs);
        setItems(fetchedItems);
      } catch (error) {
        console.error('Failed to initialize data:', error);
        addNotification(language === 'zh' ? '数据加载失败' : 'Failed to load data', 'error');
      } finally {
        setLoading(false);
      }
    };
    initData();
  }, [language, selectedConfigGroup]);

  const handleCreateNewConfig = () => {
    setEditingConfig({
      ...DEFAULT_CONFIG,
      name: language === 'zh' ? '新卡池' : 'New Pool',
      config_group: selectedConfigGroup, // 使用当前选中的config_group
      rate_up_item_ids: { '5star': [], '4star': [] },
      included_item_ids: { '5star': [], '4star': [], '3star': [] },
    });
    setCurrentView('editor');
  };

  const handleEditConfig = (config: PoolConfig) => {
    setEditingConfig(config);
    // 更新selectedConfigGroup为当前编辑配置的config_group，确保显示正确的物品列表
    setSelectedConfigGroup(config.config_group);
    setCurrentView('editor');
  };

  const handleSaveConfig = async (config: PoolConfig) => {
    const success = await saveConfig(config);
    if (success) {
      // 重新获取配置列表
      const fetchedConfigs = await fetchConfigs();
      setConfigs(fetchedConfigs);
      addNotification(`${language === 'zh' ? '已保存配置' : 'Saved configuration'}: ${config.name}`);
      setCurrentView('configs');
    } else {
      addNotification(`${language === 'zh' ? '保存配置失败' : 'Failed to save configuration'}: ${config.name}`, 'error');
    }
  };

  const executeDeleteConfig = async () => {
    if (configToDeleteIdx === null) return;
    const config = configs[configToDeleteIdx];
    if (!config.filename) return;
    
    const success = await deleteConfig(config.filename);
    if (success) {
      // 重新获取配置列表
      const fetchedConfigs = await fetchConfigs();
      setConfigs(fetchedConfigs);
      addNotification(`${language === 'zh' ? '已删除配置' : 'Deleted configuration'}: ${config.name}`, 'info');
      setSelectedConfigIdx(null);
    } else {
      addNotification(`${language === 'zh' ? '删除配置失败' : 'Failed to delete configuration'}: ${config.name}`, 'error');
    }
    setConfigToDeleteIdx(null);
  };

  const handleAddItem = async (item: Omit<GachaItem, 'id'>) => {
    const itemId = await addItem(item);
    if (itemId) {
      // 重新获取物品列表
      const fetchedItems = await fetchItems(selectedConfigGroup);
      setItems(fetchedItems);
      // 取消成功提示，只保留失败提示
      // addNotification(`${language === 'zh' ? '已添加物品' : 'Added item'}: ${item.name}`);
    } else {
      addNotification(`${language === 'zh' ? '添加物品失败' : 'Failed to add item'}: ${item.name}`, 'error');
    }
  };

  const handleAddItems = async (items: Omit<GachaItem, 'id'>[]) => {
    const success = await addItems(items);
    if (success) {
      // 重新获取物品列表
      const fetchedItems = await fetchItems(selectedConfigGroup);
      setItems(fetchedItems);
      addNotification(`${language === 'zh' ? '已批量添加物品' : 'Batch added items'}: ${items.length}`);
    } else {
      addNotification(language === 'zh' ? '批量添加物品失败' : 'Failed to batch add items', 'error');
    }
  };

  const handleUpdateItem = async (updatedItem: GachaItem) => {
    const success = await updateItem(updatedItem);
    if (success) {
      // 重新获取物品列表
      const fetchedItems = await fetchItems(selectedConfigGroup);
      setItems(fetchedItems);
      addNotification(`${language === 'zh' ? '已更新物品' : 'Updated item'}: ${updatedItem.name}`);
    } else {
      addNotification(`${language === 'zh' ? '更新物品失败' : 'Failed to update item'}: ${updatedItem.name}`, 'error');
    }
  };

  const handleDeleteItem = async (id: number) => {
    // 查找要删除的物品，获取其config_group
    const itemToDelete = items.find(item => item.id === id);
    const config_group = itemToDelete?.config_group || selectedConfigGroup;
    
    const success = await deleteItem(id, config_group);
    if (success) {
      // 重新获取物品列表
      const fetchedItems = await fetchItems(selectedConfigGroup);
      setItems(fetchedItems);
      addNotification(language === 'zh' ? '已删除物品' : 'Deleted item', 'info');
    } else {
      addNotification(language === 'zh' ? '删除物品失败' : 'Failed to delete item', 'error');
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden font-sans">
      <Sidebar 
        expanded={sidebarExpanded} 
        setExpanded={setSidebarExpanded} 
        currentView={currentView} 
        setView={setCurrentView} 
        language={language}
      />
      
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative">
        <Header 
          language={language} 
          setLanguage={setLanguage} 
          onConfigDirChange={async (dir) => {
            // 配置目录变化时重新加载配置文件
            const fetchedConfigs = await fetchConfigs();
            setConfigs(fetchedConfigs);
            addNotification(language === 'zh' ? `配置目录已更新：${dir}` : `Config directory updated: ${dir}`);
          }} 
        />
        
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6 lg:p-10 custom-scrollbar scroll-smooth">
          <div className="max-w-[1600px] mx-auto">
            {currentView === 'configs' && (
              <ConfigManager 
                configs={configs}
                items={items} 
                onEdit={handleEditConfig} 
                onCreate={handleCreateNewConfig}
                onDelete={(idx) => setConfigToDeleteIdx(idx)}
                selectedIdx={selectedConfigIdx}
                setSelectedIdx={setSelectedConfigIdx}
                language={language}
                selectedGroup={selectedConfigGroup}
                onSelectGroup={setSelectedConfigGroup}
              />
            )}
            {currentView === 'items' && (
              <ItemManager 
                items={items} 
                onAdd={handleAddItem}
                onAddItems={handleAddItems}
                onUpdate={handleUpdateItem}
                onDelete={handleDeleteItem}
                language={language}
                configGroups={configGroups}
                selectedConfigGroup={selectedConfigGroup}
                onConfigGroupChange={setSelectedConfigGroup}
              />
            )}
            {currentView === 'editor' && (
              <ConfigEditor 
                config={editingConfig || DEFAULT_CONFIG} 
                items={items}
                onSave={handleSaveConfig}
                onCancel={() => setCurrentView('configs')}
                language={language}
              />
            )}
          </div>
        </main>
      </div>

      {/* Delete Confirmation Modal */}
      {configToDeleteIdx !== null && (
        <div className="fixed inset-0 z-[300] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-[40px] w-full max-w-md shadow-2xl overflow-hidden animate-notification border border-white/20 p-8 text-center">
            <div className="w-20 h-20 bg-rose-50 text-rose-500 rounded-3xl flex items-center justify-center mx-auto mb-6 text-3xl shadow-lg shadow-rose-100 border border-rose-100">
              <i className="fas fa-triangle-exclamation"></i>
            </div>
            <h3 className="text-2xl font-black text-slate-800 tracking-tight mb-3">{(t as any).confirm_delete_title}</h3>
            <p className="text-slate-500 font-medium mb-8 leading-relaxed">
              {(t as any).confirm_delete_msg}
            </p>
            <div className="flex flex-col gap-3">
              <button 
                onClick={executeDeleteConfig}
                className="w-full py-4 bg-rose-500 text-white rounded-2xl font-black hover:bg-rose-600 transition-all active:scale-95 shadow-xl shadow-rose-100"
              >
                {(t as any).confirm_delete_btn}
              </button>
              <button 
                onClick={() => setConfigToDeleteIdx(null)}
                className="w-full py-4 bg-slate-100 text-slate-600 rounded-2xl font-black hover:bg-slate-200 transition-all active:scale-95"
              >
                {(t as any).go_back}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-3">
        {notifications.map(n => (
          <div key={n.id} className={`px-5 py-3.5 rounded-xl shadow-2xl text-white transform transition-all animate-notification flex items-center gap-3 border border-white/10 ${
            n.type === 'success' ? 'bg-emerald-600' : n.type === 'error' ? 'bg-rose-600' : 'bg-sky-600'
          }`}>
            <i className={`fas ${n.type === 'success' ? 'fa-check-circle' : n.type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'} text-lg`}></i>
            <span className="font-semibold">{n.text}</span>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes notification-slide {
          0% { opacity: 0; transform: translateX(50px) scale(0.9); }
          100% { opacity: 1; transform: translateX(0) scale(1); }
        }
        .animate-notification {
          animation: notification-slide 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default App;
