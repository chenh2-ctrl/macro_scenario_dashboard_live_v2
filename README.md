# 六情景宏观雷达：免服务器自动更新版 v2

这是可部署版本，**不是已部署的网址**。默认以 GitHub Pages 托管前端，GitHub Actions 在云端约每小时尝试从 FRED 抓取新公布的经济数据，同一个任务直接部署静态网站，解决“机器人提交数据却不会触发 Pages 分支发布”的问题。网页打开时每 5 分钟查询最新 JSON；网站无需长期打开，数据照常由 GitHub 更新。

## 首次上线（不需要服务器）

1. 在 github.com 登录并创建一个新仓库，例如 `macro-regime-radar`。默认分支为 `main`。建议仅放公开宏观指标；**GitHub Pages 网页默认面向公众**。
2. 将本文件夹的 **内容** 上传到仓库根目录（不是把整个文件夹额外套一层）。必须保留：`index.html`、`data/snapshot.json`、`data/history.json`、`scripts/update_data.py`、`.github/workflows/update.yml`。如果使用 GitHub Desktop，可将本文件夹作为本地仓库提交后 Publish；Mac Finder 按 Cmd+Shift+. 可显示 `.github` 隐藏文件夹。
3. 进入 GitHub 仓库 `Settings → Pages → Build and deployment → Source`，选择 **GitHub Actions**。不要选 `Deploy from a branch`，因为本版会在同一个更新流程里直接发布。
4. 进入 `Settings → Actions → General → Workflow permissions`，若提示 `Resource not accessible by integration` 或 `403`，选择 `Read and write permissions` 并保存。还要确保 Actions 已启用。某些账户/组织政策不允许修改，此时需要管理员授权。
5. 到仓库 `Actions`，选 `Refresh macro data and publish dashboard`，点击 `Run workflow → main → Run workflow`。首次如果由于 Pages 尚未设置而失败，完成第 3 步后重新点击一次。
6. 等待任务出现绿色勾，打开 `Settings → Pages → Visit site`。网址通常为 `https://你的用户名.github.io/macro-regime-radar/`。
7. 验证 `https://你的用户名.github.io/macro-regime-radar/data/snapshot.json` 可以访问，且 Dashboard 卡片能够显示新的 `generated_at` 和具体指标 `asof` 日期。

## 自动更新机制

- 定时任务：`.github/workflows/update.yml` 中 `cron: '17 * * * *'`，即每小时 UTC 第 17 分钟左右。GitHub 排队可能延迟或丢次，不是硬实时 SLA。要改成每 2 小时：`cron: '17 */2 * * *'`。
- 数据脚本：`scripts/update_data.py`。从 FRED 的可公开下载 CSV 获取 Brent、2Y/10Y/30Y、10Y TIPS、通胀补偿、HY 利差、失业率、核心 PCE（同比和 3 个月年化）、非农企业劳动生产率同比。FRED 有的数据源本身是 ICE BofA 等第三方授权数据，使用时遵循原数据许可。抓取失败时保留最后成功快照，不伪造数据。
- JSON：`data/snapshot.json` 保存每个指标自己的 `asof` 观察日期。只有官方数值或观察日期改变时才更新历史和提交，避免每小时都产生虚假的“新信号”。
- 情景历史：`data/history.json` 保存由公开数据变化产生的六情景**规则拟合权重**记录，跨浏览器同步。它不是经过统计回测的后验概率，初始条目是研究先验，不允许被画成历史估计。
- 发布：工作流每次运行直接运行 Pages 部署；无需等待 Actions 机器人提交后再次触发 Pages 构建。
- 网页：打开时及之后每 300 秒读取 `data/snapshot.json` 和 `data/history.json`。不开网页也不影响 GitHub 定时更新；不开网页时不会弹出网页端提醒。

## 仍需补齐的研究数据

- ISM 新订单与价格指数：目前每月人工复核录入，没有自动更新接口。核验后可通过 GitHub 网页编辑 `data/snapshot.json` 里的 `value` 和 `asof` 再提交；下一次 Actions 会将改动写入历史。
- AI CAPEX、云厂商指引、Backlog：必须从官方季度财报、管理层指引查证，当前不是自动源。可以按上面同样方式手动修改 `capexgrowth`、`capexcuts`。
- 10Y 期限溢价：目前为空，后续可接入纽约联储 ACM 数据。
- ChatGPT 六情景提醒：已有独立的 ChatGPT 每小时任务，但**尚未共享数据/概率历史后端**；网页的历史数据不自动写回 ChatGPT 任务，也不代表你能收到网页 Push 通知。

## 排错

- 页面显示旧数据：先去 `Actions` 看定时工作流有没有执行及是否失败，再打开 `/data/snapshot.json` 检查日期。不要把 GitHub 最后一次执行时间当作宏观数据观测时间。
- Actions绿色勾但指标旧：源机构可能还未发布新数值，也可能某一数据源被暂时限制，展开 `Refresh public macro data` 的日志查看 WARN。
- 部署报错 `pages:write` 或 `id-token`：确认 Pages 设置为 GitHub Actions；工作流已在默认分支 `main`；组织账户可能限制权限。
- GitHub 官方提醒：公开仓库如果 60 天没有活动，计划任务可能被自动停用。定期查看 Actions 或进行合理维护，不保证永久无需维护。
- 如果你需要私人权限控制的网站，不建议 GitHub Pages，因为即使私有仓库在适用套餐上部署，网站仍可能公开；应迁移到带认证的托管系统。

## 链接

- GitHub Pages 官方文档：https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- GitHub Pages 自定义工作流：https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
