// 财经主播助手 MVP - 前端逻辑
const { createApp } = Vue;

const DEFAULT_API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : window.location.origin;
const API_BASE = (window.API_BASE && String(window.API_BASE).trim())
    ? String(window.API_BASE).replace(/\/+$/, '')
    : DEFAULT_API_BASE;

// 从 localStorage 读取持久化设置
function loadSettings() {
    try {
        const saved = localStorage.getItem('finance_streamer_settings');
        if (saved) return JSON.parse(saved);
    } catch (_) {}
    return { duration: 30, style: '专业', apiKey: '' };
}

// 历史记录工具函数
const HISTORY_KEY = 'finance_streamer_history';
const HISTORY_MAX = 20;

function loadHistory() {
    try {
        const saved = localStorage.getItem(HISTORY_KEY);
        if (saved) return JSON.parse(saved);
    } catch (_) {}
    return [];
}

function saveHistory(historyList) {
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(historyList.slice(0, HISTORY_MAX)));
    } catch (_) {}
}

createApp({
    data() {
        return {
            // 新闻数据
            news: [],
            selectedNews: [],
            filterCategory: '全部',
            searchKeyword: '',

            // 分类
            categories: ['全部', '宏观', 'A股', '美股', '行业', '个股', '财经'],

            // 状态
            loading: false,
            generating: false,
            generatingAll: false,
            generatingPpt: false,

            // 生成结果
            result: null,
            resultType: '',
            allResults: null,
            activeTab: 'stream_script',

            // 设置
            settings: loadSettings(),
            showSettings: false,

            // 历史记录
            history: loadHistory(),
            showHistory: false,

            // 提示
            showToast: false,
            toastMessage: '',

            // 时间
            currentTime: '',
            timer: null
        };
    },

    computed: {
        filteredNews() {
            let list = this.news;
            if (this.filterCategory !== '全部') {
                list = list.filter(n => n.category === this.filterCategory);
            }
            if (this.searchKeyword.trim()) {
                const kw = this.searchKeyword.trim().toLowerCase();
                list = list.filter(n =>
                    n.title.toLowerCase().includes(kw) ||
                    (n.category || '').toLowerCase().includes(kw) ||
                    (n.source || '').toLowerCase().includes(kw)
                );
            }
            return list;
        },

        selectedCount() {
            return this.selectedNews.length;
        },

        allSelected: {
            get() {
                return this.filteredNews.length > 0 &&
                    this.filteredNews.every(n => this.selectedNews.includes(n.id));
            },
            set(_value) {
                // 由 toggleAll 方法处理
            }
        },

        hasResults() {
            return this.result !== null || this.allResults !== null;
        },

        resultTabs() {
            return [
                { key: 'stream_script', label: '📝 直播稿' },
                { key: 'article', label: '📱 公众号' },
                { key: 'deep_dive', label: '📄 深度长文' },
            ];
        },

        resultTitle() {
            const titles = {
                stream_script: '📝 直播稿',
                article: '📱 公众号文章',
                deep_dive: '📄 深度长文'
            };
            const type = this.allResults ? this.activeTab : this.resultType;
            return titles[type] || '生成结果';
        },

        resultContent() {
            if (this.allResults) {
                const r = this.allResults[this.activeTab];
                if (this.activeTab === 'article' && r && r.content) return r.content;
                return r || '';
            }
            if (!this.result) return '';
            if (this.resultType === 'article' && this.result.content) {
                return this.result.content;
            }
            return typeof this.result === 'string' ? this.result : (this.result.content || '');
        },

        currentWordCount() {
            const text = this.resultContent;
            if (!text) return 0;
            return text.replace(/\s/g, '').length;
        }
    },

    methods: {
        // 更新时间
        updateTime() {
            const now = new Date();
            this.currentTime = now.toLocaleString('zh-CN', {
                month: 'long',
                day: 'numeric',
                weekday: 'long',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        // 构建请求头
        buildHeaders() {
            const headers = { 'Content-Type': 'application/json' };
            if (this.settings.apiKey) {
                headers['X-API-Key'] = this.settings.apiKey;
            }
            return headers;
        },

        // 获取新闻
        async fetchNews(refresh = false) {
            this.loading = true;
            try {
                const response = await fetch(`${API_BASE}/api/news?refresh=${refresh}`);
                const data = await response.json();

                if (data.data) {
                    this.news = data.data;
                    if (!refresh && data.cached) {
                        this.showToastMessage(`已加载缓存数据 (${data.count}条)`);
                    } else {
                        const fallbackNote = data.fallback ? '（模拟数据）' : '';
                        this.showToastMessage(`刷新成功，获取 ${data.count} 条新闻${fallbackNote}`);
                    }
                }
            } catch (error) {
                console.error('获取新闻失败:', error);
                this.showToastMessage('获取新闻失败，请检查网络');
            } finally {
                this.loading = false;
            }
        },

        // 刷新新闻
        refreshNews() {
            this.fetchNews(true);
        },

        // 搜索新闻（前端实时过滤，无需调用接口）
        searchNews() {
            // filteredNews computed 会自动处理，此方法作为回车处理入口
        },

        // 点击新闻条目切换选中
        toggleNewsItem(id) {
            const idx = this.selectedNews.indexOf(id);
            if (idx > -1) {
                this.selectedNews.splice(idx, 1);
            } else {
                this.selectedNews.push(id);
            }
        },

        // 全选/取消全选
        toggleAll() {
            if (this.allSelected) {
                this.filteredNews.forEach(n => {
                    const index = this.selectedNews.indexOf(n.id);
                    if (index > -1) {
                        this.selectedNews.splice(index, 1);
                    }
                });
            } else {
                this.filteredNews.forEach(n => {
                    if (!this.selectedNews.includes(n.id)) {
                        this.selectedNews.push(n.id);
                    }
                });
            }
        },

        // 生成内容
        async generateContent(type) {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻');
                return;
            }

            this.generating = true;
            this.generatingAll = false;
            this.result = null;
            this.allResults = null;
            this.resultType = type;

            try {
                const response = await fetch(`${API_BASE}/api/generate`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify({
                        news_ids: this.selectedNews,
                        content_type: type,
                        duration: this.settings.duration,
                        style: this.settings.style
                    })
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const data = await response.json();

                if (data.content !== undefined || data.titles) {
                    this.result = type === 'article' ? data : data.content;
                    this.showToastMessage(`生成成功！(${this.currentWordCount} 字)`);
                    this._addToHistory(type, this.resultContent);
                } else {
                    throw new Error('生成失败，返回数据为空');
                }
            } catch (error) {
                console.error('生成失败:', error);
                this.showToastMessage(`生成失败：${error.message}`);
            } finally {
                this.generating = false;
            }
        },

        // 一键生成全部（并行）
        async generateAll() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻');
                return;
            }

            this.generating = true;
            this.generatingAll = true;
            this.result = null;
            this.allResults = null;

            try {
                const response = await fetch(`${API_BASE}/api/generate/all`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify(this.selectedNews)
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const data = await response.json();

                this.allResults = data;
                this.activeTab = 'stream_script';

                // 将三种内容分别存入历史
                const types = ['stream_script', 'article', 'deep_dive'];
                types.forEach(t => {
                    const r = data[t];
                    const content = (t === 'article' && r && r.content) ? r.content : (typeof r === 'string' ? r : '');
                    if (content) this._addToHistory(t, content);
                });

                this.showToastMessage('全部生成完成！');
            } catch (error) {
                console.error('生成失败:', error);
                this.showToastMessage(`生成失败：${error.message}`);
            } finally {
                this.generating = false;
                this.generatingAll = false;
            }
        },

        // 生成并下载 PPT
        async generatePpt() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻');
                return;
            }

            this.generatingPpt = true;
            try {
                const response = await fetch(`${API_BASE}/api/generate/ppt`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify(this.selectedNews)
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                // 从 Content-Disposition 头提取文件名（如有），否则用默认名
                const disposition = response.headers.get('Content-Disposition') || '';
                const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
                let filename = `财经日报_${this.getDateTimeString()}.pptx`;
                if (match) {
                    // 去除引号，sanitize 路径分隔符，防止路径遍历
                    const raw = decodeURIComponent(match[1]).replace(/['"]/g, '').trim();
                    filename = raw.replace(/[/\\:*?"<>|]/g, '_');
                }
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                this.showToastMessage('PPT 已生成并下载！');
            } catch (error) {
                console.error('PPT生成失败:', error);
                this.showToastMessage(`PPT生成失败：${error.message}`);
            } finally {
                this.generatingPpt = false;
            }
        },

        // 清除结果
        clearResult() {
            this.result = null;
            this.allResults = null;
        },

        // 复制结果
        async copyResult() {
            try {
                await navigator.clipboard.writeText(this.resultContent);
                this.showToastMessage('已复制到剪贴板');
            } catch (_) {
                const textarea = document.createElement('textarea');
                textarea.value = this.resultContent;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                this.showToastMessage('已复制到剪贴板');
            }
        },

        // 下载结果
        downloadResult() {
            const content = this.resultContent;
            const type = this.allResults ? this.activeTab : this.resultType;
            const filename = {
                stream_script: `直播稿_${this.getDateTimeString()}.txt`,
                article: `公众号文章_${this.getDateTimeString()}.md`,
                deep_dive: `深度长文_${this.getDateTimeString()}.md`
            }[type] || `生成内容_${this.getDateTimeString()}.txt`;

            const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showToastMessage('下载成功');
        },

        // 保存设置
        saveSettings() {
            try {
                localStorage.setItem('finance_streamer_settings', JSON.stringify(this.settings));
            } catch (_) {}
            this.showSettings = false;
            this.showToastMessage('设置已保存');
        },

        // ── 历史记录 ──────────────────────────────────────────────

        _typeLabel(type) {
            return { stream_script: '直播稿', article: '公众号', deep_dive: '深度长文' }[type] || type;
        },

        _addToHistory(type, content) {
            if (!content || !content.trim()) return;
            const entry = {
                id: Date.now(),
                type,
                typeLabel: this._typeLabel(type),
                preview: content.replace(/\s+/g, ' ').trim().slice(0, 60),
                content,
                wordCount: content.replace(/\s/g, '').length,
                savedAt: new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
            };
            this.history.unshift(entry);
            if (this.history.length > HISTORY_MAX) this.history = this.history.slice(0, HISTORY_MAX);
            saveHistory(this.history);
        },

        restoreHistory(entry) {
            this.allResults = null;
            this.resultType = entry.type;
            this.result = entry.type === 'article'
                ? { content: entry.content, titles: [], html: '' }
                : entry.content;
            this.showHistory = false;
            this.showToastMessage(`已恢复：${entry.typeLabel}`);
        },

        deleteHistory(id) {
            this.history = this.history.filter(h => h.id !== id);
            saveHistory(this.history);
        },

        clearHistory() {
            this.history = [];
            saveHistory([]);
            this.showToastMessage('历史记录已清空');
        },

        // 获取时间字符串
        getDateTimeString() {
            return new Date().toISOString().slice(0, 10).replace(/-/g, '');
        },

        // 显示提示
        showToastMessage(message) {
            this.toastMessage = message;
            this.showToast = true;
            setTimeout(() => {
                this.showToast = false;
            }, 2500);
        }
    },

    mounted() {
        this.updateTime();
        this.timer = setInterval(this.updateTime, 1000);
        this.fetchNews();
    },

    beforeUnmount() {
        if (this.timer) {
            clearInterval(this.timer);
        }
    }
}).mount('#app');

