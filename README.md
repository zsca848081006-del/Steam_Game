# Steam Game Group Recommender

一个面向 Steam 多人开黑场景的 Web 工具：输入多名玩家的 SteamID64 或个人主页链接，读取可见库存、游玩时长和心愿单，建模这桌人的共同口味，然后推荐适合一起玩的多人游戏。

> 本项目由 AI 开发（Anthropic Claude，通过 Claude Code 完成设计、编码、测试与部署），人类作者负责产品方向、需求与验收。

项目默认不保存用户 key、用户库存或个人推荐结果。Steam API Key 和可选的 DeepSeek API Key 都只随单次请求经过服务端；SQLite 只缓存可共享的游戏属性和候选池数据。

## 主要能力

- 多人库存建模：基于可见库存、游玩时长（近两周加权）和 Steam 玩家投票标签（448 维简中标签，带票数）生成群体口味向量。
- 针对性打分：候选池内 IDF 降权烂大街标签 + 余弦相似度匹配，推荐度为绝对标定；国民级大热门温和降权，避免推荐全是人尽皆知的游戏。
- 心愿单权重：读取各玩家公开心愿单，多人共同心愿的游戏按陡曲线加成（1 人很小、2 人明显、全员接近上限）；心愿单中的单人游戏不参与推荐。
- 价格信息：推荐卡片展示当前价、折扣和"本站观测史低"（历次数据刷新观测到的最低价，随运行时间越来越准）。
- 主线推荐：静态种子、TGA 多人名单和动态 Steam 候选池（热销新品/高口碑多人/常青热销，12 小时自动刷新）。
- 尝鲜推荐：可选抓取 Steam 即将推出的多人/合作游戏，单独形成尝鲜档。
- 拥有过滤：默认只推荐全员都没有的游戏，也可放宽为"部分人有也可推荐"（补票开黑）。
- 输入友好：SteamID64、`steamcommunity.com/profiles/...`、`steamcommunity.com/id/自定义名` 链接都能识别，自动解析去重。
- 好友勾选：填自己的 ID 一键拉取公开好友列表（昵称+头像），点头像勾选队友即可组队，资料未公开的好友会标灰提示；好友列表私密时回退为手动粘贴链接。
- 兜底 Key：站长可配置公共 Steam Key，用户留空即用；key 错误会区分"站长 key 不可用"和"用户自己的 key 无效/限流"分别提示。
- AI 精排与中文理由：不填 DeepSeek key 时使用确定性算法；填写后只对已有候选做精排和理由生成，不允许 AI 编造 appid。
- 并发保护：全进程共享 Steam 出站并发上限、推荐请求背压、候选池刷新单飞锁、SQLite WAL、失败负缓存和超时控制。
- 访问统计：轻量匿名埋点（一年期随机 cookie 区分访客），令牌保护的 `/stats` 统计页，不采集个人数据。

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

页面输入：

- Steam ID 列表：至少 2 个，最多 16 个；支持 SteamID64 或 Steam 个人主页链接。
- Steam Web API Key：可选，留空使用站长配置的公共 key（若有）。
- DeepSeek API Key：可选；不填则跳过 AI 精排。

## 候选池怎么更新

每次推荐请求都会先加载候选池：

1. 先读 SQLite `steam_http_cache` 里的 `candidate_pool_v1`。
2. 默认 12 小时内直接使用缓存，可通过 `STEAMREC_CANDIDATE_POOL_TTL` 调整。
3. 缓存过期时，单飞锁保证同一时间只有一个请求刷新。
4. 刷新失败优先用陈旧缓存；没有陈旧缓存才退回静态种子。

动态候选来源：

- Steam 热销多人/合作：常青热销 + 近 18 个月热门新品（好评率过滤）。
- Steam 高口碑多人：评分排序，过滤免费游戏，要求评测量和好评率。
- Steam 即将推出：组成尝鲜档，过滤 Demo、Playtest、试玩、测试类条目。
- 玩家心愿单：多人共同心愿全部入池，单人心愿限量入池。
- 静态候选和 TGA 多人相关游戏作为补充与回退。

游戏属性缓存存在 `data/game_cache.sqlite`，包括 appdetails、投票标签、评测摘要、价格观测、候选池和失败负缓存。`data/` 默认不进 git。

## API

### `GET /health`

```json
{
  "status": "ok",
  "cache_version": 10,
  "store_language": "schinese",
  "ai_key_mode": "per_request"
}
```

### `POST /api/friends`

请求 `{"entry": "你的 SteamID64 或主页链接", "steam_api_key": "可选"}`，返回 `owner`（你的 steamid/昵称/头像）、`friends_visible`（好友列表是否公开）和 `friends`（steamid/昵称/头像/资料可见性）。

### `POST /api/recommend`

请求示例：

```json
{
  "steam_api_key": "可选，留空用站长公共 key",
  "deepseek_api_key": "可选；不填则跳过 AI 精排",
  "steam_ids": ["76561198813065802", "https://steamcommunity.com/profiles/7656119..."],
  "include_fresh": false,
  "exclude_owned": true,
  "required_players": 4,
  "boost_tags": ["合作", "生存"],
  "pass_tags": ["竞技"]
}
```

主要返回字段：

- `valid_players` / `excluded_players`：参与建模的有效玩家与被排除原因。
- `group_tags`：群体口味标签权重。
- `distribution`：口味分布（`focused` / `mixed` / `diverse` / `insufficient`）。
- `recommendations` / `fresh_recommendations`：主线与尝鲜推荐，含 `wishlist_count`、`price_final`、`price_discount`、`price_lowest` 等字段。
- `ai_used` / `ai_status`：AI 是否参与，以及成功或回退说明。
- 出错时返回 `detail`，key 类错误附 `error_code`（`fallback_key_failed` / `user_key_failed`）。

## 配置项

常用环境变量：

```bash
STEAMREC_HOST=127.0.0.1
STEAMREC_PORT=8673
STEAMREC_DATA_DIR=./data
STEAMREC_CACHE_TTL_SECONDS=259200
STEAMREC_CANDIDATE_POOL_TTL=43200
STEAMREC_TAG_DICTIONARY_TTL=604800
STEAMREC_STEAM_FETCH_CONCURRENCY=8
STEAMREC_MAX_CONCURRENT_RECS=4
STEAMREC_RECOMMENDATION_TIMEOUT=240
STEAMREC_STEAM_MISS_TTL=21600
STEAMREC_WISHLIST_BONUS=0.35
STEAMREC_WISHLIST_SOLO_LIMIT=15
STEAMREC_FALLBACK_STEAM_KEY=          # 站长公共 Steam Key，可留空
STEAMREC_STATS_TOKEN=                 # 访问统计页令牌，留空则 /stats 关闭
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=45
```

## 部署

仓库包含阿里云 systemd 和 nginx 反代配置：

- `deploy/steam-group-rec.service`：服务模板，应用只监听 `127.0.0.1:8673`。
- `deploy/nginx-kaluli.conf`：HTTPS 反代配置，公网入口走 nginx 443。
- `scripts/deploy_aliyun.sh`：同步代码、安装依赖、注入 env、重启服务。
- `deploy/ALIYUN.md`：常用运维命令。

当前线上入口记录在 `ai/PROJECT_MAP.md`，本地开发不依赖线上环境。

## 项目结构

```text
app.py                  标准库 HTTP 应用入口、推荐 API、访问统计页
steamrec/config.py      路径、端口、缓存、并发、超时与 key 配置
steamrec/models.py      请求、玩家、游戏、推荐结果 dataclass
steamrec/steam_api.py   Steam 库存、appdetails、心愿单、价格、ID 解析
steamrec/tags.py        玩家投票标签字典与批量标签抓取
steamrec/cache.py       SQLite 缓存（WAL）
steamrec/ingest.py      动态候选池抓取与缓存
steamrec/recommender.py 群体口味建模、IDF 余弦打分、心愿单加成
steamrec/deepseek.py    DeepSeek 精排与中文理由
steamrec/analytics.py   匿名访问埋点与汇总
steamrec/candidates.py  静态主线/尝鲜候选
steamrec/awards.py      TGA 多人相关候选
static/                 原生 HTML/CSS/JavaScript 前端
deploy/                 systemd 和 nginx 配置
scripts/                本地运行与部署脚本
ai/                     项目地图、交接和实现边界
```

## 隐私与仓库卫生

- 不提交 `配置.md`、`.env`、数据库、运行时缓存和虚拟环境。
- 用户的 Steam/DeepSeek key 不落库，只随单次请求经过服务端。
- 访问统计只记录匿名 cookie、IP、事件类型和耗时，不关联 Steam 身份。
- `data/` 下的 SQLite 只缓存共享游戏属性和匿名事件，不进 git。

## 已知边界

- "观测史低"是本站历次数据刷新看到的最低价，不是全网历史最低；接入 IsThereAnyDeal 等第三方需要额外 API key。
- 心愿单必须公开才能读取；私密心愿单静默跳过，不影响其他功能。
- 多人上限识别仍是启发式，部分 5 人以上合作游戏可能被"开黑人数"过滤误伤。
- 冷缓存首次请求较慢（候选池刷新 + 批量游戏属性拉取），之后请求走缓存。
