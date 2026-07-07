# 项目地图

## 技术栈

- Python 3.11+。
- Python 标准库 `http.server` 提供 Web 页面和 JSON API。
- Python 标准库 `urllib` 调用 Steam Web API 与 Steam Store API。
- SQLite 只缓存共享的游戏属性包，不保存用户 key、用户库存或个人数据。
- 原生 HTML/CSS/JavaScript 构建当前 MVP 页面。
- DeepSeek 已接入推荐主流程：确定性算法先粗排候选，AI 只精排 top 候选并基于真实事实写中文理由。

## 运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
STEAMREC_PORT=8673 .venv/bin/python app.py
```

打开 `http://127.0.0.1:8673`。

## 部署状态

- 公网入口：`https://www.kaluli.xin`（备案域名，Let's Encrypt 证书，certbot nginx 插件自动续期；HTTP 自动 301 到 HTTPS）。
- 阿里云远端目录：`/opt/steam-group-rec`；systemd 服务 `steam-group-rec` 只监听 `127.0.0.1:8673`，由 nginx 443 反代（`deploy/nginx-kaluli.conf`）。
- 服务器上另有旧项目 "geo"（nginx 反代 :8000，server_name 为 IP），与本项目并存。

## 项目结构

- `app.py`：标准库 HTTP 应用入口，提供页面、健康检查和推荐 API。
- `steamrec/config.py`：路径、端口、Steam API 基础地址和缓存 TTL。
- `steamrec/models.py`：请求、玩家、游戏属性、推荐结果等 dataclass 模型。
- `steamrec/steam_api.py`：Steam 库存、appdetails、reviews 调用；补 `include_played_free_games=1`。
- `steamrec/cache.py`：SQLite 游戏属性缓存。
- `steamrec/candidates.py`：MVP 静态种子候选池和尝鲜档回退候选池。
- `steamrec/ingest.py`：从 Steam 搜索自动进料候选池（近一年热门新品/高口碑多人/热销多人/即将推出），结果缓存 12 小时。
- `steamrec/tags.py`：玩家投票标签。`GetTagList` 简中标签字典（缓存 7 天）+ `GetItems` 批量拉每游戏 top20 标签票数，均免 key。
- `steamrec/awards.py`：TGA 多人相关获奖/提名的 Steam 可推荐子集。
- `steamrec/localization.py`：候选游戏中文显示名兜底表。
- `steamrec/tag_aliases.py`：中文标签联想词和用户输入别名扩展。
- `steamrec/deepseek.py`：DeepSeek chat completions 调用、JSON 解析、appid 白名单校验和失败回退。
- `steamrec/recommender.py`：群体口味建模、口味证据生成、候选打分、拥有过滤和理由拼装。
- `PRODUCT.md`：Impeccable 产品战略上下文，register 为 `product`。
- `DESIGN.md`：Impeccable/Stitch 设计系统文档，当前主题为深色霓虹游戏推荐指挥台。
- `static/`：单页前端。
- `scripts/run_dev.sh`：本地开发启动脚本。
- `scripts/deploy_aliyun.sh`：同步到阿里云并安装 systemd 服务。
- `deploy/steam-group-rec.service`：阿里云 systemd 服务模板。
- `deploy/ALIYUN.md`：部署与运维命令。
- `ai/HANDOFF.md`：跨窗口交接，覆盖更新。
- `ai/PROJECT_MAP.md`：技术栈、结构、接口、约束。

## API

### `GET /health`

返回：

```json
{"status":"ok","cache_version":8,"store_language":"schinese","ai_key_mode":"per_request"}
```

### `GET /stats?token=<令牌>`

访问统计页(PV/独立访客/推荐执行,按日汇总)。令牌本地在 `配置.md` `stats_token：`,远端在 `/etc/steam-group-rec.env`;为空或不匹配返回 404。访客用一年期 `srvid` cookie 近似区分。

### `POST /api/recommend`

请求：

```json
{
  "steam_api_key": "浏览器输入，本次请求转发",
  "deepseek_api_key": "浏览器输入，可选；不填则跳过 AI 精排",
  "steam_ids": ["76561198813065802", "..."],
  "include_fresh": false,
  "exclude_owned": true,
  "required_players": 4,
  "boost_tags": ["Co-op"],
  "pass_tags": ["Survival"]
}
```

返回：

- `valid_players`：参与建模的有效玩家。
- `excluded_players`：库存私密或数据不足的玩家。
- `group_tags`：归一化后的群体标签权重。
- `distribution`：`focused` / `mixed` / `diverse` / `insufficient`。
- `recommendations`：主线档推荐。
- `fresh_recommendations`：尝鲜档推荐。
- `ai_used`：本次是否成功使用 DeepSeek。
- `ai_status`：AI 成功或回退状态。

推荐项里的 `score` 是内部排序系数，前端不展示；用户可见的是 `fit_percent` 推荐度。

## 当前实现边界

- DeepSeek 只精排已有候选并写理由，不允许新增候选 appid；接口失败时自动回退确定性排序和结构化理由。
- DeepSeek 输入包含 `taste_evidence`：高权重口味标签背后的已玩游戏、累计时长、覆盖人数，以及候选自己的标签、来源、口碑和拥有情况。
- 加权/降权标签会经过别名扩展，并同时匹配 Steam genres、候选来源标记和多人 category。
- 候选池由 `steamrec/ingest.py` 自动进料（Steam 搜索热销/评分/即将推出榜），叠加静态种子和 TGA 表；打分含大路货降权（评测数 ≥20 万 ×0.7、≥8 万 ×0.85）和新品加成。
- 尝鲜档动态抓 Steam comingsoon，失败时回退 `FRESH_CANDIDATES` 静态表，候选标记为 `尝鲜档` / `Steam 即将推出`。
- 口味向量基于玩家投票标签（tagid+票数，448 维简中字典），打分为候选池内 IDF 降权后的余弦相似度，近两周时长 25 倍加成；无票数数据时回退 genre。categories 仅用于多人硬过滤。
- TGA 数据是初版人工静态表，覆盖 Steam 可推荐的近年多人相关获奖/提名子集，还不是完整奖项数据库。
- Steam API key 和 DeepSeek key 都由用户在网页填写、不落库；因为请求必须代理，两个 key 会随单次 HTTP 请求经过服务器进程。DeepSeek key 不填则跳过 AI 精排、回退算法排序。
- Stitch 项目：`projects/9926863289475385038`；design system asset：`354742b8febc46e0b2345644e8b6daa0`。

## 固定约束

- 每次修改项目后及时提交 git。
- 每次修改项目后必须更新 `ai/HANDOFF.md`；必要时更新本项目地图。
- 不提交 `配置.md`、`.env`、数据库和运行时缓存。
