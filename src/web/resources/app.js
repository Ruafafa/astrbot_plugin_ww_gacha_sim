// 卡池管理应用
class BannerManager {
    constructor() {
        this.banners = [];
        this.currentBannerId = null;
        this.allItems = []; // Store all items from CSV
        
        // UP items state
        this.selected5StarItems = new Set(); // Track selected 5-star items
        this.selected4StarItems = new Set(); // Track selected 4-star items
        
        // Included items state
        this.included5StarItems = new Set(); // Track included 5-star items
        this.included4StarItems = new Set(); // Track included 4-star items
        this.included3StarItems = new Set(); // Track included 3-star items
        
        this.initEventListeners();
        this.loadItemsFromAPI(); // Load items from API first
        this.loadBanners(); // Load from backend
    }

    // Load items from API using ItemDataManager
    async loadItemsFromAPI() {
        try {
            const response = await fetch('/api/items');
            const result = await response.json();
            
            if (result.success) {
                this.allItems = result.items;
            } else {
                console.error('Failed to load items:', result.error);
                alert('加载物品数据失败: ' + result.error);
            }
        } catch (error) {
            console.error('Error loading items from API:', error);
            alert('加载物品数据时发生错误: ' + error.message);
        }
    }

    // Load banners from backend API
    async loadBanners() {
        try {
            const response = await fetch('/api/banners');
            const result = await response.json();
            
            if (result.success) {
                this.banners = result.banners;
                this.renderBannerList();
            } else {
                console.error('Failed to load banners:', result.error);
                alert('加载卡池失败: ' + result.error);
            }
        } catch (error) {
            console.error('Error loading banners:', error);
            alert('加载卡池时发生错误: ' + error.message);
        }
    }

    // Initialize event listeners
    initEventListeners() {
        // Form submission
        document.getElementById('bannerForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveBanner();
        });

        // New banner button
        document.getElementById('newBannerBtn').addEventListener('click', () => {
            this.showForm();
        });

        // Cancel form button
        document.getElementById('cancelFormBtn').addEventListener('click', () => {
            this.hideForm();
        });

        // Add soft pity button
        document.getElementById('addSoftPityBtn').addEventListener('click', () => {
            this.addSoftPityEntry();
        });

        // Add event listeners for automatic 3-star rate calculation and slider controls
        const base5StarRateInput = document.getElementById('base5StarRate');
        const base4StarRateInput = document.getElementById('base4StarRate');
        const base3StarRateInput = document.getElementById('base3StarRate');
        const base5StarRateSlider = document.getElementById('base5StarRateSlider');
        const base4StarRateSlider = document.getElementById('base4StarRateSlider');
        const base5StarRateDisplay = document.getElementById('base5StarRateDisplay');
        const base4StarRateDisplay = document.getElementById('base4StarRateDisplay');
        const base3StarRateDisplay = document.getElementById('base3StarRateDisplay');

        const calculate3StarRate = () => {
            const base5Rate = parseFloat(base5StarRateInput.value) || 0;
            const base4Rate = parseFloat(base4StarRateInput.value) || 0;
            const calculated3StarRate = Math.max(0, Math.min(1, 1 - base5Rate - base4Rate)); // Ensure value is between 0 and 1
            base3StarRateInput.value = calculated3StarRate.toFixed(4); // Fixed precision to 4 decimal places
            base3StarRateDisplay.textContent = calculated3StarRate.toFixed(4);
        };

        // Update inputs when sliders change
        const update5StarRate = (value) => {
            base5StarRateInput.value = value;
            base5StarRateDisplay.textContent = value;
            calculate3StarRate();
        };

        const update4StarRate = (value) => {
            base4StarRateInput.value = value;
            base4StarRateDisplay.textContent = value;
            calculate3StarRate();
        };

        // Add event listeners for sliders
        base5StarRateSlider.addEventListener('input', (e) => {
            update5StarRate(e.target.value);
        });

        base4StarRateSlider.addEventListener('input', (e) => {
            update4StarRate(e.target.value);
        });

        // Add event listeners for direct input (to update sliders and display)
        base5StarRateInput.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            if (!isNaN(value)) {
                base5StarRateSlider.value = value;
                base5StarRateDisplay.textContent = value.toFixed(6);
                calculate3StarRate();
            }
        });

        base4StarRateInput.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            if (!isNaN(value)) {
                base4StarRateSlider.value = value;
                base4StarRateDisplay.textContent = value.toFixed(6);
                calculate3StarRate();
            }
        });

        // Initialize the 3-star rate calculation on page load
        calculate3StarRate();
        
        // Initialize UP items selection event listeners
        this.initUpItemsEventListeners();
    }
    
    // Initialize UP items selection event listeners
    initUpItemsEventListeners() {
        // Search functionality for 5-star items
        const up5StarSearch = document.getElementById('up5StarSearch');
        up5StarSearch.addEventListener('input', (e) => {
            this.filterAvailableItems(5, e.target.value);
            // Auto-expand dropdown when typing
            this.toggleDropdown(5, true);
        });
        
        // Focus event to expand dropdown when clicking in the search box
        up5StarSearch.addEventListener('focus', () => {
            this.toggleDropdown(5, true);
            this.filterAvailableItems(5, up5StarSearch.value);
        });
        
        // Blur event to eventually collapse dropdown (with delay to allow clicks)
        up5StarSearch.addEventListener('blur', () => {
            setTimeout(() => {
                // Only close if the dropdown doesn't have focus
                if (!document.getElementById('up5StarDropdown').matches(':hover')) {
                    this.toggleDropdown(5, false);
                }
            }, 200); // Delay to allow dropdown item clicks
        });
        
        // Click event for dropdown button to toggle visibility
        const up5StarDropdownBtn = document.getElementById('up5StarDropdownBtn');
        up5StarDropdownBtn.addEventListener('click', () => {
            const dropdown = document.getElementById('up5StarDropdown');
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('show');
            this.toggleDropdown(5, !isVisible);
        });
        
        // Prevent dropdown from closing when clicking inside it
        document.getElementById('up5StarDropdown').addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
        
        // Search functionality for 4-star items
        const up4StarSearch = document.getElementById('up4StarSearch');
        up4StarSearch.addEventListener('input', (e) => {
            this.filterAvailableItems(4, e.target.value);
            // Auto-expand dropdown when typing
            this.toggleDropdown(4, true);
        });
        
        // Focus event to expand dropdown when clicking in the search box
        up4StarSearch.addEventListener('focus', () => {
            this.toggleDropdown(4, true);
            this.filterAvailableItems(4, up4StarSearch.value);
        });
        
        // Blur event to eventually collapse dropdown (with delay to allow clicks)
        up4StarSearch.addEventListener('blur', () => {
            setTimeout(() => {
                // Only close if the dropdown doesn't have focus
                if (!document.getElementById('up4StarDropdown').matches(':hover')) {
                    this.toggleDropdown(4, false);
                }
            }, 200); // Delay to allow dropdown item clicks
        });
        
        // Click event for dropdown button to toggle visibility
        const up4StarDropdownBtn = document.getElementById('up4StarDropdownBtn');
        up4StarDropdownBtn.addEventListener('click', () => {
            const dropdown = document.getElementById('up4StarDropdown');
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('show');
            this.toggleDropdown(4, !isVisible);
        });
        
        // Prevent dropdown from closing when clicking inside it
        document.getElementById('up4StarDropdown').addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
        
        // Initialize included items event listeners
        this.initIncludedItemsEventListeners();
    }
    
    // Initialize included items event listeners
    initIncludedItemsEventListeners() {
        // 5星包含物品 event listeners
        const included5StarSearch = document.getElementById('included5StarSearch');
        included5StarSearch.addEventListener('input', (e) => {
            this.filterIncludedItems(5, e.target.value);
            this.toggleDropdown('included5Star', true);
        });
        
        included5StarSearch.addEventListener('focus', () => {
            this.toggleDropdown('included5Star', true);
            this.filterIncludedItems(5, included5StarSearch.value);
        });
        
        included5StarSearch.addEventListener('blur', () => {
            setTimeout(() => {
                if (!document.getElementById('included5StarDropdown').matches(':hover')) {
                    this.toggleDropdown('included5Star', false);
                }
            }, 200);
        });
        
        const included5StarDropdownBtn = document.getElementById('included5StarDropdownBtn');
        included5StarDropdownBtn.addEventListener('click', () => {
            const dropdown = document.getElementById('included5StarDropdown');
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('show');
            this.toggleDropdown('included5Star', !isVisible);
        });
        
        document.getElementById('included5StarDropdown').addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
        
        // 5星包含物品 select all/clear all
        document.getElementById('selectAll5Star').addEventListener('click', () => {
            this.selectAllIncludedItems(5);
        });
        
        document.getElementById('clearAll5Star').addEventListener('click', () => {
            this.clearAllIncludedItems(5);
        });
        
        // 4星包含物品 event listeners
        const included4StarSearch = document.getElementById('included4StarSearch');
        included4StarSearch.addEventListener('input', (e) => {
            this.filterIncludedItems(4, e.target.value);
            this.toggleDropdown('included4Star', true);
        });
        
        included4StarSearch.addEventListener('focus', () => {
            this.toggleDropdown('included4Star', true);
            this.filterIncludedItems(4, included4StarSearch.value);
        });
        
        included4StarSearch.addEventListener('blur', () => {
            setTimeout(() => {
                if (!document.getElementById('included4StarDropdown').matches(':hover')) {
                    this.toggleDropdown('included4Star', false);
                }
            }, 200);
        });
        
        const included4StarDropdownBtn = document.getElementById('included4StarDropdownBtn');
        included4StarDropdownBtn.addEventListener('click', () => {
            const dropdown = document.getElementById('included4StarDropdown');
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('show');
            this.toggleDropdown('included4Star', !isVisible);
        });
        
        document.getElementById('included4StarDropdown').addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
        
        // 4星包含物品 select all/clear all
        document.getElementById('selectAll4Star').addEventListener('click', () => {
            this.selectAllIncludedItems(4);
        });
        
        document.getElementById('clearAll4Star').addEventListener('click', () => {
            this.clearAllIncludedItems(4);
        });
        
        // 3星包含物品 event listeners
        const included3StarSearch = document.getElementById('included3StarSearch');
        included3StarSearch.addEventListener('input', (e) => {
            this.filterIncludedItems(3, e.target.value);
            this.toggleDropdown('included3Star', true);
        });
        
        included3StarSearch.addEventListener('focus', () => {
            this.toggleDropdown('included3Star', true);
            this.filterIncludedItems(3, included3StarSearch.value);
        });
        
        included3StarSearch.addEventListener('blur', () => {
            setTimeout(() => {
                if (!document.getElementById('included3StarDropdown').matches(':hover')) {
                    this.toggleDropdown('included3Star', false);
                }
            }, 200);
        });
        
        const included3StarDropdownBtn = document.getElementById('included3StarDropdownBtn');
        included3StarDropdownBtn.addEventListener('click', () => {
            const dropdown = document.getElementById('included3StarDropdown');
            const isVisible = dropdown.style.display === 'block' || dropdown.classList.contains('show');
            this.toggleDropdown('included3Star', !isVisible);
        });
        
        document.getElementById('included3StarDropdown').addEventListener('mousedown', (e) => {
            e.stopPropagation();
        });
        
        // 3星包含物品 select all/clear all
        document.getElementById('selectAll3Star').addEventListener('click', () => {
            this.selectAllIncludedItems(3);
            // No need to refresh UP items for 3-star since UP items are only 4 and 5 star
        });
        
        document.getElementById('clearAll3Star').addEventListener('click', () => {
            this.clearAllIncludedItems(3);
            // No need to refresh UP items for 3-star since UP items are only 4 and 5 star
        });
        
        // Add listeners to refresh UP items dropdowns when included items change
        this.addIncludedItemsChangeListeners();
    }
    
    // Add event listeners to refresh UP items dropdowns when included items change
    addIncludedItemsChangeListeners() {
        // Add refresh listeners to all included items buttons and search inputs
        const included5StarSearch = document.getElementById('included5StarSearch');
        const included4StarSearch = document.getElementById('included4StarSearch');
        
        // When included items search changes, refresh UP items dropdowns
        included5StarSearch.addEventListener('input', () => {
            this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
        });
        
        included4StarSearch.addEventListener('input', () => {
            this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
        });
        
        // When included items dropdown is closed, refresh UP items dropdowns and validate
        const included5StarDropdown = document.getElementById('included5StarDropdown');
        const included4StarDropdown = document.getElementById('included4StarDropdown');
        
        included5StarDropdown.addEventListener('hidden.bs.dropdown', () => {
            this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
            this.validateUpItems();
        });
        
        included4StarDropdown.addEventListener('hidden.bs.dropdown', () => {
            this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
            this.validateUpItems();
        });
        
        // Add validation when any included item is clicked
        const included5StarDropdownItems = document.getElementById('included5StarDropdown');
        const included4StarDropdownItems = document.getElementById('included4StarDropdown');
        
        included5StarDropdownItems.addEventListener('click', () => {
            // Validate after a short delay to allow the click to process
            setTimeout(() => {
                this.validateUpItems();
            }, 100);
        });
        
        included4StarDropdownItems.addEventListener('click', () => {
            // Validate after a short delay to allow the click to process
            setTimeout(() => {
                this.validateUpItems();
            }, 100);
        });
    }
    
    // Filter and display available items based on search term and rarity
    filterAvailableItems(rarity, searchTerm) {
        let items = this.allItems.filter(item => item.rarity === rarity);
        
        // Filter items based on what's currently included
        if (rarity === 5) {
            items = items.filter(item => this.included5StarItems.has(item.name));
        } else {
            items = items.filter(item => this.included4StarItems.has(item.name));
        }
        
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            items = items.filter(item => 
                item.name.toLowerCase().includes(term) ||
                item.type.toLowerCase().includes(term) ||
                item.affiliated_type.toLowerCase().includes(term)
            );
        }
        
        // Filter out already selected items
        items = items.filter(item => {
            if (rarity === 5) {
                return !this.selected5StarItems.has(item.name);
            } else {
                return !this.selected4StarItems.has(item.name);
            }
        });
        
        this.renderAvailableItemsDropdown(items, rarity);
    }
    
    // Toggle dropdown visibility
    toggleDropdown(type, show) {
        let dropdownId, btnId;
        
        if (typeof type === 'number') {
            // UP items dropdowns (type is rarity: 5 or 4)
            dropdownId = type === 5 ? 'up5StarDropdown' : 'up4StarDropdown';
            btnId = type === 5 ? 'up5StarDropdownBtn' : 'up4StarDropdownBtn';
        } else {
            // Included items dropdowns (type is string like 'included5Star')
            dropdownId = `${type}Dropdown`;
            btnId = `${type}DropdownBtn`;
        }
        
        const dropdown = document.getElementById(dropdownId);
        const dropdownBtn = document.getElementById(btnId);
        
        if (show) {
            dropdown.classList.add('show');
            dropdown.style.display = 'block';
            dropdownBtn.classList.add('show');
        } else {
            dropdown.classList.remove('show');
            dropdown.style.display = 'none';
            dropdownBtn.classList.remove('show');
        }
    }
    
    // Render available items in the dropdown
    renderAvailableItemsDropdown(items, rarity) {
        const dropdownId = rarity === 5 ? 'up5StarDropdown' : 'up4StarDropdown';
        const dropdown = document.getElementById(dropdownId);
        
        dropdown.innerHTML = '';
        
        if (items.length === 0) {
            const noItems = document.createElement('li');
            noItems.innerHTML = '<span class="dropdown-item-text text-muted">请先在"包含物品设置"中添加物品</span>';
            dropdown.appendChild(noItems);
            return;
        }
        
        items.forEach(item => {
            const dropdownItem = document.createElement('li');
            dropdownItem.innerHTML = `
                <a class="dropdown-item" href="#" data-name="${item.name}" data-rarity="${item.rarity}">
                    ${item.name} <small class="text-muted">(${item.type})</small>
                </a>
            `;
            
            // Add click event to select item
            dropdownItem.querySelector('a').addEventListener('click', (e) => {
                e.preventDefault();
                this.selectItem(item.name, parseInt(item.rarity));
            });
            
            dropdown.appendChild(dropdownItem);
        });
    }
    
    // Select an item to add to UP list
    selectItem(itemName, rarity) {
        if (rarity === 5) {
            if (!this.selected5StarItems.has(itemName)) {
                this.selected5StarItems.add(itemName);
                this.updateSelectedDisplay(5);
                // Refresh the available items list to remove the selected item but keep search term
                const searchTerm = document.getElementById('up5StarSearch').value;
                this.filterAvailableItems(5, searchTerm);
            }
        } else {
            if (!this.selected4StarItems.has(itemName)) {
                this.selected4StarItems.add(itemName);
                this.updateSelectedDisplay(4);
                // Refresh the available items list to remove the selected item but keep search term
                const searchTerm = document.getElementById('up4StarSearch').value;
                this.filterAvailableItems(4, searchTerm);
            }
        }
    }
    
    // Remove a selected item
    removeSelectedItem(itemName, rarity) {
        if (rarity === 5) {
            this.selected5StarItems.delete(itemName);
            this.updateSelectedDisplay(5);
            // Refresh the available items list to add back the unselected item
            const searchTerm = document.getElementById('up5StarSearch').value;
            this.filterAvailableItems(5, searchTerm);
        } else {
            this.selected4StarItems.delete(itemName);
            this.updateSelectedDisplay(4);
            // Refresh the available items list to add back the unselected item
            const searchTerm = document.getElementById('up4StarSearch').value;
            this.filterAvailableItems(4, searchTerm);
        }
    }
    
    // Update the display of selected items
    updateSelectedDisplay(rarity) {
        const containerId = rarity === 5 ? 'selected5StarItemsDisplay' : 'selected4StarItemsDisplay';
        const container = document.getElementById(containerId);
        const selectedSet = rarity === 5 ? this.selected5StarItems : this.selected4StarItems;
        
        container.innerHTML = '';
        
        if (selectedSet.size === 0) {
            container.innerHTML = '<span class="text-muted">暂无物品</span>';
            return;
        }
        
        selectedSet.forEach(itemName => {
            const itemSpan = document.createElement('span');
            itemSpan.className = 'badge bg-primary me-2 mb-2 d-inline-flex align-items-center';
            itemSpan.innerHTML = `
                ${itemName}
                <button type="button" class="btn-close btn-close-white ms-2" style="font-size: 0.6rem;" 
                        aria-label="Remove" data-item="${itemName}" data-rarity="${rarity}"></button>
            `;
            
            const removeBtn = itemSpan.querySelector('button');
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeSelectedItem(itemName, parseInt(rarity));
            });
            
            container.appendChild(itemSpan);
        });
    }
    
    // Set selected items from banner data (when editing)
    setBannerUpItems(banner) {
        // Clear current selections
        this.selected5StarItems.clear();
        this.selected4StarItems.clear();
        
        // Add existing UP items to selected sets
        banner.rate_up_items['5star'].forEach(item => {
            this.selected5StarItems.add(item);
        });
        
        banner.rate_up_items['4star'].forEach(item => {
            this.selected4StarItems.add(item);
        });
        
        // Update displays
        this.updateSelectedDisplay(5);
        this.updateSelectedDisplay(4);
        
        // Refresh available items to show unselected ones
        this.filterAvailableItems(5, '');
        this.filterAvailableItems(4, '');
    }
    
    // Get selected UP items as comma-separated string
    getSelectedUpItems(rarity) {
        const selectedSet = rarity === 5 ? this.selected5StarItems : this.selected4StarItems;
        return Array.from(selectedSet).join(',');
    }
    
    // Filter and display included items based on search term and rarity
    filterIncludedItems(rarity, searchTerm) {
        let items = this.allItems.filter(item => item.rarity === rarity);
        
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            items = items.filter(item => 
                item.name.toLowerCase().includes(term) ||
                item.type.toLowerCase().includes(term) ||
                item.affiliated_type.toLowerCase().includes(term)
            );
        }
        
        // Filter out already selected items
        items = items.filter(item => {
            if (rarity === 5) {
                return !this.included5StarItems.has(item.name);
            } else if (rarity === 4) {
                return !this.included4StarItems.has(item.name);
            } else {
                return !this.included3StarItems.has(item.name);
            }
        });
        
        this.renderIncludedItemsDropdown(items, rarity);
    }
    
    // Render available items in the included items dropdown
    renderIncludedItemsDropdown(items, rarity) {
        const dropdownId = `included${rarity}StarDropdown`;
        const dropdown = document.getElementById(dropdownId);
        
        dropdown.innerHTML = '';
        
        if (items.length === 0) {
            const noItems = document.createElement('li');
            noItems.innerHTML = '<span class="dropdown-item-text text-muted">没有找到匹配的物品</span>';
            dropdown.appendChild(noItems);
            return;
        }
        
        items.forEach(item => {
            const dropdownItem = document.createElement('li');
            dropdownItem.innerHTML = `
                <a class="dropdown-item" href="#" data-name="${item.name}" data-rarity="${item.rarity}">
                    ${item.name} <small class="text-muted">(${item.type})</small>
                </a>
            `;
            
            dropdownItem.querySelector('a').addEventListener('click', (e) => {
                e.preventDefault();
                this.selectIncludedItem(item.name, parseInt(item.rarity));
            });
            
            dropdown.appendChild(dropdownItem);
        });
    }
    
    // Select an item to add to included list
    selectIncludedItem(itemName, rarity) {
        if (rarity === 5) {
            this.included5StarItems.add(itemName);
            this.updateIncludedItemsDisplay(5);
            const searchTerm = document.getElementById('included5StarSearch').value;
            this.filterIncludedItems(5, searchTerm);
        } else if (rarity === 4) {
            this.included4StarItems.add(itemName);
            this.updateIncludedItemsDisplay(4);
            const searchTerm = document.getElementById('included4StarSearch').value;
            this.filterIncludedItems(4, searchTerm);
        } else {
            this.included3StarItems.add(itemName);
            this.updateIncludedItemsDisplay(3);
            const searchTerm = document.getElementById('included3StarSearch').value;
            this.filterIncludedItems(3, searchTerm);
        }
    }
    
    // Remove an included item
    removeIncludedItem(itemName, rarity) {
        if (rarity === 5) {
            this.included5StarItems.delete(itemName);
            this.updateIncludedItemsDisplay(5);
            const searchTerm = document.getElementById('included5StarSearch').value;
            this.filterIncludedItems(5, searchTerm);
            
            // Also remove from UP items if present
            if (this.selected5StarItems.has(itemName)) {
                this.selected5StarItems.delete(itemName);
                this.updateSelectedDisplay(5);
                // Refresh UP items dropdown
                this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
            }
        } else if (rarity === 4) {
            this.included4StarItems.delete(itemName);
            this.updateIncludedItemsDisplay(4);
            const searchTerm = document.getElementById('included4StarSearch').value;
            this.filterIncludedItems(4, searchTerm);
            
            // Also remove from UP items if present
            if (this.selected4StarItems.has(itemName)) {
                this.selected4StarItems.delete(itemName);
                this.updateSelectedDisplay(4);
                // Refresh UP items dropdown
                this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
            }
        } else {
            this.included3StarItems.delete(itemName);
            this.updateIncludedItemsDisplay(3);
            const searchTerm = document.getElementById('included3StarSearch').value;
            this.filterIncludedItems(3, searchTerm);
        }
    }
    
    // Update the display of included items
    updateIncludedItemsDisplay(rarity) {
        const containerId = `selected${rarity}StarIncludedDisplay`;
        const container = document.getElementById(containerId);
        let selectedSet;
        
        if (rarity === 5) {
            selectedSet = this.included5StarItems;
        } else if (rarity === 4) {
            selectedSet = this.included4StarItems;
        } else {
            selectedSet = this.included3StarItems;
        }
        
        container.innerHTML = '';
        
        if (selectedSet.size === 0) {
            container.innerHTML = '<span class="text-muted">暂无物品</span>';
            return;
        }
        
        selectedSet.forEach(itemName => {
            const itemSpan = document.createElement('span');
            itemSpan.className = 'badge bg-primary me-2 mb-2 d-inline-flex align-items-center';
            itemSpan.innerHTML = `
                ${itemName}
                <button type="button" class="btn-close btn-close-white ms-2" style="font-size: 0.6rem;" 
                        aria-label="Remove" data-item="${itemName}" data-rarity="${rarity}"></button>
            `;
            
            const removeBtn = itemSpan.querySelector('button');
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeIncludedItem(itemName, parseInt(rarity));
            });
            
            container.appendChild(itemSpan);
        });
    }
    
    // Set included items from banner data (when editing)
    setBannerIncludedItems(banner) {
        // Clear current selections
        this.included5StarItems.clear();
        this.included4StarItems.clear();
        this.included3StarItems.clear();
        
        // Add existing included items to selected sets
        banner.included_items['5star'].forEach(item => {
            this.included5StarItems.add(item);
        });
        
        banner.included_items['4star'].forEach(item => {
            this.included4StarItems.add(item);
        });
        
        banner.included_items['3star'].forEach(item => {
            this.included3StarItems.add(item);
        });
        
        // Update displays
        this.updateIncludedItemsDisplay(5);
        this.updateIncludedItemsDisplay(4);
        this.updateIncludedItemsDisplay(3);
        
        // Refresh available items to show unselected ones
        this.filterIncludedItems(5, '');
        this.filterIncludedItems(4, '');
        this.filterIncludedItems(3, '');
    }
    
    // Select all items of a specific rarity for inclusion
    selectAllIncludedItems(rarity) {
        const items = this.allItems.filter(item => item.rarity === rarity);
        
        if (rarity === 5) {
            items.forEach(item => this.included5StarItems.add(item.name));
            this.updateIncludedItemsDisplay(5);
            this.filterIncludedItems(5, document.getElementById('included5StarSearch').value);
            // Refresh UP items dropdown
            this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
        } else if (rarity === 4) {
            items.forEach(item => this.included4StarItems.add(item.name));
            this.updateIncludedItemsDisplay(4);
            this.filterIncludedItems(4, document.getElementById('included4StarSearch').value);
            // Refresh UP items dropdown
            this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
        } else {
            items.forEach(item => this.included3StarItems.add(item.name));
            this.updateIncludedItemsDisplay(3);
            this.filterIncludedItems(3, document.getElementById('included3StarSearch').value);
            // No need to refresh UP items for 3-star since UP items are only 4 and 5 star
        }
    }
    
    // Validate UP items to ensure they're all in the included list
    validateUpItems() {
        // Validate 5-star UP items
        const invalid5StarItems = Array.from(this.selected5StarItems).filter(
            item => !this.included5StarItems.has(item)
        );
        
        if (invalid5StarItems.length > 0) {
            invalid5StarItems.forEach(item => {
                this.selected5StarItems.delete(item);
            });
            this.updateSelectedDisplay(5);
        }
        
        // Validate 4-star UP items
        const invalid4StarItems = Array.from(this.selected4StarItems).filter(
            item => !this.included4StarItems.has(item)
        );
        
        if (invalid4StarItems.length > 0) {
            invalid4StarItems.forEach(item => {
                this.selected4StarItems.delete(item);
            });
            this.updateSelectedDisplay(4);
        }
        
        // Refresh UP items dropdowns
        this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
        this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
    }
    
    // Clear all included items of a specific rarity
    clearAllIncludedItems(rarity) {
        if (rarity === 5) {
            // Remove all 5-star included items
            const removedItems = Array.from(this.included5StarItems);
            this.included5StarItems.clear();
            this.updateIncludedItemsDisplay(5);
            this.filterIncludedItems(5, document.getElementById('included5StarSearch').value);
            
            // Remove any removed items from UP items
            removedItems.forEach(item => {
                if (this.selected5StarItems.has(item)) {
                    this.selected5StarItems.delete(item);
                    this.updateSelectedDisplay(5);
                }
            });
            // Refresh UP items dropdown
            this.filterAvailableItems(5, document.getElementById('up5StarSearch').value);
        } else if (rarity === 4) {
            // Remove all 4-star included items
            const removedItems = Array.from(this.included4StarItems);
            this.included4StarItems.clear();
            this.updateIncludedItemsDisplay(4);
            this.filterIncludedItems(4, document.getElementById('included4StarSearch').value);
            
            // Remove any removed items from UP items
            removedItems.forEach(item => {
                if (this.selected4StarItems.has(item)) {
                    this.selected4StarItems.delete(item);
                    this.updateSelectedDisplay(4);
                }
            });
            // Refresh UP items dropdown
            this.filterAvailableItems(4, document.getElementById('up4StarSearch').value);
        } else {
            this.included3StarItems.clear();
            this.updateIncludedItemsDisplay(3);
            this.filterIncludedItems(3, document.getElementById('included3StarSearch').value);
        }
    }
    
    // Get included items as comma-separated string
    getIncludedItems(rarity) {
        let includedSet;
        if (rarity === 5) {
            includedSet = this.included5StarItems;
        } else if (rarity === 4) {
            includedSet = this.included4StarItems;
        } else {
            includedSet = this.included3StarItems;
        }
        return Array.from(includedSet).join(',');
    }

    // Show banner form
    showForm(banner = null) {
        document.getElementById('bannerFormSection').style.display = 'block';
        document.getElementById('bannerList').parentElement.style.display = 'none';
        document.getElementById('newBannerBtn').style.display = 'none';

        if (banner) {
            document.getElementById('formTitle').textContent = '编辑卡池';
            document.getElementById('bannerId').value = banner.id;
            document.getElementById('bannerName').value = banner.name;
            document.getElementById('base5StarRate').value = banner.probability_settings.base_5star_rate;
            document.getElementById('base5StarRateSlider').value = banner.probability_settings.base_5star_rate;
            document.getElementById('base5StarRateDisplay').textContent = banner.probability_settings.base_5star_rate.toFixed(6);
            document.getElementById('base4StarRate').value = banner.probability_settings.base_4star_rate;
            document.getElementById('base4StarRateSlider').value = banner.probability_settings.base_4star_rate;
            document.getElementById('base4StarRateDisplay').textContent = banner.probability_settings.base_4star_rate.toFixed(6);
            // Calculate and set the 3-star rate as read-only
            const calculated3StarRate = 1 - banner.probability_settings.base_5star_rate - banner.probability_settings.base_4star_rate;
            document.getElementById('base3StarRate').value = calculated3StarRate;
            document.getElementById('base3StarRateDisplay').textContent = calculated3StarRate.toFixed(4);
            document.getElementById('up5StarRate').value = banner.probability_settings.up_5star_rate;
            document.getElementById('up4StarRate').value = banner.probability_settings.up_4star_rate;
            document.getElementById('hardPityPull').value = banner.probability_progression['5star'].hard_pity_pull;
            document.getElementById('hardPityRate').value = banner.probability_progression['5star'].hard_pity_rate;

            // Set UP items for editing
            this.setBannerUpItems(banner);
            
            // Set included items for editing
            this.setBannerIncludedItems(banner);

            // Clear and populate soft pity entries
            const container = document.getElementById('softPityContainer');
            container.innerHTML = '';
            banner.probability_progression['5star'].soft_pity.forEach((entry, index) => {
                this.addSoftPityEntry(entry.start_pull, entry.end_pull, entry.increment, index);
            });
        } else {
            document.getElementById('formTitle').textContent = '创建新卡池';
            document.getElementById('bannerForm').reset();
            document.getElementById('bannerId').value = '';
            
            // Set default values for sliders and displays
            document.getElementById('base5StarRate').value = '0.008';
            document.getElementById('base5StarRateSlider').value = '0.008';
            document.getElementById('base5StarRateDisplay').textContent = '0.008';
            document.getElementById('base4StarRate').value = '0.06';
            document.getElementById('base4StarRateSlider').value = '0.06';
            document.getElementById('base4StarRateDisplay').textContent = '0.06';
            // Calculate and set the 3-star rate
            const calculated3StarRate = 1 - 0.008 - 0.06;
            document.getElementById('base3StarRate').value = calculated3StarRate.toFixed(4);
            document.getElementById('base3StarRateDisplay').textContent = calculated3StarRate.toFixed(4);
            
            // Clear selections for new banner
            // UP items
            this.selected5StarItems.clear();
            this.selected4StarItems.clear();
            this.updateSelectedDisplay(5);
            this.updateSelectedDisplay(4);
            
            // Included items
            this.included5StarItems.clear();
            this.included4StarItems.clear();
            this.included3StarItems.clear();
            this.updateIncludedItemsDisplay(5);
            this.updateIncludedItemsDisplay(4);
            this.updateIncludedItemsDisplay(3);
            
            // Refresh available items to show all
            this.filterAvailableItems(5, '');
            this.filterAvailableItems(4, '');
            this.filterIncludedItems(5, '');
            this.filterIncludedItems(4, '');
            this.filterIncludedItems(3, '');
            
            // Add default soft pity entries
            const container = document.getElementById('softPityContainer');
            container.innerHTML = '';
            this.addSoftPityEntry(66, 70, 0.04, 0);
            this.addSoftPityEntry(71, 75, 0.08, 1);
            this.addSoftPityEntry(76, 78, 0.1, 2);
        }
    }

    // Hide banner form
    hideForm() {
        document.getElementById('bannerFormSection').style.display = 'none';
        document.getElementById('bannerList').parentElement.style.display = 'block';
        document.getElementById('newBannerBtn').style.display = 'block';
    }

    // Add a soft pity entry to the form
    addSoftPityEntry(start_pull = '', end_pull = '', increment = '', index = null) {
        const container = document.getElementById('softPityContainer');
        const entryIndex = index !== null ? index : container.children.length;
        
        const entryDiv = document.createElement('div');
        entryDiv.className = 'soft-pity-entry row mb-2';
        entryDiv.dataset.index = entryIndex;
        
        entryDiv.innerHTML = `
            <div class="col-md-3">
                <label class="form-label">开始抽数</label>
                <input type="number" class="form-control soft-pity-start" value="${start_pull}" min="1" required>
            </div>
            <div class="col-md-3">
                <label class="form-label">结束抽数</label>
                <input type="number" class="form-control soft-pity-end" value="${end_pull}" min="1" required>
            </div>
            <div class="col-md-4">
                <label class="form-label">递增概率</label>
                <input type="number" class="form-control soft-pity-increment" value="${increment}" step="0.01" min="0" max="1" required>
            </div>
            <div class="col-md-2 d-flex align-items-end">
                <button type="button" class="btn btn-danger remove-soft-pity-btn">删除</button>
            </div>
        `;
        
        container.appendChild(entryDiv);
        
        // Add event listener to remove button
        entryDiv.querySelector('.remove-soft-pity-btn').addEventListener('click', () => {
            container.removeChild(entryDiv);
            this.updateHardPityMinValue();
        });
        
        // Add event listeners to soft pity inputs to update hard pity min value
        entryDiv.querySelector('.soft-pity-start').addEventListener('input', () => {
            this.updateHardPityMinValue();
        });
        
        entryDiv.querySelector('.soft-pity-end').addEventListener('input', () => {
            this.updateHardPityMinValue();
        });
        
        this.updateHardPityMinValue();
    }

    // Update the minimum value for hard pity pull based on soft pity entries
    updateHardPityMinValue() {
        // Get all soft pity entries
        const softPityEntries = document.querySelectorAll('.soft-pity-entry');
        let maxSoftPityEnd = 0;
        
        // Find the maximum end_pull value from all soft pity entries
        softPityEntries.forEach(entry => {
            const endPull = parseInt(entry.querySelector('.soft-pity-end').value) || 0;
            if (endPull > maxSoftPityEnd) {
                maxSoftPityEnd = endPull;
            }
        });
        
        const hardPityPullInput = document.getElementById('hardPityPull');
        hardPityPullInput.min = maxSoftPityEnd + 1;
        
        // If current hard pity value is less than the new minimum, update it
        const currentHardPity = parseInt(hardPityPullInput.value) || 0;
        if (currentHardPity > 0 && currentHardPity < parseInt(hardPityPullInput.min)) {
            hardPityPullInput.value = hardPityPullInput.min;
        }
    }

    // Validate form inputs
    validateForm() {
        const name = document.getElementById('bannerName').value.trim();
        if (!name) {
            alert('请输入卡池名称');
            return false;
        }

        // Validate probability rates are non-negative
        const base5Star = parseFloat(document.getElementById('base5StarRate').value) || 0;
        const base4Star = parseFloat(document.getElementById('base4StarRate').value) || 0;
        const base3Star = 1 - base5Star - base4Star; // Calculate 3-star rate
        
        if (base5Star < 0) {
            alert('5星基础概率不能为负数');
            return false;
        }
        
        if (base4Star < 0) {
            alert('4星基础概率不能为负数');
            return false;
        }
        
        if (base3Star < 0) {
            alert('3星基础概率不能为负数（5星和4星概率之和不能超过1）');
            return false;
        }

        // Validate probability rates sum to approximately 1
        const totalRate = base5Star + base4Star + base3Star;
        if (Math.abs(totalRate - 1) > 0.01) { // Allow small floating point errors
            alert(`基础概率之和应为1，当前为 ${totalRate.toFixed(3)}`);
            return false;
        }

        // Validate soft pity entries
        const softPityEntries = document.querySelectorAll('.soft-pity-entry');
        let maxSoftPityEnd = 0;
        
        for (let i = 0; i < softPityEntries.length; i++) {
            const entry = softPityEntries[i];
            const start = parseInt(entry.querySelector('.soft-pity-start').value);
            const end = parseInt(entry.querySelector('.soft-pity-end').value);
            
            if (start >= end) {
                alert(`软保底区间 ${i + 1} 的开始抽数必须小于结束抽数`);
                return false;
            }
            
            if (end > maxSoftPityEnd) {
                maxSoftPityEnd = end;
            }
        }
        
        // Validate hard pity pull is greater than max soft pity end
        const hardPityPull = parseInt(document.getElementById('hardPityPull').value);
        if (hardPityPull <= maxSoftPityEnd) {
            alert(`硬保底抽数必须大于软保底区间的最大结束抽数 (${maxSoftPityEnd})`);
            return false;
        }

        return true;
    }

    // Save banner from form
    async saveBanner() {
        if (!this.validateForm()) {
            return;
        }

        const id = document.getElementById('bannerId').value || null;
        const name = document.getElementById('bannerName').value.trim();
        
        // Get soft pity entries
        const softPity = [];
        document.querySelectorAll('.soft-pity-entry').forEach(entry => {
            const start = parseInt(entry.querySelector('.soft-pity-start').value);
            const end = parseInt(entry.querySelector('.soft-pity-end').value);
            const increment = parseFloat(entry.querySelector('.soft-pity-increment').value);
            
            softPity.push({
                start_pull: start,
                end_pull: end,
                increment: increment
            });
        });

        const banner = {
            // Don't include id in the data sent to server - server will use banner name as filename
            name: name,
            probability_settings: {
                base_5star_rate: parseFloat(document.getElementById('base5StarRate').value),
                base_4star_rate: parseFloat(document.getElementById('base4StarRate').value),
                _4star_role_rate: 0.06, // Default value
                base_3star_rate: 1 - parseFloat(document.getElementById('base5StarRate').value) - parseFloat(document.getElementById('base4StarRate').value), // This will be calculated as 1 - base_5star_rate - base_4star_rate
                up_5star_rate: parseFloat(document.getElementById('up5StarRate').value),
                up_4star_rate: parseFloat(document.getElementById('up4StarRate').value)
            },
            rate_up_items: {
                '5star': this.getSelectedUpItems(5).split(',').filter(item => item.trim() !== ''),
                '4star': this.getSelectedUpItems(4).split(',').filter(item => item.trim() !== '')
            },
            included_items: {
                '5star': this.getIncludedItems(5).split(',').filter(item => item.trim() !== ''),
                '4star': this.getIncludedItems(4).split(',').filter(item => item.trim() !== ''),
                '3star': this.getIncludedItems(3).split(',').filter(item => item.trim() !== '')
            },
            probability_progression: {
                '5star': {
                    hard_pity_pull: parseInt(document.getElementById('hardPityPull').value),
                    hard_pity_rate: parseFloat(document.getElementById('hardPityRate').value),
                    soft_pity: softPity
                },
                '4star': {
                    hard_pity_pull: 10, // Default value
                    hard_pity_rate: 1,  // Default value
                    soft_pity: []
                }
            }
        };

        // If editing an existing banner, include the ID to preserve the filename
        if (id) {
            banner.id = id;
        }

        try {
            const response = await fetch('/api/banners', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(banner)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Reload banners from the server
                await this.loadBanners();
                this.hideForm();
                alert('卡池保存成功！');
            } else {
                console.error('Failed to save banner:', result.error);
                alert('保存卡池失败: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving banner:', error);
            alert('保存卡池时发生错误: ' + error.message);
        }
    }

    // Delete a banner
    async deleteBanner(id) {
        try {
            const response = await fetch(`/api/banners/${id}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Reload banners from the server
                await this.loadBanners();
                alert('卡池删除成功！');
            } else {
                console.error('Failed to delete banner:', result.error);
                alert('删除卡池失败: ' + result.error);
            }
        } catch (error) {
            console.error('Error deleting banner:', error);
            alert('删除卡池时发生错误: ' + error.message);
        }
    }

    // Render banner list
    renderBannerList() {
        const container = document.getElementById('bannerList');
        container.innerHTML = '';

        this.banners.forEach(banner => {
            const bannerCard = document.createElement('div');
            bannerCard.className = 'col-md-6 col-lg-4 mb-4';
            bannerCard.innerHTML = `
                <div class="card banner-card h-100">
                    <div class="card-body">
                        <h5 class="card-title">${banner.name}</h5>
                        <p class="card-text">
                            <strong>基础概率:</strong><br>
                            5星: ${(banner.probability_settings.base_5star_rate * 100).toFixed(3)}%<br>
                            4星: ${(banner.probability_settings.base_4star_rate * 100).toFixed(2)}%<br>
                            3星: ${((1 - banner.probability_settings.base_5star_rate - banner.probability_settings.base_4star_rate) * 100).toFixed(1)}%<br>
                            <strong>保底设置:</strong> ${banner.probability_progression['5star'].hard_pity_pull}抽数硬保底
                        </p>
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-sm btn-primary edit-btn" data-id="${banner.id}">编辑</button>
                        <button class="btn btn-sm btn-danger delete-btn" data-id="${banner.id}" data-name="${banner.name}">删除</button>
                    </div>
                </div>
            `;

            // Add event listeners for edit and delete buttons
            bannerCard.querySelector('.edit-btn').addEventListener('click', () => {
                const bannerToEdit = this.banners.find(b => b.id === banner.id);
                this.showForm(bannerToEdit);
            });

            bannerCard.querySelector('.delete-btn').addEventListener('click', () => {
                document.getElementById('bannerToDeleteName').textContent = banner.name;
                const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
                modal.show();
                
                // Set up confirmation button
                document.getElementById('confirmDeleteBtn').onclick = async () => {
                    await this.deleteBanner(banner.id);
                    modal.hide();
                };
            });

            container.appendChild(bannerCard);
        });
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new BannerManager();
});