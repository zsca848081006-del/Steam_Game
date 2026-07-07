# Steam Game Group Recommender

一个面向 Steam 多人开黑场景的本地 Web 工具：输入多名玩家的 SteamID64 和 Steam Web API Key，读取可见库存与游戏时长，建模这桌人的共同口味，然后推荐适合一起玩的多人游戏。

项目默认不保存用户 key、用户库存或个人推荐结果。Steam API Key 和可选的 DeepSeek API Key 都只随单次请求经过服务端；SQLite 只缓存可共享的游戏属性和候选池数据。

## 主要能力

- 多人库存建模：基于多名玩家的可见库存、游玩时长和游戏类型生成群体口味标签。
- 主线推荐：从静态种子、TGA 多人相关名单和动态 Steam 候选池中筛选适合开黑的游戏。
- 尝鲜推荐：可选抓取 Steam 即将推出的多人/合作游戏，单独形成尝鲜档。
- 拥有过滤：默认只推荐全员都没有的游戏，也可以放宽为“部分人有也可推荐”。
- AI 精排与中文理由：不填 DeepSeek key 时使用确定性算法；填写后只对已有候选做精排和理由生成，不允许 AI 编造 appid。
- 并发保护：全进程共享 Steam 出站并发上限、推荐请求背压、候选池刷新单飞锁、SQLite WAL 和超时控制。

## 快速运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
STEAMREC_PORT=8673 .venv/bin/python app.py
```

打开：

```text
http://127.0.0.1:8673
```

页面需要填写：

- Steam Web API Key：用于读取玩家公开/可访问库存。
- SteamID64：至少 2 个，最多 16 个。
- DeepSeek API Key：可选；不填则跳过 AI 精排。

## 候选池怎么更新

每次推荐请求都会先调用候选池加载逻辑：

1. 先读 SQLite `steam_http_cache` 里的 `candidate_pool_v1`。
2. 默认 12 小时内直接使用缓存，可通过 `STEAMREC_CANDIDATE_POOL_TTL` 调整。
3. 缓存过期时，使用单飞锁保证同一时间只有一个请求刷新候选池。
4. 刷新失败时优先使用陈旧缓存；没有陈旧缓存才退回静态种子。

动态候选来源：

- Steam 热销多人/合作游戏：用于常青热销和近 18 个月热门新品。
- Steam 高口碑多人：评分排序，过滤免费游戏，要求一定评测量和好评率。
- Steam 即将推出：组成尝鲜档，过滤 Demo、Playtest、试玩、测试类条目。
- 静态候选和 TGA 多人相关游戏作为补充与回退。

游戏属性缓存存在 `data/game_cache.sqlite`，包括 appdetails、评测摘要、候选池和 appdetails 失败负缓存。`data/` 默认不进 git。

## API

### `GET /health`

返回：

```json
{
  "status": "ok",
  "cache_version": 8,
  "store_language": "schinese",
  "ai_key_mode": "per_request"
}
```

### `POST /api/recommend`

请求示例：

```json
{
  "steam_api_key": "浏览器输入，本次请求转发",
  "deepseek_api_key": "浏览器输入，可选；不填则跳过 AI 精排",
  "steam_ids": ["76561198813065802", "7656119..."],
  "include_fresh": false,
  "exclude_owned": true,
  "required_players": 4,
  "boost_tags": ["合作", "生存"],
  "pass_tags": ["竞技"]
}
```

主要返回字段：

- `valid_players`：参与建模的有效玩家。
- `excluded_players`：库存私密或数据不足的玩家。
- `group_tags`：群体口味标签权重。
- `distribution`：口味分布，可能是 `focused`、`mixed`、`diverse`、`insufficient`。
- `recommendations`：主线推荐。
- `fresh_recommendations`：尝鲜档推荐。
- `ai_used` / `ai_status`：AI 是否参与，以及成功或回退说明。

## 配置项

常用环境变量：

```bash
STEAMREC_HOST=127.0.0.1
STEAMREC_PORT=8673
STEAMREC_DATA_DIR=./data
STEAMREC_CACHE_TTL_SECONDS=259200
STEAMREC_CANDIDATE_POOL_TTL=43200
STEAMREC_STEAM_FETCH_CONCURRENCY=8
STEAMREC_MAX_CONCURRENT_RECS=4
STEAMREC_RECOMMENDATION_TIMEOUT=240
STEAMREC_STEAM_MISS_TTL=21600
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=45
```

## 部署

仓库包含阿里云 systemd 和 nginx 反代配置：

- `deploy/steam-group-rec.service`：服务模板，应用只监听 `127.0.0.1:8673`。
- `deploy/nginx-kaluli.conf`：HTTPS 反代配置，公网入口走 nginx 443。
- `scripts/deploy_aliyun.sh`：同步代码、安装依赖、重启 systemd 服务。
- `deploy/ALIYUN.md`：常用运维命令。

当前线上入口记录在 `ai/PROJECT_MAP.md`，本地开发不依赖线上环境。

## 项目结构

```text
app.py                  标准库 HTTP 应用入口和推荐 API
steamrec/config.py      路径、端口、缓存、并发和超时配置
steamrec/models.py      请求、玩家、游戏、推荐结果 dataclass
steamrec/steam_api.py   Steam 库存、appdetails、reviews 调用
steamrec/cache.py       SQLite 缓存
steamrec/ingest.py      动态候选池抓取与缓存
steamrec/recommender.py 群体口味建模、候选打分、拥有过滤
steamrec/deepseek.py    DeepSeek 精排与中文理由
steamrec/candidates.py  静态主线/尝鲜候选
steamrec/awards.py      TGA 多人相关候选
static/                 原生 HTML/CSS/JavaScript 前端
deploy/                 systemd 和 nginx 配置
scripts/                本地运行与部署脚本
ai/                     项目地图、交接和实现边界
```

## 隐私与仓库卫生

- 不提交 `配置.md`、`.env`、数据库、运行时缓存和虚拟环境。
- `配置.md` 可作为本地私有记录，但已被 `.gitignore` 排除。
- `data/game_cache.sqlite` 只用于共享游戏属性缓存，也不进 git。
- 推荐请求日志目前只进入 stdout/systemd journal；项目没有内置访问量或推荐次数统计表。

## 已知边界

- Steam store tags 目前主要用 genres 兜底，标签粒度还不够细。
- `fit_percent` 是当前候选集合内的相对拉伸，不是跨场景绝对分。
- 多人上限识别仍是启发式，部分 5 人以上合作游戏可能需要更精确的标签数据。
- 冷缓存首次请求会慢，尤其是候选池刷新和大量 appdetails 拉取同时发生时。
