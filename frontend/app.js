// 财经主播助手 MVP - 前端逻辑
const { createApp } = Vue;

const API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : window.location.origin;

createApp({
    data() {
        return {
            // 新闻数据
            news: [],
            selectedNews: [],
            filterCategory: '全部',

            // 分类
            categories: ['全部', '宏观', 'A股', '美股', '行业', '个股', '财经'],

            // 状态
            loading: false,
            generating: false,

            // 生成结果
            result: null,
            resultType: '',

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
            if (this.filterCategory === '全部') {
                return this.news;
            }
            return this.news.filter(n => n.category === this.filterCategory);
        },

        selectedCount() {
            return this.selectedNews.length;
        },

        allSelected: {
            get() {
                return this.filteredNews.length > 0 &&
                    this.filteredNews.every(n => this.selectedNews.includes(n.id));
            },
            set(value) {
                // 由 toggleAll 方法处理
            }
        },

        resultTitle() {
            const titles = {
                stream_script: '📝 直播稿',
                article: '📱 公众号文章',
                deep_dive: '📄 深度长文'
            };
            return titles[this.resultType] || '生成结果';
        },

        resultContent() {
            if (!this.result) return '';

            if (this.resultType === 'article' && this.result.content) {
                return this.result.content;
            }
            return this.result;
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
                        this.showToastMessage(`刷新成功，获取 ${data.count} 条新闻`);
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

        // 全选/取消全选
        toggleAll() {
            if (this.allSelected) {
                // 取消全选
                this.filteredNews.forEach(n => {
                    const index = this.selectedNews.indexOf(n.id);
                    if (index > -1) {
                        this.selectedNews.splice(index, 1);
                    }
                });
            } else {
                // 全选
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
            this.result = null;
            this.resultType = type;

            try {
                const response = await fetch(`${API_BASE}/api/generate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        news_ids: this.selectedNews,
                        content_type: type,
                        duration: 30,
                        style: '专业'
                    })
                });

                const data = await response.json();

                if (data.content || data.data) {
                    this.result = data.content || data;
                    this.showToastMessage('生成成功！');
                } else {
                    throw new Error('生成失败');
                }
            } catch (error) {
                console.error('生成失败:', error);
                this.showToastMessage('生成失败，请重试');
            } finally {
                this.generating = false;
            }
        },

        // 一键生成全部
        async generateAll() {
            if (this.selectedCount === 0) {
                this.showToastMessage('请先选择新闻');
                return;
            }

            this.generating = true;

            try {
                const response = await fetch(`${API_BASE}/api/generate/all`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.selectedNews)
                });

                const data = await response.json();

                // 默认显示直播稿
                this.resultType = 'stream_script';
                this.result = data.stream_script || '生成失败';

                // 存储其他结果供下载
                this.allResults = data;

                this.showToastMessage('全部生成完成！');
            } catch (error) {
                console.error('生成失败:', error);
                this.showToastMessage('生成失败，请重试');
            } finally {
                this.generating = false;
            }
        },

        // 复制结果
        async copyResult() {
            try {
                await navigator.clipboard.writeText(this.resultContent);
                this.showToastMessage('已复制到剪贴板');
            } catch (error) {
                // 降级方案
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
            const filename = {
                stream_script: `直播稿_${this.getDateTimeString()}.txt`,
                article: `公众号文章_${this.getDateTimeString()}.md`,
                deep_dive: `深度长文_${this.getDateTimeString()}.md`
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

            this.showToastMessage('下载成功');
        },

        // 获取时间字符串
        getDateTimeString() {
            const now = new Date();
            return now.toISOString().slice(0, 10).replace(/-/g, '');
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
        // 初始化
        this.updateTime();
        this.timer = setInterval(this.updateTime, 1000);

        // 加载新闻
        this.fetchNews();
    },

    beforeUnmount() {
        if (this.timer) {
            clearInterval(this.timer);
        }
    }
}).mount('#app');
