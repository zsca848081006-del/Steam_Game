# 交接

## 最近做了什么(本轮:DeepSeek key 改为网页填写)

- 用户担心公网访问者消耗自己的 DeepSeek 额度:DeepSeek API Key 改为前端可选输入(`#deepseekKey`,sessionStorage 暂存),随单次请求转发,服务端不再持有;不填则跳过 AI 精排、回退算法排序,`ai_status` 会说明。
- `RecommendRequest` 新增 `deepseek_api_key` 字段;`refine_recommendations` 改为接收 key 参数;`config.py` 删除从 `配置.md`/环境变量读 DeepSeek key 的逻辑;`/health` 的 `ai_configured` 改为 `ai_key_mode: per_request`。
- 部署链路清理:`deploy_aliyun.sh` 不再注入 `/etc/steam-group-rec.env` 且部署时删除该文件,service 模板去掉 `EnvironmentFile` 行。
- 本地验证:不带 key 请求 `ai_used: false` 正常回退;带 key 请求 AI 精排正常。注意 Steam key 本来就是网页填写的,本轮只动了 DeepSeek key。

## 上一轮:候选池自动进料

- 背景:用户反馈推荐"全是大路货",第一轮迭代方向定为候选池自动进料(原来只有 57 个静态种子)。
- 新增 `steamrec/ingest.py`:从 Steam 搜索 `search/results/?infinite=1` 抓多人/合作游戏,解析 HTML 里的 appid、发售日期和评测 tooltip。注意:多个 `category3` 是"与"关系,必须按 category3=9(合作)和 1(多人)分别查询再合并;`filter=popularnew` 实际返回的是老热门榜,不能当"新品"用,新品要靠热销榜 + 发售日期过滤自己算。
- 进料三路主候选:近 18 个月发售且好评率 ≥70% 的热销新品(`Steam 近一年热门新品`)、评分排序且评测数 ≥400/好评 ≥85% 的中体量游戏(`Steam 高口碑多人`,hidef2p=1)、少量常青热销(`Steam 热销多人`);尝鲜档改为动态抓 comingsoon(过滤 Demo/Playtest),静态 `FRESH_CANDIDATES` 只作回退。
- 动态池缓存在 SQLite `steam_http_cache` 表(cache.py 新增 `get_http`/`put_http`),TTL 12 小时(`STEAMREC_CANDIDATE_POOL_TTL`);刷新失败回退陈旧缓存,再失败只用静态种子,不影响可用性。
- 打分加"大路货降权":评测数 ≥20 万 ×0.7、≥8 万 ×0.85,新品/即将推出候选 +0.05。
- `candidate_source_map` 改为返回 `(source_map, fresh_ids)` 并接受动态池参数;`app.py` 请求时先 `load_candidate_pools` 再打分。
- 本地端到端验证:动态主池 78 个 + 静态种子,前排从 CS2/饥荒换成梦之形、失落城堡2、Rabbit and Steel 等中体量新品;冷缓存首次请求约 80 秒(数百个 appdetails,未见 429),热缓存约 23 秒(主要是 DeepSeek 耗时,与改动前持平)。

## 遗留事项

- 下一个质量瓶颈是口味信号:store tags 仍以 genres 兜底(十几维、区分度低,几乎所有游戏都命中"动作/冒险"),下一步接 `IStoreService/GetTagList`(支持简中)+ 带票数 tags,把口味向量换成细粒度标签,并改余弦相似度 + 烂大街标签 IDF 降权 + `playtime_2weeks` 近期加成。
- `fit_percent` 是组内 min-max 拉伸(55–98),整体不匹配时第一名也显示 98%,需要改绝对标定。
- `_max_players_hint` 把所有 co-op 一律当 4 人上限,用户要求 5 人以上时会误杀 8 人合作游戏。
- 动态池冷缓存首次请求约 80 秒;若线上触发 Steam appdetails 限流(429),考虑进料后后台预热缓存。
- 结果多样性:top 榜容易被同一品类刷屏,后续可加 MMR 式去重;再往后可做"不感兴趣/已玩腻"反馈闭环。
- DeepSeek 理由依赖 `build_taste_evidence` 的库存证据;后续若接入玩家昵称,可把 SteamID 换成更友好的成员名。
- 阿里云公网访问需在安全组放行 TCP `8673`;项目侧和服务器侧监听已配置完成。

## 操作约束

- 每次修改项目后及时提交 git。
- 每次修改项目后必须更新本交接文件;必要时同步更新 `ai/PROJECT_MAP.md`,让新窗口快速接手。
