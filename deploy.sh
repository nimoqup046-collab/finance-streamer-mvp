#!/bin/bash
# 财经主播助手 - 阿里云一键部署脚本
# 适用于 CentOS/AlmaLinux 系统

echo "🚀 开始部署财经主播助手..."

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 安装系统依赖
echo "📦 安装系统依赖..."
yum install -y python3 python3-pip nginx git wget

# 2. 创建应用目录
APP_DIR="/var/www/finance-assistant"
mkdir -p $APP_DIR
cd $APP_DIR

# 3. 克隆代码（修改为你的仓库地址）
echo "📥 拉取代码..."
# git clone https://github.com/your-username/finance-streamer-mvp.git .
# 如果代码已经存在，先删除
if [ ! -f "requirements.txt" ]; then
    echo "⚠️  请先将代码上传到服务器，或修改脚本中的 git clone 地址"
    echo "   你可以手动将代码复制到 $APP_DIR 目录"
    exit 1
fi

# 4. 安装 Python 依赖
echo "🐍 安装 Python 依赖..."
pip3 install -r requirements.txt

# 5. 创建环境变量文件
if [ ! -f ".env" ]; then
    echo "📝 创建环境变量文件..."
    cat > .env << 'EOF'
# AI 配置（默认豆包）
AI_PROVIDER=doubao
DOUBAO_API_KEY=your-api-key-here
DOUBAO_API_BASE=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_ENDPOINT_ID=
DOUBAO_MODEL=doubao-1-5-pro-32k-250115

# 服务配置
PORT=8000
CORS_ORIGINS=*
NEWS_CACHE_MINUTES=30
USE_MOCK_NEWS=false
EOF
    echo "⚠️  请编辑 .env 文件，填入你的 AI API Key"
    echo "   位置: $APP_DIR/.env"
fi

# 6. 创建 systemd 服务
echo "🔧 配置系统服务..."
cat > /etc/systemd/system/finance-assistant.service << EOF
[Unit]
Description=Finance Streamer Assistant
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. 配置 Nginx
echo "🌐 配置 Nginx..."
cat > /etc/nginx/conf.d/finance-assistant.conf << 'EOF'
server {
    listen 80;
    server_name _;

    # 前端静态文件
    location / {
        root /var/www/finance-assistant/frontend;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

# 测试 Nginx 配置
nginx -t

# 8. 启动服务
echo "▶️  启动服务..."
systemctl daemon-reload
systemctl enable finance-assistant
systemctl start finance-assistant
systemctl restart nginx

# 9. 检查服务状态
echo ""
echo "✅ 部署完成！"
echo ""
echo "📊 服务状态："
systemctl status finance-assistant --no-pager -l
echo ""
echo "🌐 访问地址："
echo "   http://$(curl -s ifconfig.me)"
echo ""
echo "📝 下一步："
echo "   1. 编辑环境变量: vi $APP_DIR/.env"
echo "   2. 填入 AI API Key"
echo "   3. 重启服务: systemctl restart finance-assistant"
echo ""
