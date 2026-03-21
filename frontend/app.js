// 财经主播助手 MVP - 前端逻辑
const { createApp } = Vue;

const DEFAULT_API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : window.location.origin;
const API_BASE = (window.API_BASE && String(window.API_BASE).trim())
    ? String(window.API_BASE).replace(/\/+$/, '')
    : DEFAULT_API_BASE;

function loadSettings() {
    try {
        const saved = localStorage.getItem('finance_streamer_settings');
        if (saved) return JSON.parse(saved);
    } catch (_) {}
    return { duration: 30, style: '洞察', apiKey: '', persona: { invest_style: '', catchphrases: '', ip_desc: '' } };
}

const PROGRESS_STEPS = [
    { text: '分析新闻内容...', tip: '正在提取关键信息和数据要点' },
    { text: '构建内容框架...', tip: '规划内容结构和叙述逻辑' },
    { text: 'AI正在撰写...', tip: '根据风格设置生成专业内容' },
    { text: '优化润色中...', tip: '检查表达流畅性和专业性' },
];

createApp({
    data() {
        const settings = loadSettings();
        return {
            // 新闻数据
            news: [],
            selectedNews: [],
            filterCategory: '全部',
            categories: ['全部', '宏观', 'A股', '美股', '行业', '个股', '财经'],
            newsSort: 'hot',
            newsLimit: 100,

            // 搜索
            searchQuery: '',

            // 收藏
            favorites: [],
            showFavoritesOnly: false,

            // 生成参数
            duration: settings.duration || 30,
            style: settings.style || '洞察',
            apiKey: settings.apiKey || '',
            showSettings: false,
            styleOptions: ['洞察', '解读型', '专业', '轻松'],
            durationOptions: [15, 30, 60],

            // 主播人设/IP记忆库（核心壁垒 2）
            persona: settings.persona || { invest_style: '', catchphrases: '', ip_desc: '' },

            // 状态
            loading: false,
            generating: false,
            generatingPpt: false,
            checkingCompliance: false,

            // 进度步骤
            progressStep: 0,
            progressTimer: null,
            progressSteps: PROGRESS_STEPS,
            streamingPreview: '',

            // 生成结果
            result: null,
            resultType: '',
            allResults: null,
            matrixResult: null,   // 内容矩阵结果（核心壁垒 3）
            activeResultTab: 'stream_script',

            // 合规审核结果（核心壁垒 1）
            complianceResult: null,

            // 在线编辑
            editingContent: false,
            editableContent: '',

            // 已选新闻摘要折叠状态
            showSelectedDetail: false,

            // 历史记录
            history: [],
            showHistory: false,

            // Toast
            showToast: false,
            toastMessage: '',
            toastType: '',

            // 时间
            currentTime: '',
            timer: null,

            // Tab配置
            resultTabs: [
                { key: 'stream_script', label: '📝 直播稿' },
                { key: 'article', label: '📱 公众号' },
                { key: 'deep_dive', label: '📄 深度长文' },
                { key: 'ppt_script', label: '🖥️ PPT脚本' },
                { key: 'flash_report', label: '⚡ 快报速评' },
            ],

            // 内容矩阵 Tab 配置（核心壁垒 3）
            matrixTabs: [
                { key: 'moments_copy', label: '📣 朋友圈预热' },
                { key: 'stream_script', label: '📝 直播稿' },
                { key: 'article', label: '📱 复盘文章' },
                { key: 'ppt_script', label: '🖥️ PPT脚本' },
            ],
        };
    },

    computed: {
        filteredNews() {
            let list = this.news;
            if (this.showFavoritesOnly) {
                list = list.filter(n => this.favorites.includes(n.id));
            } else if (this.filterCategory !== '全部') {
                list = list.filter(n => n.category === this.filterCategory);
            }
            if (this.searchQuery.trim()) {
                const q = this.searchQuery.trim().toLowerCase();
                list = list.filter(n =>
                    n.title.toLowerCase().includes(q) ||
                    (n.category || '').toLowerCase().includes(q) ||
                    (n.source || '').toLowerCase().includes(q)
                );
            }
            return list;
        },

        selectedCount() {
            return this.selectedNews.length;
        },

        allSelected() {
            return this.filteredNews.length > 0 &&
                this.filteredNews.every(n => this.selectedNews.includes(n.id));
        },

        resultTitle() {
            const titles = {
                stream_script: '📝 直播稿（刘润×小Lin说融合风格）',
                article: this.matrixResult ? '📱 复盘文章（盘后深度版）' : '📱 公众号文章（深度好文版）',
                deep_dive: '📄 深度长文（原创研究版）',
                ppt_script: '🖥️ PPT演讲脚本',
                moments_copy: '📣 朋友圈预热文案（50字诱饵）',
                flash_report: '⚡ 快报速评（30秒抓主线版）',
            };
            return titles[this.resultType] || '生成结果';
        },

        displayContent() {
            if (!this.result) return '';
            if (this.resultType === 'article' && this.result.content) {
                return this.result.content;
            }
            if (typeof this.result === 'string') return this.result;
            return JSON.stringify(this.result, null, 2);
        },

        wordCount() {
            const text = this.editingContent ? this.editableContent : this.displayContent;
            if (!text) return 0;
            const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
            const englishWords = (text.match(/\b[a-zA-Z]+\b/g) || []).length;
            return chineseChars + englishWords;
        },

        readTime() {
            return Math.max(1, Math.ceil(this.wordCount / 500));
        },
    },

    methods: {
        buildHeaders() {
            const headers = { 'Content-Type': 'application/json' };
            if (this.apiKey) {
                headers['X-API-Key'] = this.apiKey;
            }
            return headers;
        },

        buildPersona() {
            const { invest_style, catchphrases, ip_desc } = this.persona || {};
            if (!invest_style && !catchphrases && !ip_desc) return null;
            return { invest_style: invest_style || '', catchphrases: catchphrases || '', ip_desc: ip_desc || '' };
        },

        saveSettings() {
            try {
                localStorage.setItem('finance_streamer_settings', JSON.stringify({
                    duration: this.duration,
                    style: this.style,
                    apiKey: this.apiKey,
                    persona: this.persona,
                }));
                this.showToastMessage('设置已保存', 'success');
            } catch (error) {
                console.error('保存设置失败:', error);
                this.showToastMessage('保存设置失败', 'error');
            } finally {
                this.showSettings = false;
            }
        },

        // 更新时间
        updateTime() {
            const now = new Date();
            this.currentTime = now.toLocaleString('zh-CN', {
                month: 'long',
                day: 'numeric',
                weekday: 'long',
                hour: '2-digit',
                minute: '2-digit',
            });
        },

        // 获取新闻
        async fetchNews(refresh = false) {
            this.loading = true;
            try {
                const response = await fetch(
                    `${API_BASE}/api/news?refresh=${refresh}&limit=${this.newsLimit}&sort=${this.newsSort}`
                );
                const data = await response.json();
                if (data.data) {
                    this.news = data.data;
                    if (!refresh && data.cached) {
                        this.showToastMessage(`已加载缓存数据 (${data.count}/${data.total_count || data.count}条)`, 'info');
                    } else {
                        const fallbackNote = data.fallback ? '（模拟数据）' : '';
                        const sortLabel = this.newsSort === 'hot' ? '热点优先' : '最新优先';
                        this.showToastMessage(`刷新成功，获取 ${data.count}/${data.total_count || data.count} 条新闻（${sortLabel}）${fallbackNote}`, 'success');
                    }
                }
            } catch (error) {
                console.error('获取新闻失败:', error);
                this.showToastMessage('获取新闻失败，请检查网络', 'error');
            } finally {
                this.loading = false;
            }
        },

        refreshNews() {
            this.fetchNews(true);
        },

        setNewsSort(sort) {
            this.newsSort = sort;
            this.fetchNews(true);
        },

        // 分类切换
        setCategory(cat) {
            this.filterCategory = cat;
            this.showFavoritesOnly = false;
        },

        // 全选 / 取消全选
        toggleAll() {
            if (this.allSelected) {
                this.filteredNews.forEach(n => {
                    const index = this.selectedNews.indexOf(n.id);
                    if (index > -1) this.selectedNews.splice(index, 1);
                });
            } else {
                this.filteredNews.forEach(n => {
                    if (!this.selectedNews.includes(n.id)) {
                        this.selectedNews.push(n.id);
                    }
                });
            }
        },

        // 切换单条新闻选中
        toggleNewsSelection(id) {
            const index = this.selectedNews.indexOf(id);
            if (index > -1) {
                this.selectedNews.splice(index, 1);
            } else {
                this.selectedNews.push(id);
            }
        },

        removeFromSelected(id) {
            const index = this.selectedNews.indexOf(id);
            if (index > -1) this.selectedNews.splice(index, 1);
        },

        getNewsTitle(id) {
            const item = this.news.find(n => n.id === id);
            return item ? item.title : id;
        },

        // 收藏
        toggleFavorite(id) {
            const index = this.favorites.indexOf(id);
            if (index > -1) {
                this.favorites.splice(index, 1);
                this.showToastMessage('已取消收藏', 'info');
            } else {
                this.favorites.push(id);
                this.showToastMessage('已收藏 ⭐', 'success');
            }
            this.saveFavorites();
        },

        isFavorited(id) {
            return this.favorites.includes(id);
        },

        saveFavorites() {
            try {
                localStorage.setItem('finance_favorites', JSON.stringify(this.favorites));
            } catch (e) {}
        },

        loadFavorites() {
            try {
                const saved = localStorage.getItem('finance_favorites');
                if (saved) this.favorites = JSON.parse(saved);
            } catch (e) {}
        },

        // 搜索关键词高亮
        highlightSearch(title) {
            if (!this.searchQuery.trim()) return title;
            const q = this.searchQuery.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${q})`, 'gi');
            return title.replace(regex, '<mark>$1</mark>');
        },

        // 进度步骤
        startProgress() {
            this.progressStep = 0;
            this.progressTimer = setInterval(() => {
                if (this.progressStep < PROGRESS_STEPS.length - 1) {
                    this.progressStep++;
                }
            }, 3000);
        },

        stopProgress() {
            if (this.progressTimer) {
                clearInterval(this.progressTimer);
                this.progressTimer = null;
            }
            this.progressStep = PROGRESS_STEPS.length - 1;
        },

        async streamGenerate(payload, handlers = {}) {
            const response = await fetch(`${API_BASE}/api/generate/stream`, {
                method: 'POST',
                headers: this.buildHeaders(),
                body: JSON.stringify(payload),
            });

            if (!response.ok || !response.body) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            const dispatch = (rawEvent) => {
                if (!rawEvent.trim()) return;
                const lines = rawEvent.split('\n');
                let eventName = 'message';
                let data = '';

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        eventName = line.slice(6).trim();
                    } else if (line.startsWith('data:')) {
                        data += line.slice(5).trim();
                    }
                }

                if (!data) return;
                const parsed = JSON.parse(data);
                const handler = handlers[eventName];
                if (handler) handler(parsed);
            };

            while (true) {
                const { value, done } = await reader.read();
                buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

                const chunks = buffer.split('\n\n');
                buffer = chunks.pop() || '';
                chunks.forEach(dispatch);

                if (done) break;
            }

            if (buffer.trim()) {
                dispatch(buffer);
            }
        },

        async generateContentFallback(type) {
            const response = await fetch(`${API_BASE}/api/generate`, {
                method: 'POST',
                headers: this.buildHeaders(),
                body: JSON.stringify({
                    news_ids: this.selectedNews,
                    content_type: type,
                    duration: this.duration,
                    style: this.style,
                    persona: this.buildPersona(),
                }),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data.content !== undefined || data.titles) {
                this.result = type === 'article' ? data : (data.content || data);
                this.saveToHistory(type, this.result);
                return;
            }
            throw new Error('生成失败');
        },

        async generateAllFallback() {
            const response = await fetch(`${API_BASE}/api/generate/all`, {
                method: 'POST',
                headers: this.buildHeaders(),
                body: JSON.stringify(this.selectedNews),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            this.allResults = data;
            this.activeResultTab = 'stream_script';
            this.resultType = 'stream_script';
            this.result = data.stream_script || '生成失败';
            this.saveToHistory('stream_script', data.stream_script);
            if (data.article) this.saveToHistory('article', data.article);
            if (data.deep_dive) this.saveToHistory('deep_dive', data.deep_dive);
            if (data.ppt_script) this.saveToHistory('ppt_script', data.ppt_script);
        },

        // 生成内容
        async generateContent(type) {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻', 'warning');
                return;
            }

            this.generating = true;
            this.result = null;
            this.allResults = null;
            this.matrixResult = null;
            this.resultType = type;
            this.editingContent = false;
            this.streamingPreview = '';
            this.complianceResult = null;
            this.startProgress();

            try {
                if (type === 'stream_script') {
                    await this.streamGenerate(
                        {
                            news_ids: this.selectedNews,
                            content_type: type,
                            duration: this.duration,
                            style: this.style,
                            persona: this.buildPersona(),
                        },
                        {
                            status: (event) => {
                                if (typeof event.step === 'number') {
                                    this.progressStep = event.step;
                                }
                            },
                            chunk: (event) => {
                                this.streamingPreview += event.delta || '';
                            },
                            complete: (event) => {
                                this.result = event.result;
                                this.saveToHistory(type, this.result);
                            },
                            error: (event) => {
                                throw new Error(event.message || '流式生成失败');
                            },
                        },
                    );
                } else {
                    await this.generateContentFallback(type);
                }
                this.showToastMessage('✅ 生成成功！', 'success');
            } catch (error) {
                console.error('生成失败:', error);
                if (type === 'stream_script') {
                    try {
                        this.showToastMessage('流式生成失败，正在回退普通生成…', 'warning');
                        await this.generateContentFallback(type);
                        this.showToastMessage('✅ 已回退为普通生成', 'success');
                    } catch (fallbackError) {
                        console.error('回退生成失败:', fallbackError);
                        this.showToastMessage(`❌ 生成失败：${fallbackError.message}`, 'error');
                    }
                } else {
                    this.showToastMessage(`❌ 生成失败：${error.message}`, 'error');
                }
            } finally {
                this.generating = false;
                this.stopProgress();
            }
        },

        // 全部生成
        async generateAll() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻', 'warning');
                return;
            }

            this.generating = true;
            this.result = null;
            this.allResults = null;
            this.matrixResult = null;
            this.editingContent = false;
            this.streamingPreview = '';
            this.complianceResult = null;
            this.startProgress();

            try {
                await this.streamGenerate(
                    {
                        news_ids: this.selectedNews,
                        content_type: 'all',
                        duration: this.duration,
                        style: this.style,
                        persona: this.buildPersona(),
                    },
                    {
                        status: (event) => {
                            if (typeof event.step === 'number') {
                                this.progressStep = event.step;
                            }
                        },
                        chunk: (event) => {
                            if (event.result_type === 'stream_script') {
                                this.streamingPreview += event.delta || '';
                            }
                        },
                        result: (event) => {
                            if (!this.allResults) {
                                this.allResults = {};
                            }
                            this.allResults[event.result_type] = event.result;
                            if (event.result_type === 'stream_script') {
                                this.resultType = 'stream_script';
                                this.activeResultTab = 'stream_script';
                                this.result = event.result;
                            }
                        },
                        complete: (event) => {
                            this.allResults = event.results;
                            this.activeResultTab = 'stream_script';
                            this.resultType = 'stream_script';
                            this.result = event.results.stream_script || '生成失败';
                            this.saveToHistory('stream_script', event.results.stream_script);
                            this.saveToHistory('article', event.results.article);
                            this.saveToHistory('deep_dive', event.results.deep_dive);
                            if (event.results.ppt_script) this.saveToHistory('ppt_script', event.results.ppt_script);
                        },
                        error: (event) => {
                            throw new Error(event.message || '流式生成失败');
                        },
                    },
                );
                this.showToastMessage('✅ 全部生成完成！', 'success');
            } catch (error) {
                console.error('生成失败:', error);
                try {
                    this.showToastMessage('流式生成失败，正在回退普通全部生成…', 'warning');
                    await this.generateAllFallback();
                    this.showToastMessage('✅ 已回退为普通全部生成', 'success');
                } catch (fallbackError) {
                    console.error('全部生成回退失败:', fallbackError);
                    this.showToastMessage(`❌ 全部生成失败：${fallbackError.message}`, 'error');
                }
            } finally {
                this.generating = false;
                this.stopProgress();
            }
        },

        // 一键内容矩阵（核心壁垒 3）
        async generateMatrix() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻', 'warning');
                return;
            }

            this.generating = true;
            this.result = null;
            this.allResults = null;
            this.matrixResult = null;
            this.editingContent = false;
            this.streamingPreview = '';
            this.complianceResult = null;
            this.startProgress();

            try {
                const response = await fetch(`${API_BASE}/api/generate/matrix`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify({
                        news_ids: this.selectedNews,
                        focus_topic: '',
                        duration: this.duration,
                        style: this.style,
                        persona: this.buildPersona(),
                    }),
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const data = await response.json();
                this.matrixResult = data;
                this.activeResultTab = 'moments_copy';
                this.resultType = 'moments_copy';
                this.result = data.moments_copy || '';

                // Save all matrix items to history
                if (data.moments_copy) this.saveToHistory('moments_copy', data.moments_copy);
                if (data.stream_script) this.saveToHistory('stream_script', data.stream_script);
                if (data.article) this.saveToHistory('article', data.article);
                if (data.ppt_script) this.saveToHistory('ppt_script', data.ppt_script);

                this.showToastMessage('✅ 内容矩阵生成完成！', 'success');
            } catch (error) {
                console.error('内容矩阵生成失败:', error);
                this.showToastMessage(`❌ 内容矩阵生成失败：${error.message}`, 'error');
            } finally {
                this.generating = false;
                this.stopProgress();
            }
        },

        // 切换内容矩阵 Tab
        switchMatrixTab(tab) {
            this.activeResultTab = tab;
            this.resultType = tab;
            this.editingContent = false;
            if (this.matrixResult) {
                if (tab === 'moments_copy') this.result = this.matrixResult.moments_copy;
                else if (tab === 'stream_script') this.result = this.matrixResult.stream_script;
                else if (tab === 'article') this.result = this.matrixResult.article;
                else if (tab === 'ppt_script') this.result = this.matrixResult.ppt_script;
            }
        },

        // 合规审核（核心壁垒 1）
        async checkCompliance() {
            const content = this.editingContent ? this.editableContent : this.displayContent;
            if (!content || !content.trim()) {
                this.showToastMessage('没有可审核的内容', 'warning');
                return;
            }

            this.checkingCompliance = true;
            this.complianceResult = null;
            try {
                const response = await fetch(`${API_BASE}/api/compliance/check`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify({ content }),
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                this.complianceResult = await response.json();
                if (this.complianceResult.is_compliant) {
                    this.showToastMessage('✅ 合规审核通过，未发现风险点', 'success');
                } else {
                    this.showToastMessage(`⚠️ 发现 ${this.complianceResult.issues.length} 处合规风险，请查看报告`, 'warning');
                }
            } catch (error) {
                console.error('合规审核失败:', error);
                this.showToastMessage(`❌ 合规审核失败：${error.message}`, 'error');
            } finally {
                this.checkingCompliance = false;
            }
        },

        // 应用合规改写版本
        applyRevisedContent() {
            if (!this.complianceResult || !this.complianceResult.revised_content) return;
            const revised = this.complianceResult.revised_content;
            if (typeof this.result === 'string') {
                this.result = revised;
            } else if (this.result && this.result.content) {
                this.result = { ...this.result, content: revised };
            }
            this.complianceResult = null;
            this.showToastMessage('✅ 已应用合规改写版本', 'success');
        },

        async generatePpt() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻', 'warning');
                return;
            }

            this.generatingPpt = true;
            try {
                const response = await fetch(`${API_BASE}/api/generate/ppt`, {
                    method: 'POST',
                    headers: this.buildHeaders(),
                    body: JSON.stringify(this.selectedNews),
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;

                const disposition = response.headers.get('Content-Disposition') || '';
                const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
                let filename = `财经日报_${this.getDateTimeString()}.pptx`;
                if (match) {
                    const raw = decodeURIComponent(match[1]).replace(/['"]/g, '').trim();
                    filename = raw.replace(/[/\\:*?"<>|]/g, '_');
                }

                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                this.showToastMessage('PPT 已生成并下载！', 'success');
            } catch (error) {
                console.error('PPT生成失败:', error);
                this.showToastMessage(`PPT生成失败：${error.message}`, 'error');
            } finally {
                this.generatingPpt = false;
            }
        },

        // 切换结果Tab（全部生成后）
        switchResultTab(tab) {
            this.activeResultTab = tab;
            this.resultType = tab;
            this.editingContent = false;
            if (this.allResults) {
                if (tab === 'stream_script') this.result = this.allResults.stream_script;
                else if (tab === 'article') this.result = this.allResults.article;
                else if (tab === 'deep_dive') this.result = this.allResults.deep_dive;
                else if (tab === 'ppt_script') this.result = this.allResults.ppt_script;
                else if (tab === 'flash_report') this.result = this.allResults.flash_report;
            }
        },

        // 在线编辑
        startEditing() {
            this.editableContent = this.displayContent;
            this.editingContent = true;
        },

        saveEditing() {
            if (typeof this.result === 'string') {
                this.result = this.editableContent;
            } else if (this.result && this.result.content) {
                this.result = { ...this.result, content: this.editableContent };
            }
            this.editingContent = false;
            this.showToastMessage('✅ 已保存修改', 'success');
        },

        cancelEditing() {
            this.editingContent = false;
            this.editableContent = '';
        },

        closeResult() {
            this.result = null;
            this.allResults = null;
            this.matrixResult = null;
            this.complianceResult = null;
            this.editingContent = false;
        },

        // 复制
        async copyResult() {
            const content = this.editingContent ? this.editableContent : this.displayContent;
            try {
                await navigator.clipboard.writeText(content);
                this.showToastMessage('✅ 已复制到剪贴板', 'success');
            } catch (error) {
                const textarea = document.createElement('textarea');
                textarea.value = content;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                this.showToastMessage('✅ 已复制到剪贴板', 'success');
            }
        },

        // 复制富文本（微信公众号用）
        async copyRichText() {
            const html = (this.result && this.result.html) ? this.result.html : this.displayContent;
            try {
                const blob = new Blob([html], { type: 'text/html' });
                const clipItem = new ClipboardItem({ 'text/html': blob });
                await navigator.clipboard.write([clipItem]);
                this.showToastMessage('✅ 已复制富文本，可直接粘贴到微信编辑器', 'success');
            } catch (e) {
                // 降级：复制HTML源码
                await navigator.clipboard.writeText(html).catch(() => {});
                this.showToastMessage('已复制HTML代码', 'info');
            }
        },

        // 下载
        downloadResult() {
            const content = this.editingContent ? this.editableContent : this.displayContent;
            const filename = {
                stream_script: `直播稿_${this.getDateTimeString()}.txt`,
                article: `公众号文章_${this.getDateTimeString()}.md`,
                deep_dive: `深度长文_${this.getDateTimeString()}.md`,
                ppt_script: `PPT脚本_${this.getDateTimeString()}.md`,
                moments_copy: `朋友圈预热_${this.getDateTimeString()}.txt`,
                flash_report: `快报速评_${this.getDateTimeString()}.txt`,
            }[this.resultType] || `生成内容_${this.getDateTimeString()}.txt`;

            const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            this.showToastMessage('✅ 下载成功', 'success');
        },

        // 历史记录
        saveToHistory(type, content) {
            const titles = {
                stream_script: '直播稿',
                article: '公众号文章',
                deep_dive: '深度长文',
                ppt_script: 'PPT脚本',
                moments_copy: '朋友圈预热',
                flash_report: '快报速评',
            };
            const text = typeof content === 'string'
                ? content
                : (content && content.content ? content.content : JSON.stringify(content));

            const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
            const preview = text.replace(/\s+/g, ' ').slice(0, 40) + '...';

            const item = {
                type,
                title: titles[type] || '生成内容',
                content,
                preview,
                wordCount: chineseChars,
                newsCount: this.selectedCount,
                createdAt: new Date().toLocaleString('zh-CN', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                }),
            };

            this.history.unshift(item);
            if (this.history.length > 10) this.history.pop();

            try {
                localStorage.setItem('finance_history', JSON.stringify(this.history));
            } catch (e) {}
        },

        loadHistory() {
            try {
                const saved = localStorage.getItem('finance_history');
                if (saved) this.history = JSON.parse(saved);
            } catch (e) {}
        },

        restoreHistory(item) {
            this.resultType = item.type;
            this.result = item.content;
            this.allResults = null;
            this.editingContent = false;
            this.showHistory = false;
            this.showToastMessage('✅ 已恢复历史记录', 'success');
        },

        clearHistory() {
            this.history = [];
            localStorage.removeItem('finance_history');
            this.showToastMessage('历史记录已清空', 'info');
        },

        toggleHistory() {
            this.showHistory = !this.showHistory;
        },

        // 工具方法
        getDateTimeString() {
            return new Date().toISOString().slice(0, 10).replace(/-/g, '');
        },

        showToastMessage(message, type = 'info') {
            this.toastMessage = message;
            this.toastType = type;
            this.showToast = true;
            setTimeout(() => {
                this.showToast = false;
            }, 2500);
        },

        // 键盘快捷键
        handleKeyboard(e) {
            // Ctrl/Cmd + G：快速生成直播稿
            if ((e.ctrlKey || e.metaKey) && e.key === 'g') {
                e.preventDefault();
                if (this.selectedCount > 0 && !this.generating) {
                    this.generateContent('stream_script');
                } else if (this.selectedCount === 0) {
                    this.showToastMessage('请先选择新闻', 'warning');
                }
            }
            // Escape：关闭面板
            if (e.key === 'Escape') {
                if (this.showHistory) {
                    this.showHistory = false;
                } else if (this.editingContent) {
                    this.cancelEditing();
                } else if (this.result) {
                    this.closeResult();
                }
            }
        },
    },

    mounted() {
        this.updateTime();
        this.timer = setInterval(this.updateTime, 1000);
        this.fetchNews();
        this.loadHistory();
        this.loadFavorites();
        document.addEventListener('keydown', this.handleKeyboard);
    },

    beforeUnmount() {
        if (this.timer) clearInterval(this.timer);
        if (this.progressTimer) clearInterval(this.progressTimer);
        document.removeEventListener('keydown', this.handleKeyboard);
    },
}).mount('#app');
