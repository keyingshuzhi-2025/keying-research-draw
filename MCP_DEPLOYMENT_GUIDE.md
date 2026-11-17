# Research Draw MCP v0.1.5 部署教程

本文覆盖三种部署方式：本机进程（stdio）、本机 Docker，以及阿里云 ECS 上的 Alibaba Cloud Linux 3 服务器部署。MCP 会话、工作区和数据路径规则详见 [MCP_SERVER_README.md](MCP_SERVER_README.md)。

## 部署方式选择

| 方式 | 传输 | 适用场景 | MCP 地址 |
| --- | --- | --- | --- |
| 本机进程 | stdio | 柯影智航与 MCP 服务运行在同一台电脑 | 客户端启动本机命令 |
| 本机 Docker | Streamable HTTP | 本机容器测试或调试 | `http://127.0.0.1:8000/mcp` |
| 阿里云服务器 | Streamable HTTP + HTTPS 反向代理 | 多台客户端远程接入 | `https://mcp.example.com/mcp` |

v0.1.5 已发布的 `linux/amd64` 镜像为 `ghcr.io/keyingshuzhi-2025/keying-research-draw-mcp:v0.1.5`。当前仓库的发布工作流按仓库 owner 生成后续镜像地址；发布新版本时，以该版本实际发布的 GHCR 地址为准，并更新 `.env` 中的 `RESEARCH_DRAW_MCP_IMAGE`。

## 一、本机进程部署（stdio）

此方式不启动 HTTP 端口，也不需要 bearer token。MCP 客户端直接启动服务进程。

### 1. 安装依赖并准备工作区

先安装 `uv`；项目通过 `.python-version` 固定 Python `3.13.15`。在项目根目录执行：

```bash
uv sync --extra mcp
mkdir -p "$HOME/ResearchDrawWorkspaces/research"
```

### 2. 在终端启动

将下面命令中的路径替换为本机实际路径：

```bash
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research \
RESEARCH_DRAW_MCP_WORKSPACES="{\"research\":\"$HOME/ResearchDrawWorkspaces/research\"}" \
uv run --extra mcp research-draw-mcp
```

调用方传 `workspace: "research"`，或省略 `workspace` 使用默认工作区。共享数据可放在工作区根目录或其子目录；导入时传相对路径，例如 `data.csv` 或 `datasets/data.csv`。导入副本和绘图结果存入当前 stdio 服务进程对应的会话目录。

### 3. 配置柯影智航本机命令

在柯影智航的 MCP 服务配置中选择“本地命令（stdio）”：

- 启动命令：本机 `uv` 的绝对路径，例如 macOS Homebrew 安装的 `/opt/homebrew/bin/uv`
- 参数：`run`、`--project`、项目根目录绝对路径、`--extra`、`mcp`、`research-draw-mcp`
- 工作目录：项目根目录
- 普通环境变量：`RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research`、`RESEARCH_DRAW_MCP_WORKSPACES={"research":"/本机实际路径/ResearchDrawWorkspaces/research"}`
- 凭据引用：留空；stdio 模式不使用 HTTP bearer token

`RESEARCH_DRAW_MCP_WORKSPACES` 中的工作区目录必须是已存在的绝对路径。stdio 如需限制可访问范围，也可以另外配置 `RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 作为共同根目录。

## 二、本机 Docker 部署

本机 Docker 使用项目根目录的 `compose.mcp.yaml` 和 Docker Desktop。可以拉取已发布的 v0.1.5 镜像，也可以从当前源码构建开发镜像。配置固定为 `linux/amd64`；Apple Silicon 主机通过 Docker Desktop 的 amd64 支持运行。

### 1. 准备工作区和令牌

以下示例适用于 macOS。先在本机创建一个独立于项目目录的工作区和 token 文件：

```bash
mkdir -p "$HOME/ResearchDrawWorkspaces/research" "$HOME/.config/research-draw"
openssl rand -hex 32 > "$HOME/.config/research-draw/mcp-token"
chmod 600 "$HOME/.config/research-draw/mcp-token"
```

令牌文件保存原始 token，不要加 `Bearer ` 前缀。客户端凭据中的 Header 值才使用 `Bearer <token>`。

### 2. 配置 `.env`

从模板复制并编辑：

```bash
cp .env.mcp.example .env
```

本机 Docker 至少设置以下值。将 `/Users/<用户名>` 替换为实际 home 路径，并将 UID/GID 替换为 `id -u`、`id -g` 的结果：

```dotenv
RESEARCH_DRAW_MCP_IMAGE=ghcr.io/keyingshuzhi-2025/keying-research-draw-mcp:v0.1.5
RESEARCH_DRAW_MCP_TOKEN_FILE_HOST=/Users/<用户名>/.config/research-draw/mcp-token
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT=/Users/<用户名>/ResearchDrawWorkspaces
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/Users/<用户名>/ResearchDrawWorkspaces/research"}'
RESEARCH_DRAW_MCP_UID=501
RESEARCH_DRAW_MCP_GID=20
RESEARCH_DRAW_MCP_ALLOWED_HOSTS=localhost:8000,127.0.0.1:8000
RESEARCH_DRAW_MCP_ALLOWED_ORIGINS=
RESEARCH_DRAW_MCP_HOST_PORT=8000
```

工作区根目录必须是映射目录的父目录，且映射目录必须预先存在。Compose 将共同根目录挂载到容器 `/host-workspaces`；选定的逻辑工作区仍由 `RESEARCH_DRAW_MCP_WORKSPACES` 白名单控制。macOS 的 UID/GID 示例值仅供参考，以本机 `id -u` 和 `id -g` 输出为准。

### 3. 拉取并启动已发布镜像

在项目根目录执行：

```bash
docker compose -f compose.mcp.yaml pull
docker compose -f compose.mcp.yaml up -d --no-build
docker compose -f compose.mcp.yaml ps
docker compose -f compose.mcp.yaml logs --tail 100 research-draw-mcp
```

MCP 地址为 `http://127.0.0.1:8000/mcp`。本机 Docker Compose 默认只把端口绑定到回环地址，不应改成 `0.0.0.0` 后直接暴露到网络。

### 4. 从本地源码构建（可选）

如需测试尚未发布的代码，将 `.env` 中镜像名改成开发标签，再构建启动：

```dotenv
RESEARCH_DRAW_MCP_IMAGE=research-draw-mcp:dev-0.1.5-amd64
```

```bash
docker compose -f compose.mcp.yaml up -d --build
```

## 三、阿里云 ECS：Alibaba Cloud Linux 3

此示例使用已发布镜像、Docker Compose 和 Nginx TLS 反向代理。容器端口只绑定服务器本机 `127.0.0.1:8000`；客户端通过 HTTPS 域名访问 MCP。

### 1. 准备 ECS、域名和网络规则

1. 创建 `x86_64` 架构的 Alibaba Cloud Linux 3 ECS（当前 v0.1.5 镜像为 `linux/amd64`），并为域名（例如 `mcp.example.com`）配置指向 ECS 公网 IP 的 DNS A 记录。
2. 在 ECS 安全组中允许管理员来源访问 SSH `22/TCP`；允许 MCP 客户端访问 HTTPS `443/TCP`。如需 HTTP 跳转或证书签发，再开放 `80/TCP`。如果接入来源固定，安全组来源填写对应 CIDR。
3. 不要在安全组中开放容器端口 `8000`。Compose 将它绑定在 `127.0.0.1`，只供同机 Nginx 转发。

阿里云文档：[ECS 安全组规则](https://help.aliyun.com/en/ecs/user-guide/security-group-rules)、[Alibaba Cloud Linux 防火墙管理](https://help.aliyun.com/en/ecs/user-guide/enable-or-disable-the-system-firewall-in-a-linux-instance)。

### 2. 安装 Docker 和 Compose 插件

在 ECS 上执行阿里云针对 Alibaba Cloud Linux 3 的安装命令：

```bash
sudo dnf -y install wget
sudo wget -O /etc/yum.repos.d/docker-ce.repo http://mirrors.cloud.aliyuncs.com/docker-ce/linux/centos/docker-ce.repo
sudo sed -i 's|https://mirrors.aliyun.com|http://mirrors.cloud.aliyuncs.com|g' /etc/yum.repos.d/docker-ce.repo
sudo dnf -y install dnf-plugin-releasever-adapter --repo alinux3-plus
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

详细步骤见[阿里云 Docker 和 Docker Compose 安装文档](https://help.aliyun.com/en/ecs/user-guide/install-and-use-docker)。

### 3. 创建宿主机工作区和 Docker Secret

容器在 Linux 上以 UID/GID `10001:10001` 运行。创建可供该用户写入的工作区，并创建仅容器组可读的 bearer token 文件：

```bash
sudo install -d -o 10001 -g 10001 -m 2770 /srv/research-draw/workspaces/research
sudo install -d -o root -g 10001 -m 750 /etc/research-draw
sudo sh -c 'umask 027; openssl rand -hex 32 > /etc/research-draw/mcp-token'
sudo chown root:10001 /etc/research-draw/mcp-token
sudo chmod 440 /etc/research-draw/mcp-token
```

把要导入的源数据放在 `/srv/research-draw/workspaces/research/` 或其子目录中。绘图结果和导入副本会写入该工作区的 `.mcp-sessions/<session-key>/`，不会写入容器可写层或 Docker volume。

### 4. 放置 Compose 文件并配置服务器环境

将项目仓库克隆到服务器，复制环境模板：

```bash
sudo dnf -y install git
sudo mkdir -p /opt/research-draw-mcp
sudo chown "$USER":"$USER" /opt/research-draw-mcp
git clone --depth 1 https://github.com/keyingshuzhi/keying-research-draw.git /opt/research-draw-mcp
cd /opt/research-draw-mcp
cp .env.mcp.example .env
```

编辑 `/opt/research-draw-mcp/.env`，至少确认以下值与服务器一致：

```dotenv
RESEARCH_DRAW_MCP_IMAGE=ghcr.io/keyingshuzhi-2025/keying-research-draw-mcp:v0.1.5
RESEARCH_DRAW_MCP_TOKEN_FILE_HOST=/etc/research-draw/mcp-token
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT=/srv/research-draw/workspaces
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/srv/research-draw/workspaces/research"}'
RESEARCH_DRAW_MCP_UID=10001
RESEARCH_DRAW_MCP_GID=10001
RESEARCH_DRAW_MCP_ALLOWED_HOSTS=mcp.example.com,mcp.example.com:*
RESEARCH_DRAW_MCP_ALLOWED_ORIGINS=https://mcp.example.com
RESEARCH_DRAW_MCP_HOST_PORT=8000
RESEARCH_DRAW_MCP_MAX_IMPORT_MB=200
RESEARCH_DRAW_MCP_MAX_UPLOAD_MB=32
RESEARCH_DRAW_MCP_MAX_CHUNKED_UPLOAD_MB=200
RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB=48
```

将 `mcp.example.com` 替换为真实域名。`RESEARCH_DRAW_MCP_ALLOWED_HOSTS` 与 `RESEARCH_DRAW_MCP_ALLOWED_ORIGINS` 要允许客户端实际发送的 Host 和 Origin。不要把 token 值写入 `.env`，只填写 token 文件路径。

### 5. 拉取镜像并启动 MCP 容器

```bash
cd /opt/research-draw-mcp
sudo docker compose -f compose.mcp.yaml pull
sudo docker compose -f compose.mcp.yaml up -d --no-build
sudo docker compose -f compose.mcp.yaml ps
sudo docker compose -f compose.mcp.yaml logs --tail 100 research-draw-mcp
```

确认 Compose 仅在本机 `127.0.0.1:8000` 发布端口。需要令牌轮换或修改 `.env` 后，重新创建容器：

```bash
sudo docker compose -f compose.mcp.yaml up -d --no-build --force-recreate
```

### 6. 配置 Nginx HTTPS 反向代理

先安装 Nginx。下面使用阿里云 Linux 3 的 Nginx 官方稳定版软件源：

```bash
sudo tee /etc/yum.repos.d/nginx.repo <<'EOF'
[nginx-stable]
name=nginx stable repo
baseurl=https://nginx.org/packages/centos/8/$basearch/
gpgcheck=1
enabled=1
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true
EOF
sudo dnf -y install nginx
sudo mkdir -p /etc/nginx/ssl
```

部署有效的域名证书，将证书和私钥放在 `/etc/nginx/ssl/fullchain.pem` 和 `/etc/nginx/ssl/privkey.pem`。证书的申请与部署可参考[阿里云 LNMP 部署文档](https://help.aliyun.com/en/ecs/user-guide/deploy-the-lnmp-environment)。

```nginx
server {
    listen 80;
    server_name mcp.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name mcp.example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    client_max_body_size 48m;

    location = /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

保存到 `/etc/nginx/conf.d/research-draw-mcp.conf`，再检查并启动 Nginx：

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

如果服务器启用了 `firewalld`，允许 SSH、HTTP 和 HTTPS 服务后再 reload；不要添加 `8000/tcp`：

```bash
sudo firewall-cmd --state
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 7. 在 MCP 客户端连接

- Streamable HTTP 地址：`https://mcp.example.com/mcp`
- HTTP Header：`Authorization: Bearer <服务器 /etc/research-draw/mcp-token 中的 token>`
- 连接后调用 `get_version`，预期返回 `v0.1.5`；调用 `list_workspaces` 确认默认工作区 `research`。

阿里云 ECS 安全组和系统防火墙只需要允许客户端到 HTTPS 反向代理的流量；不要把后端 HTTP 端口 `8000` 暴露到公网。

## 运维常用命令

在 Compose 文件所在目录执行：

```bash
# 查看运行状态
sudo docker compose -f compose.mcp.yaml ps

# 查看日志
sudo docker compose -f compose.mcp.yaml logs --tail 100 research-draw-mcp

# 拉取新镜像并更新容器
sudo docker compose -f compose.mcp.yaml pull
sudo docker compose -f compose.mcp.yaml up -d --no-build

# 停止容器；宿主机工作区数据会保留
sudo docker compose -f compose.mcp.yaml down
```

若是在本机部署且 Docker CLI 不需要 `sudo`，去掉命令前的 `sudo`。
