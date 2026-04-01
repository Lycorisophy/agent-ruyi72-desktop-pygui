/**
 * 如意 Agent - 前端应用
 */

// API 配置
const API_BASE = 'http://127.0.0.1:8765/api';
const WS_BASE = 'ws://127.0.0.1:8765/api';

// 状态管理
const state = {
    sessionId: 'default',
    agentMode: 'general',
    isStreaming: false,
    messages: [],
    skills: [],
    systemInfo: null,
};

// 工具函数
function $(selector) {
    return document.querySelector(selector);
}

function $$(selector) {
    return document.querySelectorAll(selector);
}

// ==========================================================
// 初始化
// ==========================================================

async function init() {
    console.log('[App] Initializing...');
    
    // 加载技能列表
    await loadSkills();
    
    // 加载系统信息
    await loadSystemInfo();
    
    // 健康检查
    await healthCheck();
    
    // 绑定事件
    bindEvents();
    
    // 加载历史
    await loadHistory();
    
    console.log('[App] Initialized');
}

async function loadSkills() {
    try {
        const result = await pywebview.api.get_skills();
        if (result.skills) {
            state.skills = result.skills;
            renderSkills();
        }
    } catch (e) {
        console.error('[App] Failed to load skills:', e);
    }
}

async function loadSystemInfo() {
    try {
        const info = await pywebview.api.get_system_info();
        state.systemInfo = info;
        updateSystemInfo();
    } catch (e) {
        console.error('[App] Failed to load system info:', e);
    }
}

async function healthCheck() {
    try {
        const health = await pywebview.api.health_check();
        updateHealthStatus(health);
    } catch (e) {
        updateHealthStatus({ status: 'offline', error: e.message });
    }
}

async function loadHistory() {
    try {
        const result = await pywebview.api.get_history(state.sessionId);
        if (result.history) {
            state.messages = result.history;
            renderMessages();
        }
    } catch (e) {
        console.error('[App] Failed to load history:', e);
    }
}

// ==========================================================
// UI 渲染
// ==========================================================

function renderSkills() {
    const container = $('#skills-list');
    if (!container) return;
    
    const categories = {};
    state.skills.forEach(skill => {
        const cat = skill.category || 'general';
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(skill);
    });
    
    let html = '';
    for (const [cat, skills] of Object.entries(categories)) {
        html += `<div class="skill-category">
            <h4>${cat}</h4>
            <div class="skill-items">`;
        skills.forEach(skill => {
            html += `<button class="skill-btn" data-skill="${skill.name}" title="${skill.description}">
                ${skill.name}
            </button>`;
        });
        html += '</div></div>';
    }
    
    container.innerHTML = html || '<p class="text-muted">暂无技能</p>';
    
    // 绑定技能按钮事件
    $$('.skill-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const skillName = btn.dataset.skill;
            const skill = state.skills.find(s => s.name === skillName);
            if (skill) {
                showSkillDialog(skill);
            }
        });
    });
}

function renderMessages() {
    const container = $('#messages');
    if (!container) return;
    
    let html = '';
    state.messages.forEach(msg => {
        const role = msg.role === 'user' ? 'user' : 'assistant';
        html += `<div class="message ${role}">
            <div class="message-role">${role === 'user' ? '你' : '如意'}</div>
            <div class="message-content">${escapeHtml(msg.content)}</div>
        </div>`;
    });
    
    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
}

function updateHealthStatus(health) {
    const indicator = $('#health-indicator');
    const status = $('#health-status');
    
    if (indicator && status) {
        if (health.status === 'healthy') {
            indicator.className = 'status-indicator online';
            status.textContent = `在线 (${health.ollama || 'unknown'})`;
        } else if (health.status === 'degraded') {
            indicator.className = 'status-indicator warning';
            status.textContent = '部分功能可用';
        } else {
            indicator.className = 'status-indicator offline';
            status.textContent = '离线';
        }
    }
}

function updateSystemInfo() {
    if (!state.systemInfo) return;
    
    const info = state.systemInfo;
    const container = $('#system-info');
    if (container) {
        container.innerHTML = `
            <p><strong>版本:</strong> ${info.version}</p>
            <p><strong>模型:</strong> ${info.ollama?.model || 'unknown'}</p>
            <p><strong>技能:</strong> ${info.skills_count || 0}</p>
            <p><strong>会话:</strong> ${info.sessions_count || 0}</p>
        `;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
}

// ==========================================================
// 事件绑定
// ==========================================================

function bindEvents() {
    // 发送消息
    const input = $('#message-input');
    const sendBtn = $('#send-btn');
    
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    // Agent 模式切换
    $$('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.agentMode = btn.dataset.mode;
        });
    });
    
    // 清空会话
    const clearBtn = $('#clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
            if (confirm('确定要清空当前会话吗？')) {
                await pywebview.api.clear_session(state.sessionId);
                state.messages = [];
                renderMessages();
            }
        });
    }
    
    // 技能标签点击
    const skillsTab = $('[data-tab="skills"]');
    if (skillsTab) {
        skillsTab.addEventListener('click', () => switchTab('skills'));
    }
    
    // 设置标签
    const settingsTab = $('[data-tab="settings"]');
    if (settingsTab) {
        settingsTab.addEventListener('click', () => switchTab('settings'));
    }
}

function switchTab(tabName) {
    $$('.tab-content').forEach(tab => {
        tab.classList.remove('active');
        if (tab.id === `${tabName}-panel`) {
            tab.classList.add('active');
        }
    });
    
    $$('.sidebar-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        }
    });
}

// ==========================================================
// 核心功能
// ==========================================================

async function sendMessage() {
    const input = $('#message-input');
    const message = input?.value.trim();
    
    if (!message || state.isStreaming) return;
    
    // 清空输入
    if (input) input.value = '';
    
    // 添加用户消息
    state.messages.push({ role: 'user', content: message });
    renderMessages();
    
    // 设置流式状态
    state.isStreaming = true;
    const sendBtn = $('#send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.textContent = '思考中...';
    }
    
    // 添加占位消息
    const placeholderIndex = state.messages.length;
    state.messages.push({ role: 'assistant', content: '...' });
    renderMessages();
    
    try {
        // 流式请求
        const response = await fetch(`${API_BASE}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                agent_mode: state.agentMode,
                session_id: state.sessionId,
                stream: true,
            }),
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.error) {
                            state.messages[placeholderIndex] = {
                                role: 'assistant',
                                content: `错误: ${data.error}`,
                            };
                        } else if (data.chunk) {
                            fullResponse += data.chunk;
                            state.messages[placeholderIndex] = {
                                role: 'assistant',
                                content: fullResponse,
                            };
                            renderMessages();
                        } else if (data.done) {
                            state.messages[placeholderIndex] = {
                                role: 'assistant',
                                content: fullResponse || '已完成',
                            };
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }
            }
        }
        
    } catch (e) {
        console.error('[App] Stream error:', e);
        state.messages[placeholderIndex] = {
            role: 'assistant',
            content: `请求失败: ${e.message}`,
        };
    }
    
    // 恢复状态
    state.isStreaming = false;
    if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.textContent = '发送';
    }
    
    renderMessages();
}

function showSkillDialog(skill) {
    const modal = $('#skill-modal');
    if (!modal) return;
    
    // 填充技能信息
    $('#skill-modal-title').textContent = skill.name;
    $('#skill-modal-desc').textContent = skill.description;
    
    // 生成参数表单
    const paramsContainer = $('#skill-params');
    let paramsHtml = '';
    
    (skill.parameters || []).forEach(param => {
        paramsHtml += `
            <div class="form-group">
                <label>${param.name} ${param.required ? '*' : ''}</label>
                <input type="text" 
                       name="${param.name}" 
                       placeholder="${param.description}"
                       ${param.required ? 'required' : ''}>
            </div>
        `;
    });
    
    paramsContainer.innerHTML = paramsHtml || '<p>此技能不需要参数</p>';
    
    // 显示模态框
    modal.classList.add('active');
    
    // 绑定确认按钮
    $('#skill-execute-btn').onclick = async () => {
        const params = {};
        paramsContainer.querySelectorAll('input').forEach(input => {
            if (input.value) {
                params[input.name] = input.value;
            }
        });
        
        try {
            const result = await pywebview.api.execute_skill(skill.name, params);
            if (result.success) {
                alert(`执行成功:\n${result.output}`);
            } else {
                alert(`执行失败:\n${result.error}`);
            }
        } catch (e) {
            alert(`执行出错:\n${e.message}`);
        }
        
        modal.classList.remove('active');
    };
    
    // 绑定取消按钮
    $('#skill-cancel-btn').onclick = () => {
        modal.classList.remove('active');
    };
}

// ==========================================================
// 启动
// ==========================================================

document.addEventListener('DOMContentLoaded', init);
