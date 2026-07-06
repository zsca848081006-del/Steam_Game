# 交接

## 最近做了什么

- 创建了项目基础结构：标准库 HTTP 后端、静态前端、Steam API 客户端、SQLite 游戏属性缓存和确定性推荐器。
- 默认开发端口设为 `8673`，避开已占用的 `8670` / `8671` / `8672`。
- 验证了测试 Steam ID 可通过 Steam Web API 拉取库存，也验证了本机到阿里云 `root@8.131.69.97` 的免密 SSH 连通。
- 添加了阿里云 systemd 服务模板和一键部署脚本，并已部署到 `/opt/steam-group-rec`。
- 远端 `steam-group-rec` systemd 服务已启用并运行；服务器本机 `http://127.0.0.1:8673/health` 返回正常。
- 服务器已监听 `0.0.0.0:8673`，Ubuntu `ufw` inactive；本机访问 `http://8.131.69.97:8673/health` 超时，待在阿里云安全组放行 TCP `8673`。
- 初始化了 `ai/` 文档约定，本文件用于跨窗口交接，覆盖更新，不做流水账增量。
- 本轮修了中文展示和推荐解释：Steam Store 请求改为简中，推荐卡片展示 `推荐度 xx%`，不再暴露内部排序系数。
- 新增 `steamrec/awards.py`，把 TGA 近年多人相关获奖/提名的 Steam 可推荐子集结构化并入候选来源。
- 口味标签改为只使用 Steam genres；categories 只用于多人硬过滤，避免“家庭共享/辅助功能/玩家对战”等平台能力污染口味解释。
- 新增候选游戏中文显示名表 `steamrec/localization.py`，补齐 Steam 简中接口未翻译的常见标题。
- 修复部署脚本：每次同步后强制 `systemctl restart steam-group-rec`，避免服务继续跑旧代码。
- `/health` 现在返回 `cache_version` 和 `store_language`，便于确认线上进程是否已加载新版。
- 接入 DeepSeek：结构化算法先粗排，DeepSeek 只对 top 候选做精排并生成中文理由；失败时自动回退算法排序。
- 本地优先从被 git 忽略的 `配置.md` 读取 `deepseek_api_key`；远端通过 `/etc/steam-group-rec.env` 注入 `DEEPSEEK_API_KEY`。
- 改进 AI 理由输入：新增群体口味证据，把每个高权重标签背后的已玩游戏、累计时长和覆盖人数传给 DeepSeek，避免只复述标签和评分。
- UI 在 Steam Web API Key 输入框下方添加了官方申请链接 `https://steamcommunity.com/dev/apikey`。
- 加权/降权标签支持中文别名扩展：例如输入 `生存` 会匹配 `生存合作`、`生存多人`、`多人开放世界生存` 等候选来源/标签。
- UI 加了标签联想按钮，输入或聚焦加权/降权标签框时会显示常用中文标签建议，可点击追加。
- 恢复尝鲜档候选源：从 Steam coming soon 官方搜索中筛过多人/合作 appid 后写入 `FRESH_CANDIDATES`，勾选尝鲜档会生成独立推荐列表。
- 使用 Impeccable 初始化了产品/设计上下文：新增 `PRODUCT.md` 和 `DESIGN.md`，设计方向为深色霓虹游戏推荐指挥台。
- 使用 Stitch MCP 创建项目 `projects/9926863289475385038`（Steam Group Recommender Neon UI），上传 `DESIGN.md` 并创建 design system asset `354742b8febc46e0b2345644e8b6daa0`。
- 重构静态前端为深色霓虹 UI：输入区/共同口味区并排，游戏卡片突出 Steam header 图、排名、推荐度环、来源标签和 AI 理由。
- Steam 游戏属性缓存版本升到 `8`，优先使用 `header_image` 作为游戏卡片图。

## 遗留事项

- 当前候选池仍是结构化 MVP 种子表 + TGA 初版静态表；下一步需要实现“最近 N 个月多人新品 / 热销榜”的真实增量进料。
- Steam store tags 暂以 `appdetails` 里的 categories/genres 兜底；还需要勘查是否能稳定取得带票数的 store tags。
- AI 精排与理由生成已接入 DeepSeek，但仍必须只使用候选事实；若 DeepSeek 不可用会回退结构化理由。
- DeepSeek 理由目前依赖 `build_taste_evidence` 生成的库存证据；后续如果接入玩家昵称，可把 SteamID 替换成更友好的成员名。
- 尝鲜档目前仍是静态候选表，下一步应做成定时/按需抓 Steam coming soon 并缓存。
- `data/neon-ui-desktop-v2.png` 和 `data/neon-ui-mobile-v2.png` 是本轮本地验证截图，位于 ignored 的运行目录，不提交。
- 阿里云公网访问需放行 TCP `8673` 安全组规则；项目侧和服务器侧监听已经配置完成。
- 本机 Python 3.14 编译第三方依赖较慢，已改为无第三方运行时依赖的标准库实现。

## 操作约束

- 每次修改项目后及时提交 git。
- 每次修改项目后必须更新本交接文件；必要时同步更新 `ai/PROJECT_MAP.md`，让新窗口快速接手。
