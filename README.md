# 每日全球新闻邮件（零成本）

每天当地 10 点，把过去 24 小时的全球要闻发到你的邮箱。无 API、无服务器、无费用。

## 5 分钟发布
1. 在 GitHub 新建一个仓库（建议 **Public**，Actions 完全免费），把本文件夹全部内容（含隐藏的 `.github`）上传。
2. 开通 Gmail 应用专用密码：Google 账号 → 安全性 → 开启两步验证 → 搜索“应用专用密码”，生成 16 位密码。
3. 仓库 → Settings → Secrets and variables → Actions → New repository secret，添加：
   - `GMAIL_USER`：你的 Gmail 地址
   - `GMAIL_APP_PASSWORD`：上一步的 16 位密码
   - `TO_EMAIL`：收件邮箱（可与发件相同；用别的邮箱收件也行）
4. Actions 页 → daily-news → Run workflow，立刻收到一封测试邮件。

## 换时区
改 `config.json` 里的 `timezone`（如 `Asia/Tokyo`、`America/New_York`），直接在 GitHub 网页上编辑保存即可。

## 自定义
`config.json` 可改：新闻源 `feeds`、条数、关注关键词 `boost_keywords`（命中会排前面）。

## 注意
- 定时任务有时会延迟几分钟，偶尔漏跑属正常；邮件通常在 10:00–10:30 之间到。
- 仓库 60 天无任何提交，GitHub 会暂停定时任务，到 Actions 页点一下重新启用即可。
- 个别 RSS 地址如果失效，邮件底部会显示“未能获取”，换个地址即可。
