# 交接

## 最近做了什么(本轮:口味向量升级,只在本地,未部署)

- **注意:本轮改动只提交了 git,按用户要求暂未部署到阿里云**,线上仍是旧版口味逻辑;下次部署照常跑 `scripts/deploy_aliyun.sh` 即可。
- 口味信号从十几维 genre 换成玩家投票标签:新增 `steamrec/tags.py`,`IStoreService/GetTagList`(简中标签字典,448 个,免 key,缓存 7 天)+ `IStoreBrowseService/GetItems`(每游戏 top20 标签带票数,免 key,支持批量,每批 40 个);`GameRecord` 新增 `tag_weights`(str(tagid)→票数),缓存版本升到 9(旧缓存自动重建,冷启动约 45 秒)。
- `recommender.py` 重写打分:向量键为 str(tagid)(无票数时回退 genre 名);游戏标签按票数占比分摊;口味信号 `sqrt(playtime_forever + 25 * playtime_2weeks)` 给近两周游玩强加成;候选池内算 IDF(`log(N/df)`)降权烂大街标签,出现在全部候选里的标签(如"多人")权重归零;匹配改余弦相似度,消除"标签多天然得分高"偏差。
- `fit_percent` 改绝对标定:`55 + 43 * min(cosine/0.55, 1)`(`FIT_COSINE_CAP`),整体不匹配时不再虚标 98%。
- 大路货降权加一档:评测数 ≥50 万 ×0.55(此前 138 万评测的腐蚀仍能凭高相似度冲第一)。
- 展示层:`apply_display_tags` 把 tagid 解析成简中名写回 `record.tags`(UI/DeepSeek/口味证据共用),`top_group_tags` 滤噪声并归一;boost/pass 标签现在直接对真实标签名匹配。
- 本地验证:群体口味从"动作/冒险/独立"变成"开放世界生存制作/基地建设/自动化"级别;推荐咬住测试号的生存建造偏好;DeepSeek 理由开始引用具体游戏+细粒度标签("戴森球计划数百小时→热爱自动化→Factorio");热缓存约 21 秒(主要为 DeepSeek 耗时);Steam key 未触发限额。

## 上一轮:访问统计

- 新增 `steamrec/analytics.py`:埋点存独立 `data/analytics.sqlite`(WAL),events 表带时间戳;`page_view`(GET /)和 `recommend`(POST /api/recommend,meta 含 status/duration_ms/players,含 busy/bad_request/timeout 等失败态)两类事件;埋点异常静默吞掉,绝不影响正常请求。
- 访客区分:无登录体系,用服务端一年期随机 cookie(`srvid`,HttpOnly,SameSite=Lax)近似区分浏览器;清 cookie/换设备会算新访客,精度"大概差不多"是预期内的。
- 统计页 `GET /stats?token=<令牌>`:总览卡片(PV/独立访客/推荐执行/成功)+ 最近 30 天按日表(UTC+8,`STEAMREC_STATS_TZ`)+ 最近 20 条事件;令牌为空或不匹配一律 404(hmac.compare_digest),页面 noindex、no-store,UI 任何地方不链接它。
- 令牌链路:进不了 git;本地在 `配置.md` 的 `stats_token：...`(config.py 会读),远端由部署脚本从 配置.md 提取写入 `/etc/steam-group-rec.env`(600),service 模板恢复了 `EnvironmentFile=-`(现在只承载这个低敏感令牌,AI key 仍然不落服务器)。
- 本地验证:cookie 首发/复用正确;PV、独立访客、成功/失败推荐计数正确;无/错令牌 404。

## 上一轮:README 更新

- 重写 GitHub 首页 `README.md`:补全项目定位、快速运行、候选池更新机制、API 示例、配置项、部署入口、项目结构、隐私/仓库卫生和已知边界。
- 上传前已做敏感信息检查:`配置.md` 含本地 DeepSeek key 形态内容但被 `.gitignore` 排除;`data/game_cache.sqlite` 也不被 git 跟踪。
- 远端仓库为 `git@github.com:zsca848081006-del/Steam_Game.git`,本地 `main` 跟踪 `origin/main`;推送使用仓库专用 deploy key `~/.ssh/steam_game_deploy`(`core.sshCommand` 已设置)。

## 最近做了什么(本轮:并发健壮性)

- 保持标准库、不引第三方框架(本机 Python 3.14 编第三方包慢是既有约束,且瓶颈都在逻辑层)。改造为:单一共享 asyncio 事件循环(`app.py` 模块级 `_LOOP`,专用线程跑 `run_forever`,handler 用 `run_coroutine_threadsafe` 提交),替代原来每请求 `asyncio.run`。
- 全进程共享 Steam 出站并发信号量(`steam_api._steam_semaphore`,默认 8,`STEAMREC_STEAM_FETCH_CONCURRENCY`),不再随请求数放大;共享循环的默认执行器固定 32 线程(2 核机默认只有 6,撑不起并发抓取+DeepSeek)。
- 背压:同时计算的推荐请求上限默认 4(`STEAMREC_MAX_CONCURRENT_RECS`),超出立刻 503 中文提示;单请求超时 240 秒(`STEAMREC_RECOMMENDATION_TIMEOUT`,小于 nginx 的 300 秒)返回 504。
- 候选池刷新加单飞锁(`ingest._refresh_lock` + 双检缓存),过期时只有一个请求真正去刷,避免惊群。
- SQLite 开 WAL + busy_timeout 10s,并发读写不再互卡。
- `_get_json` 对 429/5xx 重试(最多 3 次,退避 2/4 秒);配套 appdetails 负缓存(失败/非游戏 appid 记 6 小时,`STEAMREC_STEAM_MISS_TTL`),坏 appid 不会每个请求重试一遍。
- 验证:热缓存单请求约 3.2 秒(无 AI);限 2 并发打 5 个 → 恰好 2×200 + 3×503(503 毫秒级返回),期间 /health 正常;连续请求槽位释放正常。
- 测试踩坑:zsh 脚本里 `wait` 不带参数会连后台 server 一起等导致假"卡死";负缓存生效前,冷池刷新 + 429 重试叠加会让首次请求慢到分钟级。

## 上一轮:「只推全员都没有的」勾选项

- 前端新增勾选项「只推全员都没有的」(`#excludeOwned`,默认勾选),请求字段 `exclude_owned`(后端默认 true)。
- 勾选时:候选只要有任何一名玩家拥有就被排除(主线档和尝鲜档都生效);不勾选时:恢复原行为,只排除全员都拥有的,部分人拥有的仍可推荐(补票开黑场景)。
- 拥有判定基于玩家完整库存(`owned_by_app` 用全部 games 构建),不受口味建模只取 top 30 的限制。
- 验证:合成数据单测两种开关行为正确;注意用同一 SteamID 传两次冒烟测试看不出该开关差别(重复库存会命中"全员拥有"规则),需要不同 ID 才能观察。

## 上一轮:域名 + HTTPS

- 站点绑定备案域名 `kaluli.xin` / `www.kaluli.xin`(解析已指向 8.131.69.97),nginx 443 端口 TLS 终止后反代到 `127.0.0.1:8673`,HTTP 自动 301 到 HTTPS;配置在 `deploy/nginx-kaluli.conf`,部署脚本会安装并 reload nginx。
- 复用服务器上已有的 Let's Encrypt 证书(certbot,authenticator/installer 均为 nginx 插件,续期依赖新站点里的 server_name)。
- 应用改为只监听 `127.0.0.1`(service 模板 `STEAMREC_HOST=127.0.0.1`),公网流量必须走 HTTPS 反代,`http://IP:8673` 直连已不可达,key 不再明文暴露。
- nginx `proxy_read_timeout 300s`,兼容冷缓存首次推荐的长耗时。
- 服务器上还有旧项目"geo"(nginx `sites-enabled/geo`,server_name 为 IP,反代 :8000),未动它;域名 Host 命中新站点,旧项目仍可用 IP 访问。
- 公网已验证:`https://www.kaluli.xin/health` 200、证书有效、HTTP 301 跳转正常、静态资源正常。

## 上一轮:DeepSeek key 改为网页填写

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

- **口味升级已完成但未上线**:部署前建议先在服务器跑一次冷启动验证(缓存版本 9 全量重建 + GetItems 批量接口在阿里云网络下的表现)。
- `FIT_COSINE_CAP=0.55` 和 IDF/降权系数是按单个测试号标定的,多人真实小队数据进来后可能需要微调。
- `_max_players_hint` 把所有 co-op 一律当 4 人上限,用户要求 5 人以上时会误杀 8 人合作游戏;GetItems 其实能返回更多字段,后续可评估从中取真实人数上限。
- 口味建模仍只取每人 top30 游戏(`owned_appids`);标签维度细了之后,适当放宽到 top50 可能让口味更完整,注意请求量权衡。
- 动态池冷缓存首次请求约 80 秒;若线上触发 Steam appdetails 限流(429),考虑进料后后台预热缓存。
- 结果多样性:top 榜容易被同一品类刷屏,后续可加 MMR 式去重;再往后可做"不感兴趣/已玩腻"反馈闭环。
- DeepSeek 理由依赖 `build_taste_evidence` 的库存证据;后续若接入玩家昵称,可把 SteamID 换成更友好的成员名。
- 阿里云公网访问需在安全组放行 TCP `8673`;项目侧和服务器侧监听已配置完成。

## 操作约束

- 每次修改项目后及时提交 git。
- 每次修改项目后必须更新本交接文件;必要时同步更新 `ai/PROJECT_MAP.md`,让新窗口快速接手。
