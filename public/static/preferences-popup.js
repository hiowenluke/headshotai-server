// PreferencesPopup JavaScript 逻辑

// 偏好设置数据模型
window.preferencesData = {
    gender: 'female',
    ethnicity: 'white',
    age: 'middle',
    bodySize: 'm'
};

// 处理选项点击
window.handleOptionClick = function (event) {
    const option = event.currentTarget;
    const group = option.closest('[data-group]').getAttribute('data-group');
    const value = option.getAttribute('data-value');

    // 更新数据模型
    window.preferencesData[group] = value;

    // 更新UI状态
    const groupContainer = option.closest('[data-group]');
    const allOptions = groupContainer.querySelectorAll('.preferences-option');
    allOptions.forEach(opt => opt.classList.remove('active'));
    option.classList.add('active');
};

// 处理Apply按钮点击
window.handlePreferencesApply = function () {
    // 从当前UI状态读取数据，而不是从window.preferencesData
    const payload = {};
    
    // 读取每个组的选中状态
    ['gender', 'ethnicity', 'age', 'bodySize'].forEach(group => {
        const groupContainer = document.querySelector(`[data-group="${group}"]`);
        if (groupContainer) {
            const activeOption = groupContainer.querySelector('.preferences-option.active');
            if (activeOption) {
                payload[group] = activeOption.getAttribute('data-value');
            }
        }
    });
    
    // 保存到localStorage（使用与PreferencesPage.vue相同的键名）
    const PREF_KEY = 'user_prefs_v1';
    const PREF_SHOWN_KEY = 'user_prefs_shown_v1';
    
    try {
        localStorage.setItem(PREF_KEY, JSON.stringify(payload));
        localStorage.setItem(PREF_SHOWN_KEY, '1');
    } catch (error) {
        return;
    }

    // 隐藏弹窗
    const popup = document.getElementById('preferences-popup');
    if (popup) {
        popup.classList.add('preferences-popup-hidden');

        // 标记PreferencesPopup已完成
        window.__preferencesCompleted = true;

        // 延迟移除DOM元素
        setTimeout(() => {
            if (popup.parentElement) {
                popup.parentElement.removeChild(popup);
            }
        }, 300);
    }
};

// 初始化事件监听器
window.initPreferencesPopup = function () {
    // 防止重复初始化
    if (window.__preferencesInitialized) {
        return;
    }
    window.__preferencesInitialized = true;
    
    // 绑定选项点击事件
    const options = document.querySelectorAll('.preferences-option');
    options.forEach(option => {
        option.addEventListener('click', window.handleOptionClick);
    });

    // 绑定Apply按钮事件
    const applyBtn = document.getElementById('preferences-apply');
    if (applyBtn) {
        applyBtn.addEventListener('click', window.handlePreferencesApply);
        applyBtn.onclick = window.handlePreferencesApply;
    }
};

// 脚本加载完成，等待HTML内容被动态加载后再调用