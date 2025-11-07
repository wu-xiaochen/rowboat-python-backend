#!/bin/bash

# Rowboat Python Backend 部署脚本
# 支持多种部署模式：开发、生产、Docker

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
ENVIRONMENT="development"
PORT=8000
WORKERS=1
LOG_LEVEL="INFO"
DOCKER_COMPOSE_FILE="docker-compose.yml"

# 函数定义
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
Rowboat Python Backend 部署脚本

用法: $0 [选项]

选项:
    -e, --environment   部署环境 (development|production|docker) [默认: development]
    -p, --port         服务端口 [默认: 8000]
    -w, --workers      工作进程数 [默认: 1]
    -l, --log-level    日志级别 [默认: INFO]
    -d, --docker-file  Docker Compose文件 [默认: docker-compose.yml]
    -s, --setup        仅设置环境，不启动服务
    -t, --test         运行测试
    -m, --migrate      运行数据迁移
    -c, --cleanup      清理Docker资源
    -h, --help         显示帮助信息

示例:
    $0                                          # 开发环境启动
    $0 -e production                           # 生产环境启动
    $0 -e docker -d docker-compose.prod.yml   # Docker生产环境
    $0 -t                                      # 运行测试
    $0 -m                                      # 数据迁移
    $0 -c                                      # 清理资源
EOF
}

check_dependencies() {
    log_info "检查依赖..."

    # 检查Python
    if ! command -v python3 > /dev/null; then
        log_error "Python 3 未安装"
        exit 1
    fi

    # 检查Docker（如果需要）
    if [[ "$ENVIRONMENT" == "docker" ]] || [[ "$ENVIRONMENT" == "production" ]]; then
        if ! command -v docker > /dev/null; then
            log_error "Docker 未安装"
            exit 1
        fi

        if ! command -v docker-compose > /dev/null; then
            log_error "Docker Compose 未安装"
            exit 1
        fi
    fi

    log_success "依赖检查通过"
}

setup_environment() {
    log_info "设置环境..."

    # 创建虚拟环境（如果不存在）
    if [[ ! -d "venv" ]]; then
        log_info "创建虚拟环境..."
        python3 -m venv venv
    fi

    # 激活虚拟环境
    source venv/bin/activate

    # 升级pip
    pip install --upgrade pip

    # 安装依赖
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log_info "安装生产环境依赖..."
        pip install -r requirements.txt
    else
        log_info "安装开发环境依赖..."
        pip install -r requirements-minimal.txt
    fi

    # 创建必要目录
    mkdir -p logs data uploads ssl

    # 创建环境文件（如果不存在）
    if [[ ! -f ".env" ]]; then
        log_info "创建环境文件..."
        cp .env.example .env
        log_warning "请编辑 .env 文件以配置您的环境"
    fi

    log_success "环境设置完成"
}

run_tests() {
    log_info "运行测试..."

    source venv/bin/activate

    # 运行基础测试
    if [[ -f "test_basic.py" ]]; then
        log_info "运行基础测试..."
        python test_basic.py
    fi

    # 运行API兼容性测试
    if [[ -f "test_api_compatibility.py" ]]; then
        log_info "运行API兼容性测试..."
        python test_api_compatibility.py
    fi

    log_success "测试完成"
}

run_migration() {
    log_info "运行数据迁移..."

    source venv/bin/activate

    if [[ -f "migrate_data.py" ]]; then
        log_info "执行数据迁移..."
        python migrate_data.py
    else
        log_warning "迁移脚本不存在"
    fi
}

start_development() {
    log_info "启动开发环境..."

    setup_environment

    # 数据库初始化
    log_info "初始化数据库..."
    python -c "from src.database import DatabaseManager; import asyncio; db = DatabaseManager(); asyncio.run(db.initialize())"

    # 启动服务
    log_info "启动开发服务器..."
    uvicorn src.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload \
        --log-level $LOG_LEVEL
}

start_production() {
    log_info "启动生产环境..."

    setup_environment

    # 数据库初始化
    log_info "初始化数据库..."
    python -c "from src.database import DatabaseManager; import asyncio; db = DatabaseManager(); asyncio.run(db.initialize())"

    # 启动服务
    log_info "启动生产服务器..."
    uvicorn src.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --workers $WORKERS \
        --log-level $LOG_LEVEL \
        --access-log
}

start_docker() {
    log_info "启动Docker环境..."

    # 构建镜像
    log_info "构建Docker镜像..."
    docker-compose -f $DOCKER_COMPOSE_FILE build

    # 启动服务
    log_info "启动Docker服务..."
    docker-compose -f $DOCKER_COMPOSE_FILE up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10

    # 健康检查
    log_info "执行健康检查..."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "服务启动成功！"
    else
        log_error "服务启动失败"
        docker-compose -f $DOCKER_COMPOSE_FILE logs
        exit 1
    fi
}

cleanup_docker() {
    log_info "清理Docker资源..."

    # 停止服务
    docker-compose -f $DOCKER_COMPOSE_FILE down

    # 删除镜像
    docker image prune -f

    # 删除卷（谨慎使用）
    read -p "是否删除数据卷？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume prune -f
    fi

    log_success "Docker资源清理完成"
}

show_status() {
    log_info "服务状态："

    if [[ "$ENVIRONMENT" == "docker" ]]; then
        docker-compose -f $DOCKER_COMPOSE_FILE ps
    else
        # 检查端口是否被占用
        if lsof -Pi :$PORT -sTCP:LISTEN -t > /dev/null 2>&1; then
            log_success "服务正在端口 $PORT 运行"
        else
            log_warning "服务未运行"
        fi
    fi
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -p|--port)
                PORT="$2"
                shift 2
                ;;
            -w|--workers)
                WORKERS="$2"
                shift 2
                ;;
            -l|--log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            -d|--docker-file)
                DOCKER_COMPOSE_FILE="$2"
                shift 2
                ;;
            -s|--setup)
                setup_environment
                exit 0
                ;;
            -t|--test)
                run_tests
                exit 0
                ;;
            -m|--migrate)
                run_migration
                exit 0
                ;;
            -c|--cleanup)
                cleanup_docker
                exit 0
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 检查依赖
    check_dependencies

    # 根据环境启动服务
    case $ENVIRONMENT in
        development)
            start_development
            ;;
        production)
            start_production
            ;;
        docker)
            start_docker
            ;;
        *)
            log_error "未知环境: $ENVIRONMENT"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"""# 生产环境部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.production.yml"
DOMAIN="your-domain.com"
EMAIL="your-email@example.com"

# 函数定义
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统要求
check_system_requirements() {
    log_info "检查系统要求..."

    # 检查内存（建议至少2GB）
    total_memory=$(free -m | awk '/^Mem:/ {print $2}')
    if [[ $total_memory -lt 2048 ]]; then
        log_warning "系统内存小于2GB，可能影响性能"
    fi

    # 检查磁盘空间（建议至少10GB）
    available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_disk -lt 10 ]]; then
        log_warning "可用磁盘空间小于10GB"
    fi

    log_success "系统要求检查完成"
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."

    # 更新系统包
    sudo apt update && sudo apt upgrade -y

    # 安装必要软件
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        htop \
        fail2ban \
        ufw \
        certbot \
        python3-certbot-nginx

    log_success "系统依赖安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."

    # 启用UFW
    sudo ufw --force enable

    # 默认策略
    sudo ufw default deny incoming
    sudo ufw default allow outgoing

    # 允许SSH
    sudo ufw allow ssh

    # 允许HTTP/HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp

    # 允许应用端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 8000
    sudo ufw allow from 172.16.0.0/12 to any port 8000
    sudo ufw allow from 192.168.0.0/16 to any port 8000

    # 允许监控端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 9090
    sudo ufw allow from 172.16.0.0/12 to any port 9090
    sudo ufw allow from 192.168.0.0/16 to any port 9090

    log_success "防火墙配置完成"
}

# 配置SSL证书
setup_ssl() {
    log_info "配置SSL证书..."

    # 创建SSL目录
    mkdir -p ssl

    # 使用Let's Encrypt获取证书
    if [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "your-domain.com" ]]; then
        sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive

        # 复制证书到项目目录
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
        sudo chown $USER:$USER ssl/*.pem
        sudo chmod 600 ssl/*.pem

        log_success "SSL证书配置完成"
    else
        log_warning "未配置域名，使用自签名证书"

        # 生成自签名证书（仅用于测试）
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem \
            -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

        chmod 600 ssl/*.pem
    fi
}

# 配置系统优化
setup_system_optimization() {
    log_info "配置系统优化..."

    # 增加文件描述符限制
    echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
    echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

    # 优化内核参数
    cat << EOF | sudo tee /etc/sysctl.d/99-rowboat.conf
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# 文件系统优化
fs.file-max = 2097152
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF

    sudo sysctl -p /etc/sysctl.d/99-rowboat.conf

    log_success "系统优化配置完成"
}

# 配置Docker
setup_docker() {
    log_info "配置Docker..."

    # 安装Docker（如果未安装）
    if ! command -v docker > /dev/null; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker $USER
    fi

    # 安装Docker Compose（如果未安装）
    if ! command -v docker-compose > /dev/null; then
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

    # 配置Docker守护进程
    cat << EOF | sudo tee /etc/docker/daemon.json
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ]
}
EOF

    sudo systemctl restart docker
    log_success "Docker配置完成"
}

# 部署应用
deploy_application() {
    log_info "部署应用..."

    # 构建镜像
    log_info "构建Docker镜像..."
    docker-compose -f $COMPOSE_FILE build --no-cache

    # 启动服务
    log_info "启动服务..."
    docker-compose -f $COMPOSE_FILE up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30

    # 健康检查
    log_info "执行健康检查..."
    max_attempts=30
    attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "服务启动成功！"
            break
        fi

        log_info "等待服务启动... (尝试 $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    if [[ $attempt -gt $max_attempts ]]; then
        log_error "服务启动失败"
        docker-compose -f $COMPOSE_FILE logs
        exit 1
    fi
}

# 配置监控
setup_monitoring() {
    log_info "配置监控..."

    # 等待监控服务启动
    sleep 10

    # 验证Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus 运行正常"
    else
        log_error "Prometheus 未运行"
    fi

    # 验证Grafana
    if curl -f http://localhost:3001/api/health > /dev/null 2>&1; then
        log_success "Grafana 运行正常"
    else
        log_error "Grafana 未运行"
    fi

    log_success "监控配置完成"
}

# 创建系统服务
create_system_service() {
    log_info "创建系统服务..."

    cat << EOF | sudo tee /etc/systemd/system/rowboat.service
[Unit]
Description=Rowboat Python Backend
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose -f $COMPOSE_FILE up -d
ExecStop=/usr/local/bin/docker-compose -f $COMPOSE_FILE down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable rowboat.service

    log_success "系统服务创建完成"
}

# 设置日志轮转
setup_log_rotation() {
    log_info "设置日志轮转..."

    cat << EOF | sudo tee /etc/logrotate.d/rowboat
/var/log/rowboat/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker-compose -f $COMPOSE_FILE kill -s USR1 rowboat-backend-prod
    endscript
}
EOF

    log_success "日志轮转配置完成"
}

# 创建备份脚本
create_backup_script() {
    log_info "创建备份脚本..."

    cat << 'EOF' > backup.sh
#!/bin/bash

# 备份目录
BACKUP_DIR="/opt/backups/rowboat"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose -f $COMPOSE_FILE exec -T rowboat-backend-prod sqlite3 /app/data/rowboat.db ".backup $BACKUP_DIR/database_$DATE.db"

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# 备份配置
cp .env $BACKUP_DIR/env_$DATE.backup

# 清理旧备份（保留30天）
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete

echo "备份完成: $DATE"
EOF

    chmod +x backup.sh

    # 添加到crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/backup.sh") | crontab -

    log_success "备份脚本创建完成"
}

# 显示部署信息
show_deployment_info() {
    log_info "部署信息："
    echo "=================================="
    echo "应用URL: https://$DOMAIN"
    echo "API文档: https://$DOMAIN/docs"
    echo "监控面板: http://$DOMAIN:3001"
    echo "Prometheus: http://$DOMAIN:9090"
    echo ""
    echo "Docker命令："
    echo "  查看日志: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  重启服务: docker-compose -f $COMPOSE_FILE restart"
    echo "  停止服务: docker-compose -f $COMPOSE_FILE down"
    echo ""
    echo "系统服务："
    echo "  启动: sudo systemctl start rowboat"
    echo "  停止: sudo systemctl stop rowboat"
    echo "  状态: sudo systemctl status rowboat"
    echo ""
    echo "备份："
    echo "  手动备份: ./backup.sh"
    echo "  自动备份: 每天凌晨2点"
    echo "=================================="
}

# 主函数
main() {
    log_info "开始生产环境部署..."

    # 检查系统要求
    check_system_requirements

    # 安装系统依赖
    install_system_dependencies

    # 配置防火墙
    setup_firewall

    # 配置SSL
    setup_ssl

    # 系统优化
    setup_system_optimization

    # 配置Docker
    setup_docker

    # 部署应用
    deploy_application

    # 配置监控
    setup_monitoring

    # 创建系统服务
    create_system_service

    # 设置日志轮转
    setup_log_rotation

    # 创建备份脚本
    create_backup_script

    # 显示部署信息
    show_deployment_info

    log_success "生产环境部署完成！"
}

# 运行主函数
main "$@""# 生产环境部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.production.yml"
DOMAIN="your-domain.com"
EMAIL="your-email@example.com"

# 函数定义
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统要求
check_system_requirements() {
    log_info "检查系统要求..."

    # 检查内存（建议至少2GB）
    total_memory=$(free -m | awk '/^Mem:/ {print $2}')
    if [[ $total_memory -lt 2048 ]]; then
        log_warning "系统内存小于2GB，可能影响性能"
    fi

    # 检查磁盘空间（建议至少10GB）
    available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_disk -lt 10 ]]; then
        log_warning "可用磁盘空间小于10GB"
    fi

    log_success "系统要求检查完成"
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."

    # 更新系统包
    sudo apt update && sudo apt upgrade -y

    # 安装必要软件
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        htop \
        fail2ban \
        ufw \
        certbot \
        python3-certbot-nginx

    log_success "系统依赖安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."

    # 启用UFW
    sudo ufw --force enable

    # 默认策略
    sudo ufw default deny incoming
    sudo ufw default allow outgoing

    # 允许SSH
    sudo ufw allow ssh

    # 允许HTTP/HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp

    # 允许应用端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 8000
    sudo ufw allow from 172.16.0.0/12 to any port 8000
    sudo ufw allow from 192.168.0.0/16 to any port 8000

    # 允许监控端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 9090
    sudo ufw allow from 172.16.0.0/12 to any port 9090
    sudo ufw allow from 192.168.0.0/16 to any port 9090

    log_success "防火墙配置完成"
}

# 配置SSL证书
setup_ssl() {
    log_info "配置SSL证书..."

    # 创建SSL目录
    mkdir -p ssl

    # 使用Let's Encrypt获取证书
    if [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "your-domain.com" ]]; then
        sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive

        # 复制证书到项目目录
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
        sudo chown $USER:$USER ssl/*.pem
        sudo chmod 600 ssl/*.pem

        log_success "SSL证书配置完成"
    else
        log_warning "未配置域名，使用自签名证书"

        # 生成自签名证书（仅用于测试）
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem \
            -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

        chmod 600 ssl/*.pem
    fi
}

# 配置系统优化
setup_system_optimization() {
    log_info "配置系统优化..."

    # 增加文件描述符限制
    echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
    echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

    # 优化内核参数
    cat << EOF | sudo tee /etc/sysctl.d/99-rowboat.conf
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# 文件系统优化
fs.file-max = 2097152
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF

    sudo sysctl -p /etc/sysctl.d/99-rowboat.conf

    log_success "系统优化配置完成"
}

# 配置Docker
setup_docker() {
    log_info "配置Docker..."

    # 安装Docker（如果未安装）
    if ! command -v docker > /dev/null; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker $USER
    fi

    # 安装Docker Compose（如果未安装）
    if ! command -v docker-compose > /dev/null; then
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

    # 配置Docker守护进程
    cat << EOF | sudo tee /etc/docker/daemon.json
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ]
}
EOF

    sudo systemctl restart docker
    log_success "Docker配置完成"
}

# 部署应用
deploy_application() {
    log_info "部署应用..."

    # 构建镜像
    log_info "构建Docker镜像..."
    docker-compose -f $COMPOSE_FILE build --no-cache

    # 启动服务
    log_info "启动服务..."
    docker-compose -f $COMPOSE_FILE up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30

    # 健康检查
    log_info "执行健康检查..."
    max_attempts=30
    attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "服务启动成功！"
            break
        fi

        log_info "等待服务启动... (尝试 $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    if [[ $attempt -gt $max_attempts ]]; then
        log_error "服务启动失败"
        docker-compose -f $COMPOSE_FILE logs
        exit 1
    fi
}

# 配置监控
setup_monitoring() {
    log_info "配置监控..."

    # 等待监控服务启动
    sleep 10

    # 验证Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus 运行正常"
    else
        log_error "Prometheus 未运行"
    fi

    # 验证Grafana
    if curl -f http://localhost:3001/api/health > /dev/null 2>&1; then
        log_success "Grafana 运行正常"
    else
        log_error "Grafana 未运行"
    fi

    log_success "监控配置完成"
}

# 创建系统服务
create_system_service() {
    log_info "创建系统服务..."

    cat << EOF | sudo tee /etc/systemd/system/rowboat.service
[Unit]
Description=Rowboat Python Backend
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose -f $COMPOSE_FILE up -d
ExecStop=/usr/local/bin/docker-compose -f $COMPOSE_FILE down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable rowboat.service

    log_success "系统服务创建完成"
}

# 设置日志轮转
setup_log_rotation() {
    log_info "设置日志轮转..."

    cat << EOF | sudo tee /etc/logrotate.d/rowboat
/var/log/rowboat/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker-compose -f $COMPOSE_FILE kill -s USR1 rowboat-backend-prod
    endscript
}
EOF

    log_success "日志轮转配置完成"
}

# 创建备份脚本
create_backup_script() {
    log_info "创建备份脚本..."

    cat << 'EOF' > backup.sh
#!/bin/bash

# 备份目录
BACKUP_DIR="/opt/backups/rowboat"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose -f $COMPOSE_FILE exec -T rowboat-backend-prod sqlite3 /app/data/rowboat.db ".backup $BACKUP_DIR/database_$DATE.db"

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# 备份配置
cp .env $BACKUP_DIR/env_$DATE.backup

# 清理旧备份（保留30天）
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete

echo "备份完成: $DATE"
EOF

    chmod +x backup.sh

    # 添加到crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/backup.sh") | crontab -

    log_success "备份脚本创建完成"
}

# 显示部署信息
show_deployment_info() {
    log_info "部署信息："
    echo "=================================="
    echo "应用URL: https://$DOMAIN"
    echo "API文档: https://$DOMAIN/docs"
    echo "监控面板: http://$DOMAIN:3001"
    echo "Prometheus: http://$DOMAIN:9090"
    echo ""
    echo "Docker命令："
    echo "  查看日志: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  重启服务: docker-compose -f $COMPOSE_FILE restart"
    echo "  停止服务: docker-compose -f $COMPOSE_FILE down"
    echo ""
    echo "系统服务："
    echo "  启动: sudo systemctl start rowboat"
    echo "  停止: sudo systemctl stop rowboat"
    echo "  状态: sudo systemctl status rowboat"
    echo ""
    echo "备份："
    echo "  手动备份: ./backup.sh"
    echo "  自动备份: 每天凌晨2点"
    echo "=================================="
}

# 主函数
main() {
    log_info "开始生产环境部署..."

    # 检查系统要求
    check_system_requirements

    # 安装系统依赖
    install_system_dependencies

    # 配置防火墙
    setup_firewall

    # 配置SSL
    setup_ssl

    # 系统优化
    setup_system_optimization

    # 配置Docker
    setup_docker

    # 部署应用
    deploy_application

    # 配置监控
    setup_monitoring

    # 创建系统服务
    create_system_service

    # 设置日志轮转
    setup_log_rotation

    # 创建备份脚本
    create_backup_script

    # 显示部署信息
    show_deployment_info

    log_success "生产环境部署完成！"
}

# 运行主函数
main "$@""# 生产环境部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.production.yml"
DOMAIN="your-domain.com"
EMAIL="your-email@example.com"

# 函数定义
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统要求
check_system_requirements() {
    log_info "检查系统要求..."

    # 检查内存（建议至少2GB）
    total_memory=$(free -m | awk '/^Mem:/ {print $2}')
    if [[ $total_memory -lt 2048 ]]; then
        log_warning "系统内存小于2GB，可能影响性能"
    fi

    # 检查磁盘空间（建议至少10GB）
    available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_disk -lt 10 ]]; then
        log_warning "可用磁盘空间小于10GB"
    fi

    log_success "系统要求检查完成"
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."

    # 更新系统包
    sudo apt update && sudo apt upgrade -y

    # 安装必要软件
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        htop \
        fail2ban \
        ufw \
        certbot \
        python3-certbot-nginx

    log_success "系统依赖安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."

    # 启用UFW
    sudo ufw --force enable

    # 默认策略
    sudo ufw default deny incoming
    sudo ufw default allow outgoing

    # 允许SSH
    sudo ufw allow ssh

    # 允许HTTP/HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp

    # 允许应用端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 8000
    sudo ufw allow from 172.16.0.0/12 to any port 8000
    sudo ufw allow from 192.168.0.0/16 to any port 8000

    # 允许监控端口（仅内部网络）
    sudo ufw allow from 10.0.0.0/8 to any port 9090
    sudo ufw allow from 172.16.0.0/12 to any port 9090
    sudo ufw allow from 192.168.0.0/16 to any port 9090

    log_success "防火墙配置完成"
}

# 配置SSL证书
setup_ssl() {
    log_info "配置SSL证书..."

    # 创建SSL目录
    mkdir -p ssl

    # 使用Let's Encrypt获取证书
    if [[ -n "$DOMAIN" ]] && [[ "$DOMAIN" != "your-domain.com" ]]; then
        sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive

        # 复制证书到项目目录
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
        sudo chown $USER:$USER ssl/*.pem
        sudo chmod 600 ssl/*.pem

        log_success "SSL证书配置完成"
    else
        log_warning "未配置域名，使用自签名证书"

        # 生成自签名证书（仅用于测试）
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem \
            -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

        chmod 600 ssl/*.pem
    fi
}

# 配置系统优化
setup_system_optimization() {
    log_info "配置系统优化..."

    # 增加文件描述符限制
    echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
    echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

    # 优化内核参数
    cat << EOF | sudo tee /etc/sysctl.d/99-rowboat.conf
# 网络优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# 文件系统优化
fs.file-max = 2097152
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF

    sudo sysctl -p /etc/sysctl.d/99-rowboat.conf

    log_success "系统优化配置完成"
}

# 配置Docker
setup_docker() {
    log_info "配置Docker..."

    # 安装Docker（如果未安装）
    if ! command -v docker > /dev/null; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker $USER
    fi

    # 安装Docker Compose（如果未安装）
    if ! command -v docker-compose > /dev/null; then
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

    # 配置Docker守护进程
    cat << EOF | sudo tee /etc/docker/daemon.json
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ]
}
EOF

    sudo systemctl restart docker
    log_success "Docker配置完成"
}

# 部署应用
deploy_application() {
    log_info "部署应用..."

    # 构建镜像
    log_info "构建Docker镜像..."
    docker-compose -f $COMPOSE_FILE build --no-cache

    # 启动服务
    log_info "启动服务..."
    docker-compose -f $COMPOSE_FILE up -d

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30

    # 健康检查
    log_info "执行健康检查..."
    max_attempts=30
    attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "服务启动成功！"
            break
        fi

        log_info "等待服务启动... (尝试 $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    if [[ $attempt -gt $max_attempts ]]; then
        log_error "服务启动失败"
        docker-compose -f $COMPOSE_FILE logs
        exit 1
    fi
}

# 配置监控
setup_monitoring() {
    log_info "配置监控..."

    # 等待监控服务启动
    sleep 10

    # 验证Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus 运行正常"
    else
        log_error "Prometheus 未运行"
    fi

    # 验证Grafana
    if curl -f http://localhost:3001/api/health > /dev/null 2>&1; then
        log_success "Grafana 运行正常"
    else
        log_error "Grafana 未运行"
    fi

    log_success "监控配置完成"
}

# 创建系统服务
create_system_service() {
    log_info "创建系统服务..."

    cat << EOF | sudo tee /etc/systemd/system/rowboat.service
[Unit]
Description=Rowboat Python Backend
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose -f $COMPOSE_FILE up -d
ExecStop=/usr/local/bin/docker-compose -f $COMPOSE_FILE down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable rowboat.service

    log_success "系统服务创建完成"
}

# 设置日志轮转
setup_log_rotation() {
    log_info "设置日志轮转..."

    cat << EOF | sudo tee /etc/logrotate.d/rowboat
/var/log/rowboat/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker-compose -f $COMPOSE_FILE kill -s USR1 rowboat-backend-prod
    endscript
}
EOF

    log_success "日志轮转配置完成"
}

# 创建备份脚本
create_backup_script() {
    log_info "创建备份脚本..."

    cat << 'EOF' > backup.sh
#!/bin/bash

# 备份目录
BACKUP_DIR="/opt/backups/rowboat"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose -f $COMPOSE_FILE exec -T rowboat-backend-prod sqlite3 /app/data/rowboat.db ".backup $BACKUP_DIR/database_$DATE.db"

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# 备份配置
cp .env $BACKUP_DIR/env_$DATE.backup

# 清理旧备份（保留30天）
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete

echo "备份完成: $DATE"
EOF

    chmod +x backup.sh

    # 添加到crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/backup.sh") | crontab -

    log_success "备份脚本创建完成"
}

# 显示部署信息
show_deployment_info() {
    log_info "部署信息："
    echo "=================================="
    echo "应用URL: https://$DOMAIN"
    echo "API文档: https://$DOMAIN/docs"
    echo "监控面板: http://$DOMAIN:3001"
    echo "Prometheus: http://$DOMAIN:9090"
    echo ""
    echo "Docker命令："
    echo "  查看日志: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  重启服务: docker-compose -f $COMPOSE_FILE restart"
    echo "  停止服务: docker-compose -f $COMPOSE_FILE down"
    echo ""
    echo "系统服务："
    echo "  启动: sudo systemctl start rowboat"
    echo "  停止: sudo systemctl stop rowboat"
    echo "  状态: sudo systemctl status rowboat"
    echo ""
    echo "备份："
    echo "  手动备份: ./backup.sh"
    echo "  自动备份: 每天凌晨2点"
    echo "=================================="
}

# 主函数
main() {
    log_info "开始生产环境部署..."

    # 检查系统要求
    check_system_requirements

    # 安装系统依赖
    install_system_dependencies

    # 配置防火墙
    setup_firewall

    # 配置SSL
    setup_ssl

    # 系统优化
    setup_system_optimization

    # 配置Docker
    setup_docker

    # 部署应用
    deploy_application

    # 配置监控
    setup_monitoring

    # 创建系统服务
    create_system_service

    # 设置日志轮转
    setup_log_rotation

    # 创建备份脚本
    create_backup_script

    # 显示部署信息
    show_deployment_info

    log_success "生产环境部署完成！"
}

# 运行主函数
main "$@"