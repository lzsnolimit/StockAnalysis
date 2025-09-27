# Reddit 热点股票自动分析与数据抓取规范（Spec）

## 目标与范围
- 每次启动流程时：
  - 抓取 r/wallstreetbets 的热门帖子（hot/new/top/rising，以及按评论排序的搜索）。
  - 从帖子内容中识别股票代码（Ticker），计算热度并选出 Top 10。
  - 调用股票数据接口，拉取所选 Top 10 的完整数据集（行情、历史、基本面、期权、新闻/情绪），并落盘为结构化文件。

## 总体架构
- 阶段 1：Reddit 数据采集（已有脚本 `scripts/fetch_wsb_reddit.py`）。
  - 使用 Reddit 公共 JSON 接口（无需鉴权），输出原始与归一化数据。
- 阶段 2：Ticker 提取与热度计算。
  - 从标题、自述（selftext）、URL、flair 中用规则与词典识别股票代码。
  - 计算热度分数并排序，选出 Top 10。
- 阶段 3：股票数据抓取。
  - 按配置选择 Provider（默认 `yfinance`，可切换到 Alpha Vantage/Finnhub/FMP 等）。
  - 拉取行情、历史 K 线、基本面、期权链、新闻与情绪（视 Provider 能力）。
- 阶段 4：落盘与汇总。
  - 统一 JSON/CSV 输出；生成元数据与报表。

## 触发与运行
- 启动方式：
  - CLI 命令：`python scripts/run_pipeline.py`（建议新增，见“实现建议”）。
  - 或在现有流程中调用：先运行 `scripts/fetch_wsb_reddit.py`，再执行 Ticker 提取与股票抓取模块。
- 频率：
  - 手动/定时（可用 cron 或调度器）。POC 推荐每小时运行一次。
  - Cron 示例：`0 * * * * cd /path/to/StockAnalysis && /usr/bin/env python3 scripts/run_pipeline.py`
  - 支持增量或全量抓取（通过时间窗口与分页控制）。

## 配置项（Config）
- 通用：
  - `REDDIT_MAX_PAGES`（默认 10）
  - `REDDIT_TOP_TIME`（默认 `all`；用于 top 列表）
  - `REDDIT_SLEEP_SECONDS`（默认 0.8）
  - `REDDIT_SUBREDDIT`（默认 `wallstreetbets`）
  - `OUTPUT_DIR`（默认 `outputs`）
  - `TOP_N_TICKERS`（默认 10）
  - `SCAN_INTERVAL_SECONDS`（默认 3600；每小时一次）
- 股票 Provider：
  - `STOCK_API_PROVIDER`：`yfinance`（默认）| `alphavantage` | `finnhub` | `fmp` | `polygon` | `iex` | `twelvedata` 等。
  - Provider 鉴权：
    - `ALPHAVANTAGE_API_KEY`
    - `FINNHUB_TOKEN`
    - `FMP_API_KEY`
    - `IEX_TOKEN`
    - `POLYGON_API_KEY`
    - `TWELVEDATA_API_KEY`
  - `STOCK_HISTORY_GRANULARITY`：`1d` | `1h` | `15m` | `1m`（视 Provider 能力）
  - `STOCK_HISTORY_LOOKBACK`：如 `5y`、`1y`、`90d`、`30d`
  - `ENABLE_OPTIONS_CHAIN`：true/false
  - `ENABLE_NEWS_SENTIMENT`：true/false
- 新闻 Provider（简化优先）：
  - `NEWS_PROVIDER`：`yfinance`（默认，无需鉴权）| `alphavantage` | `finnhub` | `fmp`
  - 对应鉴权：沿用上述 API KEY/TOKEN（yfinance 无需）
- 邮件通知：
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`
  - `SUBSCRIBERS_FILE`：订阅者邮件列表 CSV 路径（例如 `config/subscribers.csv`）
 - 指数监控：
   - `INDEX_WATCHLIST`（默认见上），可在环境变量或配置文件覆盖。

## 数据识别与热度算法
- 识别规则：
  - 正则匹配：`\b[A-Z]{1,5}\b`、带 `$` 前缀（如 `$AAPL`）、或带交易所后缀（如 `BRK.B`）。
  - 排除列表（Stoplist）：常见英文短词（`I`, `IT`, `ALL`, `USA` 等）与非股票缩写。
  - 白名单/词典：已知股票列表（可本地维护或调用 API 验证合法性）。
  - 链接/URL 解析：提取 `.../stocks/<TICKER>`、`.../symbol/<TICKER>` 等路径。
- 热度分数（示例权重）：
  - `mentions_weight = 1.0`（出现次数）
  - `score_weight = 0.002`（Reddit 帖子 `score`）
  - `comments_weight = 0.001`（`num_comments`）
  - 时间衰减：近期帖子权重更高（如对 `created_utc` 做指数衰减）。
  - 总分：`score = mentions*1.0 + post_score*0.002 + num_comments*0.001 + time_bonus`

## 输出目录与文件
- Reddit 原始与归一化（已存在）：
  - `outputs/wallstreetbets_raw_<listing>.json`
  - `outputs/wallstreetbets_normalized.json`
  - `outputs/wallstreetbets_normalized.csv`
  - `outputs/wallstreetbets_metadata.json`
- 新增：Ticker 热度与 Top N：
  - `outputs/wsb_tickers_rank.json`：每个 Ticker 的热度评分与来源统计。
  - `outputs/wsb_top10_tickers.json`：Top 10 列表（含分数与样本来源）。
- 股票数据（按 Ticker 分目录）：
  - `outputs/stocks/<TICKER>/quote.json`：最新行情与关键统计。
  - `outputs/stocks/<TICKER>/history_<granularity>.json`：历史 K 线。
  - `outputs/stocks/<TICKER>/fundamentals.json`：公司概览、财务报表、比率（视 Provider）。
  - `outputs/stocks/<TICKER>/options.json`：期权链（如启用且 Provider 支持）。
  - `outputs/stocks/<TICKER>/news.json`：新闻与情绪（如启用且 Provider 支持）。
  - `outputs/stocks/<TICKER>/news_summary.json`：该股票的简要新闻摘要（POC 格式，见下）。
  - 汇总：`outputs/stocks_summary.json`（抓取时间、完成率、失败列表、Provider 指标）。
 - 告警与运行：
   - `outputs/alerts.json`：本次扫描触发“attention”的股票列表与原因摘要。
   - `outputs/last_run.json`：上次运行的时间戳与统计。

## 字段与 Schema（示例）
- `wsb_tickers_rank.json`（数组）：
  - `ticker`：字符串，如 `AAPL`
  - `mentions`：整数
  - `post_score_sum`：整数
  - `num_comments_sum`：整数
  - `sources`：数组（Reddit 列表来源 `hot/new/top/rising/comments`）
  - `score`：浮点数（热度分数）
- `quote.json`：
  - `symbol`, `price`, `open`, `high`, `low`, `previous_close`, `volume`, `market_cap`, `pe`, `dividend_yield`, `currency`, `exchange`, `timestamp`
- `history_*.json`（数组）：
  - 每条：`date`, `open`, `high`, `low`, `close`, `volume`, `adj_close`（可选）
- `fundamentals.json`：
  - `profile`：`name`, `sector`, `industry`, `website`, `description`
  - `financials`：`income_statement`, `balance_sheet`, `cash_flow`（各为周期化条目数组）
  - `ratios`：如 `roe`, `roa`, `gross_margin`, `net_margin`
- `options.json`：
  - `expiration_dates`（数组），`chains`（按到期日分组的看涨/看跌合约列表）
- `news.json`：
  - 每条：`datetime`, `source`, `headline`, `summary`, `url`, `symbols`，`sentiment`（可选）

## Provider 选择与映射
- 默认：`yfinance`
  - 优点：免鉴权，易用；适合历史与部分基本信息。
  - 局限：抓取来源，稳定性与速率有限；基本面完整度欠缺；期权、新闻覆盖有限。
- 可选：
  - `alphavantage`：基本面（OVERVIEW/财务）+ 历史；免费层速率限制明显。
  - `finnhub`：画像、新闻、持仓/内幕、实时/延迟行情（多为付费）。
  - `fmp`（Financial Modeling Prep）：财务与公司画像覆盖较好；有免费层。
  - `polygon/iex/twelvedata`：更强的实时与期权数据（多付费）。
- 统一接口（建议）：
  - `fetch_quote(ticker) -> Dict`
  - `fetch_history(ticker, granularity, lookback) -> List[Dict]`
  - `fetch_intraday_1m(ticker, range) -> List[Dict]`
  - `fetch_fundamentals(ticker) -> Dict`
  - `fetch_options(ticker) -> Dict`
  - `fetch_news(ticker, window) -> List[Dict]`
 - 实现细节（当前 POC）：
   - `quote`：优先 `yfinance`（fast_info/info），缺失时回退 Yahoo v7 `/finance/quote`。
   - `symbol 映射`：点号改为短横（如 `BRK.B`→`BRK-B`）。
   - `intraday_1m`：优先 `yfinance`，失败时回退 Yahoo v8 `/finance/chart`（`range=1d&interval=1m`）。

## 新闻抓取与摘要（POC 简化）
- Provider 选择（按最少依赖）：
  - 默认使用 `yfinance.Ticker(t).news`（若可用）。
  - 若配置了 `ALPHAVANTAGE_API_KEY`，可使用 `NEWS_SENTIMENT` 作为补充。
  - 若配置了 `FINNHUB_TOKEN` 或 `FMP_API_KEY`，可分别调用其公司新闻端点。
- 抓取窗口：最近 24–48 小时（可配置）。
- 摘要方法（极简）：
  - 对每条新闻保留：`datetime`, `source`, `headline`, `summary`（若有）, `url`, `symbols`。
  - 生成 `news_summary.json`：
    - `top_headlines`：按时间与重要度挑选最近 3–5 条（含标题、来源、时间、链接）。
    - `overall_sentiment`：若 Provider 提供则汇总平均；否则 `neutral`。
    - `key_points`：从 `summary` 或标题中抽取 2–3 个要点（规则：句首两句或关键动词/事件词）。

## Attention 判定与告警邮件（POC 简化）
- 触发规则（任一满足即触发）：
  - Reddit 热度分数位于当次扫描的前 10（已筛选）且分数 > 设定阈值（如 `score >= 5`）。
  - 近 24h 新闻条数 >= 阈值（如 `count >= 3`），或存在关键词事件（`earnings`, `merger`, `SEC`, `downgrade`, `upgrade`）。
  - 价格变动幅度（相对前收）>= 阈值（如 `abs(change_pct) >= 3%`）。
- 邮件内容（极简）：
  - 主题：`[Attention] <TICKER> <change_pct>% — <top_headline>`
  - 正文：
    - 简介：触发原因与简短解释。
    - 关键数据：最新价、涨跌幅、成交量、市场值（若有）。
    - 新闻摘要：3–5 条标题 + 来源 + 时间 + 链接。
    - 免责声明：不构成投资建议。
- 发送方式：
  - 使用 SMTP 发送到 `SUBSCRIBERS_FILE` 列表（CSV 中单列 `email`）。
  - 失败重试 1 次；失败记录到 `alerts.json` 的 `delivery_failures`。

## 日志与可观测性（更新）
- 记录每小时扫描的开始/结束时间、耗时、Top10 列表与触发告警的股票。
- 将关键统计写入 `outputs/last_run.json` 与控制台日志。

## POC 最小化实现（聚焦核心功能）
- 步骤：
  1. 运行 Reddit 抓取，得到 `normalized` 数据。
  2. 提取 Ticker，调用 LLM（gpt-5，medium）返回 Top 10（含 `discussion_highlights`），输出 `stage1_top10.json`。
  3. 对 Top 10：抓取 `quote`（含 Yahoo v7 fallback）、`history_1d`（近 30 天）、`intraday_1m`（当日，若可用），输出 `stage2_enriched.json`。
  4. 抓取最近新闻并生成 `news.json` 与 `news_summary.json`。
  5. 应用简化触发规则，生成 `alerts.json`；满足条件则发邮件通知订阅者。
- 依赖：`requests`, `yfinance`（默认）；如需新闻加强，可加 `alphavantage`/`finnhub` KEY。
- 调度：建议使用系统 `cron` 每小时触发即可。

## 输出示例结构（简化）
- `outputs/wsb_top10_tickers.json`：`[{ticker, score, mentions, post_score_sum, num_comments_sum}]`
- `outputs/stocks/<T>/quote.json`：`{symbol, price, change_pct, volume, market_cap, timestamp}`（字段可因 Provider 有限而为空）
- `outputs/stocks/<T>/history_1d.json`：`[{date, open, high, low, close, volume}]`
 - `outputs/stocks/<T>/intraday_1m.json`：`[{datetime, open, high, low, close, volume}]`
- `outputs/stocks/<T>/news_summary.json`：`{top_headlines:[{title, source, time, url}], count, overall_sentiment, key_points:[...]}`
- `outputs/alerts.json`：`[{ticker, attention, severity, reasons:[...], top_headline, price_change_pct, news_count, run_ts}]`

## 简化与边界（避免过度设计）
- 不做复杂 NLP；新闻摘要以标题+已给摘要为主，最多 3–5 条。
- 不做多 Provider 融合；默认 `yfinance`，其余作为可选增强。
- 不做数据库；全部落地 JSON/CSV 文件即可。
- 不做并发复杂调度；串行或简单队列足够应对每小时频率。

## 错误处理与重试
- Reddit 抓取：429/超时时指数退避重试；分页中断时记录到元数据。
- 股票抓取：对单 Ticker 的各子任务独立重试（最多 N 次），失败写入 `stocks_summary.json`。
- 速率限制：Provider 特定的节流（sleep）与并发控制（队列/串行）。
- 数据质量：
  - 代码合法性验证（Provider 校验或本地库）。
  - 空数据与字段缺失填充为空字符串或 `null`，保持 CSV/JSON 可读性。

## 日志与可观测性
- 控制台日志：阶段开始/结束、各 Ticker 抓取耗时与结果。
- 结构化元数据：`wallstreetbets_metadata.json` 与 `stocks_summary.json` 聚合统计。
- 可选：Prometheus 指标或简单的 JSON 指标文件（成功率、重试次数）。

## 实现建议（最小可用版本）
- 新增脚本：`scripts/run_pipeline.py`
  - 调用 `fetch_wsb_reddit.py`（或直接 import 其函数），收集 `normalized` 数据。
  - 识别 Ticker（正则 + 过滤 + 可选的 Provider 验证）。
  - 计算热度并输出 `wsb_tickers_rank.json` 与 `wsb_top10_tickers.json`。
  - 调用 Provider 封装，拉取 Top 10 的数据并落盘至 `outputs/stocks/<TICKER>/...`。
- 依赖（建议）：
  - `requests`（已用）、`yfinance`（默认 Provider）、`pandas`（可选，用于 CSV 处理）
- 配置读取：
  - 支持 CLI 参数与环境变量（如 `STOCK_API_PROVIDER`、各 API KEY）。

## 安全与合规
- 免责声明：输出仅供信息参考，不构成投资建议。
- 遵守各 Provider 的使用条款与速率限制；不得非法再分发受限数据。

## 测试与验收
- 单元测试（可选）：Ticker 识别与热度计算函数的测试用例。
- 集成测试（可选）：对小样本 Reddit 数据运行端到端，验证输出文件存在与非空。
- 验收标准：
  - 能稳定生成 Top 10 Ticker 列表。
  - 每个 Ticker 至少输出 `quote.json` 与 `history_*.json` 两类文件。
  - 元数据包含成功率与失败列表。

## 里程碑
- M1（最小版本）：完成 Top 10 识别与 `yfinance` 行情/历史输出。
- M2：加入基本面与期权。
- M3：加入新闻与情绪；可视化报表（可选）。
## 组件架构（POC）
- 组件 1：热点与新闻（Hotness & News）
  - 职责：抓取 Reddit（WSB），调用 LLM 从讨论中识别并输出最热的 10 个股票及“需要关注的点”，生成阶段 1 JSON；可选拉取最近新闻并简要摘要。
  - 输入：无（运行时从 Reddit 获取）。
  - 输出：`outputs/stage1_top10.json`（核心）、可选 `outputs/stocks/<T>/news.json` 与 `outputs/stocks/<T>/news_summary.json`。
- 组件 2：股票详情（Stock Details）
  - 职责：为 Top10 拉取最新的指标数据（POC：quote + 近 30 天日线 + 当日 1 分钟线），并补充合并进阶段 1 的 JSON。
  - 输入：Top10 Ticker 列表。
  - 输出：`outputs/stocks/<T>/quote.json`、`outputs/stocks/<T>/history_1d.json`、`outputs/stocks/<T>/intraday_1m.json`（如可用），以及合并后的 `outputs/stage2_enriched.json`。
- 组件 3：综合分析与告警（Analyzer）
  - 职责：调用 LLM 逐个分析是否需要 Attention，在 JSON 为每个股票打标 `attention_needed` 并生成 `email content`，触发邮件通知。
  - 输入：阶段 2 合并后的 JSON。
  - 输出：`outputs/stage3_analyzed.json`（最终决策 JSON）、`outputs/alerts.json`（便于流水线读取）、`outputs/last_run.json`（运行统计）、邮件通知（如触发）。

## 组件接口（极简）
- 组件 1：
  - `llm_top10(records) -> List[stage1_item]`（LLM 输出 Top10 与关注点）
  - 可选：`fetch_news(ticker, hours=48) -> List[news_item]`
  - 可选：`summarize_news(items) -> news_summary`
- 组件 2：
  - `fetch_quote(ticker) -> Dict`
  - `fetch_history(ticker, granularity="1d", lookback="30d") -> List[Dict]`
  - `fetch_intraday_1m(ticker, range="1d") -> List[Dict]`
  - `enrich_stage1(stage1_items, quotes, histories) -> stage2_enriched`
- 组件 3：
  - `llm_attention_decision(stage2_enriched_item) -> {attention_needed, severity, reasons, email}`
  - `send_alert_email(ticker, email_subject, email_body, recipients) -> bool`

## 运行顺序（每小时）
1. 组件 1：抓取 Reddit → 调用 LLM 提取 Top10 与关注点（含讨论摘要）→ 可选拉取新闻并摘要 → 写入 `stage1_top10.json`。
2. 组件 2：为 Top10 拉取 `quote` + 近 30 天 `history_1d` + 当日 `intraday_1m` 并合并到 JSON（`stage2_enriched.json`）。
3. 组件 3：调用 LLM 逐个给出 Attention 决定与邮件内容 → 写入 `stage3_analyzed.json` 与 `alerts.json` → 触发邮件（如需要）。

## LLM Provider 与配置（POC）
- 环境变量：
  - `LLM_PROVIDER`：`openai`（默认）或 `ollama/azure/anthropic`。
  - `LLM_MODEL`：默认 `gpt-5`（中等推理能力）。
  - `LLM_API_KEY`：对应 Provider 的 Key。
  - 可选：`LLM_BASE_URL`（自托管或代理）。
- 成本控制：Top10 任务使用精简英文提示与裁剪后的帖子内容；限制输入长度在数百 Tokens 级别。

## 阶段输出 JSON 合同（核心）
- 阶段 1（`outputs/stage1_top10.json`）：
  - `run_ts`: ISO 时间戳
  - `items`: 数组（最多 10 项），每项：
    - `ticker`: 股票代码（字符串）
    - `attention_points`: 数组（2–5 条，英文，精炼短句）
    - `discussion_highlights`: 数组（2–4 条，英文，来自近期讨论的简短要点）
    - `sources`: 可选，数组（Reddit `permalink` 或 `id`）
    - `heat_score`: 可选，0–10 浮点（LLM 估计或简单计数）
- 阶段 2（`outputs/stage2_enriched.json`）：
  - 基于阶段 1 的结构，给每项新增：
    - `data.quote`: `{price, change_pct, open, high, low, previous_close, volume, market_cap, currency, timestamp}`（字段缺失可为空）
    - `data.history_1d`: 数组 `[{date, open, high, low, close, volume}]`（近 30 天）
    - `data.intraday_1m`: 数组 `[{datetime, open, high, low, close, volume}]`（当日 1 分钟线，如可用）
    - 可选：`data.fundamentals`（如 Provider 可用）
- 阶段 3（`outputs/stage3_analyzed.json`）：
  - 在阶段 2 的每项追加：
    - `analysis.attention_needed`: 布尔
    - `analysis.severity`: `watch|alert`
    - `analysis.reasons`: 数组（2–4 条简洁理由）
    - `analysis.email.subject`: 字符串
    - `analysis.email.body`: 文本（不超过 10 行，包含触发原因与关键数据/新闻要点）
  - 另存：`outputs/alerts.json`（仅包含 `ticker`, `attention_needed`, `severity`, `email_subject`, `email_body` 与 `run_ts`）。

## LLM 提示词（Prompt）示例（POC）
- 阶段 1（提取 Top10 与关注点）：
  - 系统（英文）：You are a financial assistant. From recent r/wallstreetbets posts, extract the top tickers and summarize why they are active. Return JSON with `items` (max 10): `ticker`, `attention_points` (<=5), `discussion_highlights` (<=4), `sources` (<=3 permalinks), `heat_score` (0–10).
  - 用户输入：`normalized_posts`（title、selftext（裁剪）、score、num_comments、created_utc、flair、permalink）。
  - 输出：纯 JSON（英文）。
- 阶段 3（Attention 与邮件）：
  - 系统（英文，保守判定）：You are a conservative risk-control assistant. Set `attention_needed=true` ONLY if a major event exists (earnings now, M&A, SEC action, major guidance, scandal) OR at least two strong signals hold (|price_change_today| ≥ 3%, unusual volume ≥ 2x recent average, ≥ 3 credible news in 48h, concrete catalyst in Stage1 highlights). If insufficient/ambiguous, default to false. Return only JSON: `{attention_needed, severity ('watch'|'alert'), reasons (<=4), email {subject, body (<=10 lines)}}`。
  - 用户输入：`stage2_enriched_item`（含 30d 日线与当日 1m 分钟线，Stage1 attention_points 与 discussion_highlights）。

## Attention 判定的最小信号（POC）
- Reddit 热度：Top10 中且 `score >= 5`。
- 新闻脉冲：近 24–48h 新闻条数 `>= 3` 或包含关键词：`earnings|merger|SEC|downgrade|upgrade|guidance|investigation`。
- 价格波动：相对前收盘 `abs(change_pct) >= 3%`。
- 成交量异常（可选）：当日成交量 `>= 2x` 近 20 日均量（若可获取）。
- 决策：满足任意一类信号 → `attention=true`，`severity` 依据信号数量与类型（例如 1 条为 `watch`，2 条以上含价格/新闻为 `alert`）。

## 指数与指标关注（POC）
- 指数监控清单（可扩展）：`INDEX_WATCHLIST = ["SPY","QQQ","IWM","DIA","^GSPC","^IXIC","^RUT"]`
- 规则：同样应用“新闻脉冲 + 价格波动”简化逻辑；若 Top10 中存在指数或 Reddit 频繁提及指数词（如 `SPY`），同样进入分析。
- 指标（不超工程）：仅使用变动幅度与新闻数量；高级指标（波动率、期权偏度）暂不在 POC 内。

## 系统设计总览
- 管道：每小时触发 → 阶段 1（LLM 提取 Top10 与关注点）→ 阶段 2（API 获取详情并合并）→ 阶段 3（LLM 决策 + 邮件）。
- 数据流：
  - 输入：`outputs/wallstreetbets_normalized.json`（或直接通过函数返回）
  - 阶段 1 输出：`outputs/stage1_top10.json`
  - 阶段 2 输出：`outputs/stage2_enriched.json` + 各股票数据文件
  - 阶段 3 输出：`outputs/stage3_analyzed.json` + `outputs/alerts.json` + 邮件发送
- 设计原则：
  - POC 优先：函数简单、串行执行、错误尽量记录而不是中断整体流程。
  - 可插拔 Provider：LLM 与股票数据来源通过环境变量切换。

## 目录结构建议
```
StockAnalysis/
  scripts/
    fetch_wsb_reddit.py           # 已有：抓取并归一化 Reddit 数据
    run_pipeline.py               # 主入口（每小时），串行调用 3 阶段
    component_stage1_llm.py       # 阶段 1：LLM 提取 Top10 与关注点
    component_stage2_enrich.py    # 阶段 2：数据抓取与合并
    component_stage3_analyze.py   # 阶段 3：LLM 判定与邮件通知
  providers/
    yfinance_client.py            # 行情与历史数据
  utils/
    llm_client.py                 # 统一 LLM 调用封装
    email_sender.py               # SMTP 发送工具
    io_helpers.py                 # 读写 JSON/CSV 的小工具
    ticker_utils.py               # Ticker 校验/格式化
  spec/
    spec.md                       # 本说明
  config/
    subscribers.csv               # 订阅者邮件列表（一列 email）
  outputs/                        # 运行生成的输出文件
  requirements.txt
```

## 关键模块说明
- 阶段 1（`component_stage1_llm.py`）
  - 读取 `outputs/wallstreetbets_normalized.json` 或直接接收列表。
  - 构造提示词，将帖子标题/自述/score/num_comments 精简后传入 LLM。
  - 控制上下文长度：仅取最近 N 页与前 M 条高分帖子。
  - 生成 `outputs/stage1_top10.json`：包含 `ticker` 与 `attention_points`。
- 阶段 2（`component_stage2_enrich.py`）
  - 使用 `providers/yfinance_client.py`：`fetch_quote` 与 `fetch_history`。
  - 计算 `change_pct = (price - previous_close) / previous_close * 100`（若字段可用）。
  - 合并输出为 `outputs/stage2_enriched.json` 并保留阶段 1 的关注点。
- 阶段 3（`component_stage3_analyze.py`）
  - 对 `stage2_enriched.json.items` 逐个调用 LLM：提供行情/历史片段与关注点。
  - 输出 `attention_needed`、`severity`、`reasons`、以及邮件 `subject/body`。
  - 写入 `outputs/stage3_analyzed.json` 与 `outputs/alerts.json`；通过 `utils/email_sender.py` 发送通知。
- LLM 客户端（`utils/llm_client.py`）
  - 读取 `LLM_PROVIDER/LLM_MODEL/LLM_API_KEY/LLM_BASE_URL`。
  - 暴露 `generate(prompt, system=None, temperature=0)`。
- 邮件发送（`utils/email_sender.py`）
  - 读取 `SMTP_*` 与 `EMAIL_FROM`，加载 `config/subscribers.csv`。
  - 函数：`send_email(subject, body, recipients) -> bool`。
- Ticker 工具（`utils/ticker_utils.py`）
  - 规范化：如去除 `$` 前缀、统一大小写、处理 `BRK.B` 这类包含点的代码。
  - 校验：可选通过 Provider/本地列表确认是否有效。

## 接口与类型（简化）
- `Stage1Item`：`{ticker: str, attention_points: List[str], sources?: List[str], heat_score?: float}`
- `Quote`：`{price?: float, change_pct?: float, open?: float, high?: float, low?: float, previous_close?: float, volume?: int, market_cap?: float, currency?: str, timestamp?: str}`
- `Candle1D`：`{date: str, open?: float, high?: float, low?: float, close?: float, volume?: int}`
- `Stage2Item`：`{ticker: str, attention_points: List[str], data: {quote: Quote, history_1d: List[Candle1D], fundamentals?: Dict}}`
- `Stage3Item`：`{ticker: str, attention_points: List[str], data: {...}, analysis: {attention_needed: bool, severity: str, reasons: List[str], email: {subject: str, body: str}}}`

## 时序流程与伪代码
- `run_pipeline.py`：
```
def run():
  posts = load_or_fetch_reddit_normalized()
  stage1 = stage1_llm(posts)
  save_json("outputs/stage1_top10.json", stage1)

  enriched = stage2_enrich(stage1)
  save_json("outputs/stage2_enriched.json", enriched)

  analyzed = stage3_analyze_llm(enriched)
  save_json("outputs/stage3_analyzed.json", analyzed)
  alerts = extract_alerts(analyzed)
  save_json("outputs/alerts.json", alerts)
  send_emails(alerts)
  save_last_run_stats()
```

## 配置管理
- 优先使用环境变量；如需本地 `.env`，读取并注入进环境。
- 关键参数：`LLM_*`, `SMTP_*`, `STOCK_API_PROVIDER`, `ALPHAVANTAGE_API_KEY` 等。
- 默认值：模型用低成本，Provider 用 `yfinance`，扫描窗口 48h，TopN=10。

## 错误处理与重试
- Reddit/HTTP：设置 `timeout` 与有限重试（如 2 次），错误落盘到 `last_run.json`。
- LLM：失败返回空列表或默认判定为 `attention_needed=false`；记录错误信息。
- 股票 API：单 Ticker 失败不影响其他；在 `stage2_enriched.json` 标注 `data_error=true`。
- 邮件：失败重试 1 次；依旧失败则在 `alerts.json` 标注 `delivery_failed=true`。

## 日志与可观测性
- 控制台输出关键进度与统计；文件 `outputs/last_run.json` 记录：
  - `run_ts`, `duration_ms`, `top10_count`, `alerts_count`, `errors: [...]`。
- 可选：在 `outputs/logs/` 写入 JSONL 形式流水日志（POC 可省略）。

## 性能与成本
- LLM：阶段 1 1 次调用（聚合 Top10），阶段 3 最多 10 次调用；总 Tokens 控制在几千以内。
- 数据抓取：`yfinance` 顺序调用；若需加速可做小并发（POC 可串行）。
- 文件 I/O：JSON 写入按需覆盖，避免多版本冗余。

## 安全与合规
- 密钥与口令仅存环境变量或本地未提交的 `.env`；不入库。
- 邮件内容含免责声明，不构成投资建议。
- 遵守各数据源的使用条款与速率限制。

## 部署与运行
- 依赖安装：`pip install -r requirements.txt`
- Python 版本：`>= 3.9`
- 定时：系统 `cron` 每小时运行一次（见前述示例）。
- 可选容器：Docker（POC 可不做）。

## 测试计划（轻量）
- 单元测试：
  - `stage2_enrich` 合并与 `change_pct` 计算。
  - `yfinance_client`：点号转短横符号映射（如 `BRK.B`→`BRK-B`）。
  - `quote` 回退：yfinance 为空时使用 Yahoo v7 `/finance/quote`。
  - `intraday_1m`：yfinance 与 Yahoo v8 `/finance/chart` 回退路径。
  - `email_sender` 在本地 SMTP/捕获方式下的发送成功路径。
- 集成测试：
  - 以小样本 `normalized_posts` 运行端到端，检查输出文件存在与关键字段非空。
- LLM 测试：
  - 使用少量帖子验证能稳定返回不超过 10 个 `ticker` 与英文关注点/讨论摘要；如异常，降级为规则提取（fallback）。

## 风险与边界
- LLM 可能产生幻觉：通过 Ticker 校验与关注点简化降低风险。
- `yfinance` 数据质量有限：作为 POC 数据源，正式环境应更换为商业 API。
- 邮件投递合规：仅向授权订阅者发送；后续需加入退订机制（POC 暂不覆盖）。

## 未来扩展
- 改用更稳定的行情与新闻 API（Polygon/Finnhub/FMP 等）。
- 新闻情绪打分与更细的事件分类（财报、并购、监管）。
- 指数与板块联动分析；多维度关注条件（期权异常、波动率飙升）。
- 简易前端或仪表盘；告警记录与趋势回溯。

## 阶段 4：写库（SQLite）
- 目标：在阶段 3 完成后，将本次分析结果落入 SQLite，供后续 API 查询使用。
- 数据库文件：`data/attention.db`（可配置环境变量 `SQLITE_PATH`）。
- 表结构（POC，尽量简单）：
  - `runs`
    - `run_id` INTEGER PRIMARY KEY AUTOINCREMENT
    - `run_ts` TEXT NOT NULL  // ISO 时间戳
    - `duration_ms` INTEGER
    - `top10_count` INTEGER
    - `alerts_count` INTEGER
    - `errors_json` TEXT  // JSON 字符串
  - `alerts`
    - `id` INTEGER PRIMARY KEY AUTOINCREMENT
    - `run_id` INTEGER NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE
    - `ticker` TEXT NOT NULL
    - `severity` TEXT  // watch|alert
    - `attention_needed` INTEGER NOT NULL  // 0/1
    - `reasons_json` TEXT  // JSON 数组字符串
    - `email_subject` TEXT
    - `email_body` TEXT
    - `price` REAL NULL
    - `change_pct` REAL NULL
    - `news_count` INTEGER NULL
    - `data_snapshot_json` TEXT  // 阶段 2/3 的合并结果快照（JSON 字符串）
    - `created_at` TEXT  // ISO 时间戳
    - UNIQUE(`run_id`, `ticker`)
  - 索引：
    - `CREATE INDEX idx_alerts_run ON alerts(run_id);`
    - `CREATE INDEX idx_alerts_ticker ON alerts(ticker);`
    - `CREATE INDEX idx_alerts_attn ON alerts(attention_needed, severity);`
- 初始化：启动时若不存在则创建表；`scripts/component_stage3_analyze.py` 完成写库。
- 写入流程：
  1. 新增一条 `runs` 记录，返回 `run_id`。
  2. 遍历阶段 3 的 `alerts` 项，插入到 `alerts` 表（含快照与邮件内容）。
  3. 更新 `runs.alerts_count`、`runs.duration_ms` 等统计。

## 阶段 5：API（展示需要关注的股票）
- 目标：提供一个简单 HTTP API，展示最新一批需要关注的股票（最后一次 run 的结果）。
- 技术选型：`Flask`（POC 轻量）；可选 `FastAPI`（如需自动文档）。
- 目录结构：
  - `server/app.py`：Flask 应用入口。
  - `server/db.py`：SQLite 连接与查询封装（读取 `SQLITE_PATH`）。
- 运行方式：
  - `python server/app.py`（开发模式）；或 `gunicorn -w 2 -b 0.0.0.0:8000 server.app:app`。
- 配置：
  - `SQLITE_PATH` 环境变量（默认 `data/attention.db`）。
  - 可选 `API_PORT`（默认 8000）。
- 端点设计（JSON 响应）：
  - `GET /health`
    - 响应：`{status: "ok"}`
  - `GET /alerts/latest`
    - 描述：返回最近一次 run 的全部 `attention_needed==true` 的股票列表。
    - 响应：
      - `run`: `{run_id, run_ts, alerts_count}`
      - `items`: `[{ticker, severity, reasons: [...], email_subject, email_body, price, change_pct, news_count}]`
  - `GET /alerts/latest/summary`
    - 描述：返回最近一次 run 的摘要统计。
    - 响应：`{run_id, run_ts, total_items, attention_items, by_severity: {watch, alert}}`
  - `GET /alerts/by_run/{run_id}`（可选）
    - 描述：返回指定 `run_id` 的全部结果。
- 查询逻辑：
  1. 查 `runs` 表最大 `run_id` 作为最新批次。
  2. 查 `alerts` 中 `attention_needed=1 AND run_id=?` 的记录，按 `severity DESC, ticker ASC` 排序。
- 响应字段来源：
  - 直接取自 `alerts` 表的列与 `data_snapshot_json` 中的部分关键字段（如需补充）。
- 错误处理：
  - 库不存在或无数据：返回 `404` 或空列表，`run_id=null`。
  - 查询异常：返回 `500` 与简单错误信息（不泄露内部细节）。

## API 返回示例
- `GET /alerts/latest`
```
{
  "run": {"run_id": 42, "run_ts": "2025-09-27T08:00:00Z", "alerts_count": 5},
  "items": [
    {
      "ticker": "AAPL",
      "severity": "alert",
      "reasons": ["新闻脉冲：近48h 5条", "价格波动：+3.8%"],
      "email_subject": "[Attention] AAPL +3.8% — 新品发布会预期",
      "email_body": "触发原因：新闻密集+股价显著波动...",
      "price": 234.56,
      "change_pct": 3.8,
      "news_count": 5
    }
  ]
}
```

## 集成与部署（更新）
- 阶段 3 完成后写库；API 独立进程读取库提供查询。
- 部署：
  - 管道（cron）与 API 可在同一机器不同进程运行。
  - 访问控制：POC 暂不做鉴权；若外网暴露，建议加入简单的 IP 白名单或只在内网可见。
- 监控：
  - API `GET /health` 用于存活检查；可加简单日志记录请求量与错误率。

---

## 系统更新（2025-09-27）

### 阶段 3（Analyzer）改进
- 并发：默认 10 线程（环境变量 `STAGE3_WORKERS`，默认 `10`）。每线程独立 LLM 客户端（避免线程安全问题），保持输入顺序。
- 判定严格度：通过 `ATTENTION_STRICTNESS=relaxed|balanced|strict` 动态调整提示词逻辑（默认 `balanced`）。
- 写库与邮件：阶段 3 完成后直接写入 SQLite（`data/attention.db` 或 `DB_PATH/SQLITE_PATH`），并触发邮件发送（见“邮件发送（Composio）”）。

### 阶段 4（Notifier）新增
- 独立脚本：`scripts/component_stage4_notify.py`。
- 行为：读取 `outputs/stage3_analyzed.json`（可配置 `STAGE4_INPUT`），对所有 `attention_needed=true` 的项发送邮件，输出到 `outputs/stage4_email_summary.json`（可配置 `STAGE4_OUTPUT`）。

### API 扩展（FastAPI）
- 新增服务入口：`server/fastapi_app.py`。保留 `server/app.py`（Flask）作为 POC。
- 新端点：
  - `GET /runs/latest/items`：返回最新一次 run 的全部股票（含非关注项）
    - 响应：`{ run: {run_id, run_ts, alerts_count, top10_count}, items: [{ticker, attention_needed, severity, reasons, email_subject, email_body, price, change_pct, news_count, attention_points, heat_score}] }`
- 现有端点：
  - `GET /health`、`GET /alerts/latest`、`GET /alerts/latest/summary`
- CORS：允许前端访问，`CORS_ORIGINS`（逗号分隔，默认 `*`）。

### 邮件发送（Composio）
- 工具：Composio 的 `GMAIL_SEND_EMAIL`（OpenAI tools 调用）。
- 收件人：优先 `ALERT_RECIPIENTS`（逗号分隔），否则读取 `SUBSCRIBERS_CSV`（默认 `config/subscribers.csv`）。
- 环境：
  - `COMPOSIO_USER_ID`：需与绑定 Gmail 的用户一致，否则会出现 “No connected account found”。
  - `EMAIL_LOG_LEVEL=DEBUG|INFO`、`EMAIL_DRY_RUN=1`（干跑）、`EMAIL_LOG_FILE`（可选）。
- 失败处理：最佳努力，单封失败记录到汇总但不影响整体流程。

### 其他配置与约定
- LLM：`LLM_MODEL`（默认 `gpt-5`）、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_REASONING_EFFORT`（默认 `medium`）。
- 数据库路径：`DB_PATH`（优先）或 `SQLITE_PATH`（默认 `data/attention.db`）。
- API 端口：`API_PORT`（默认 `8000`）。
