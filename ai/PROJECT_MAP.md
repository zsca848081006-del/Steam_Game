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

- 阿里云远端目录：`/opt/steam-group-rec`。
- systemd 服务：`steam-group-rec`，当前配置监听 `0.0.0.0:8673`。
- 服务器内 `http://127.0.0.1:8673/health` 已验证正常。
- 公网访问需要阿里云安全组放行 TCP `8673`。

## 项目结构

- `app.py`：标准库 HTTP 应用入口，提供页面、健康检查和推荐 API。
- `steamrec/config.py`：路径、端口、Steam API 基础地址和缓存 TTL。
- `steamrec/models.py`：请求、玩家、游戏属性、推荐结果等 dataclass 模型。
- `steamrec/steam_api.py`：Steam 库存、appdetails、reviews 调用；补 `include_played_free_games=1`。
- `steamrec/cache.py`：SQLite 游戏属性缓存。
- `steamrec/candidates.py`：MVP 候选池和尝鲜档候选池。
- `steamrec/awards.py`：TGA 多人相关获奖/提名的 Steam 可推荐子集。
- `steamrec/localization.py`：候选游戏中文显示名兜底表。
- `steamrec/deepseek.py`：DeepSeek chat completions 调用、JSON 解析、appid 白名单校验和失败回退。
- `steamrec/recommender.py`：群体口味建模、候选打分、拥有过滤和理由拼装。
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
{"status":"ok","cache_version":7,"store_language":"schinese","ai_configured":true}
```

### `POST /api/recommend`

请求：

```json
{
  "steam_api_key": "浏览器输入，本次请求转发",
  "steam_ids": ["76561198813065802", "..."],
  "include_fresh": false,
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
- 候选枚举还不是自动抓 Steam 新品/热销榜。
- Steam store tags 暂用 genres 代替，标签粒度不足；categories 仅用于多人硬过滤。
- TGA 数据是初版人工静态表，覆盖 Steam 可推荐的近年多人相关获奖/提名子集，还不是完整奖项数据库。
- Steam API key 不落库；但因为 Steam 请求必须代理，key 会随单次 HTTP 请求经过服务器进程。
- DeepSeek key 不进 git；本地从 `配置.md` 读取，远端从 `/etc/steam-group-rec.env` 读取。

## 固定约束

- 每次修改项目后及时提交 git。
- 每次修改项目后必须更新 `ai/HANDOFF.md`；必要时更新本项目地图。
- 不提交 `配置.md`、`.env`、数据库和运行时缓存。
