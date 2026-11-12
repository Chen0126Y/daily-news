#!/usr/bin/env python3
"""每日全球新闻邮件：纯标准库、零 API、零成本。
用法:
  python news_digest.py            # 到本地发送时刻才发送（供定时任务每小时调用）
  python news_digest.py --force    # 立即发送
  python news_digest.py --dry-run  # 不发邮件，生成 preview.html
"""
import html, json, os, re, smtplib, ssl, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

STOP = set("the and for with from that this have has had will would are was were been about after over into amid says said say new more than their they its his her you not but out who what when why how can could may might one two".split())
UA = "Mozilla/5.0 (daily-news-digest)"


def local(tag):
    return tag.rsplit("}", 1)[-1]


def kid(el, names):
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse_feed(data, source):
    root = ET.fromstring(data)
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        t = kid(el, ("title",))
        l = kid(el, ("link",))
        d = kid(el, ("pubDate", "published", "updated", "date"))
        if t is None or l is None or d is None:
            continue
        link = (l.text or "").strip() or l.attrib.get("href", "")
        title = re.sub(r"\s+", " ", html.unescape("".join(t.itertext()))).strip()
        when = parse_date(d.text)
        if title and link and when:  # 没有发布时间的一律丢弃，保证“过去24小时”准确
            items.append({"title": title, "link": link, "source": source, "time": when})
    return items


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def tokens(title):
    t = title.lower()
    words = {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in STOP}
    for run in re.findall(r"[\u4e00-\u9fff]+", title):
        words |= {run[i:i + 2] for i in range(len(run) - 1)}
    return words


def similar(a, b):
    shared = len(a & b)
    return shared >= 3 and shared / max(1, min(len(a), len(b))) >= 0.45


def cluster(items):
    clusters = []
    for it in sorted(items, key=lambda x: x["time"]):
        tk = tokens(it["title"])
        it["_tk"] = tk
        for c in clusters:
            if it["source"] not in {m["source"] for m in c} and any(similar(tk, m["_tk"]) for m in c):
                c.append(it)
                break
        else:
            clusters.append([it])
    return clusters


def score(c, boosts):
    n = len({m["source"] for m in c})
    text = " ".join(m["title"] for m in c).lower()
    b = sum(0.5 for k in boosts if k.lower() in text)
    return n + b + max(m["time"] for m in c).timestamp() / 1e11


def render(confirmed, single, now_local, failed, hours):
    def li(c):
        head = c[0]
        others = "".join(
            f' · <a href="{html.escape(m["link"])}" style="color:#666">{html.escape(m["source"])}</a>' for m in c[1:]
        )
        srcs = len({m["source"] for m in c})
        tag = f'<span style="color:#0a7">✔ {srcs}家媒体</span> ' if srcs > 1 else ""
        t = head["time"].astimezone(now_local.tzinfo).strftime("%m-%d %H:%M")
        return (f'<li style="margin:0 0 14px"><a href="{html.escape(head["link"])}" style="color:#111;font-weight:600;'
                f'text-decoration:none">{html.escape(head["title"])}</a><br>'
                f'<span style="font-size:12px;color:#888">{tag}{html.escape(head["source"])} · {t}{others}</span></li>')

    h = [f'<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:680px;margin:auto;line-height:1.5">',
         f'<h2>🌍 全球新闻 · {now_local:%Y-%m-%d}</h2>',
         f'<p style="color:#888;font-size:12px">过去{hours}小时 · 标题均为媒体原文，未经改写 · 时间为当地时间</p>',
         '<h3>多源确认</h3><ol style="padding-left:20px">']
    h += [li(c) for c in confirmed] or ["<p>暂无多家媒体共同报道的事件</p>"]
    h.append("</ol>")
    if single:
        h.append('<h3>单一来源 · 待证实</h3><ul style="padding-left:20px">')
        h += [li(c) for c in single]
        h.append("</ul>")
    if failed:
        h.append(f'<p style="color:#bbb;font-size:11px">未能获取：{html.escape("、".join(failed))}</p>')
    h.append("</div>")
    return "\n".join(h)


def send(subject, body):
    user, pwd = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    raw = os.environ.get("TO_EMAIL") or user
    to_list = [a.strip() for a in re.split(r"[,;，；\s]+", raw) if a.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, user
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pwd)
        s.sendmail(user, to_list, msg.as_string())


def main(argv):
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
    now_local = datetime.now(ZoneInfo(cfg["timezone"]))
    if "--force" not in argv and "--dry-run" not in argv and now_local.hour != cfg["send_hour"]:
        print(f"{cfg['timezone']} 现在 {now_local:%H:%M}，不是 {cfg['send_hour']} 点，跳过。")
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["window_hours"])
    items, failed = [], []
    for f in cfg["feeds"]:
        try:
            got = [i for i in parse_feed(fetch(f["url"]), f["name"]) if cutoff <= i["time"] <= datetime.now(timezone.utc) + timedelta(minutes=5)]
            print(f"{f['name']}: {len(got)} 条")
            items += got
        except Exception as e:
            print(f"{f['name']} 失败: {e}")
            failed.append(f["name"])
    clusters = sorted(cluster(items), key=lambda c: score(c, cfg["boost_keywords"]), reverse=True)
    ms = cfg["min_sources_confirmed"]
    confirmed = [c for c in clusters if len({m["source"] for m in c}) >= ms][: cfg["max_events"]]
    single = [c for c in clusters if len({m["source"] for m in c}) < ms][: cfg["max_single"]]
    body = render(confirmed, single, now_local, failed, cfg["window_hours"])
    if "--dry-run" in argv:
        open("preview.html", "w", encoding="utf-8").write(body)
        print("已生成 preview.html")
        return
    if not items:
        print("没有抓到任何新闻，不发送。")
        return
    send(f"🌍 全球新闻 {now_local:%m-%d} | {len(confirmed)}条多源确认", body)
    print("已发送。")


if __name__ == "__main__":
    main(sys.argv[1:])
