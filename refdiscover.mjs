// refdiscover - rigorous reference selection on YouTube by niche.
// Ranks by VELOCITY (views/day) within a RECENCY window - not absolute views (which favors old/big-channel virals).
// Returns top-5 with velocity + age + engagement, so "what's working NOW in this niche" surfaces.
// TikTok/IG discovery is GATED (no API) - harvest those via claude-in-chrome (TIKTOK_CAPTURE.md).
// Usage: YOUTUBE_API_KEY=... node refdiscover.mjs "<niche>" [minSec=10] [maxSec=120] [windowDays=90]
const key = process.env.YOUTUBE_API_KEY ?? "";
if (key === "") { console.log(JSON.stringify({ error: "no YOUTUBE_API_KEY" })); process.exit(0); }
function durSec(iso) { const m = /PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/.exec(iso || ""); return m ? Number(m[1] || 0) * 3600 + Number(m[2] || 0) * 60 + Number(m[3] || 0) : 0; }
const q = encodeURIComponent(process.argv[2] || "꿀팁");
const minD = Number(process.argv[3] || 10), maxD = Number(process.argv[4] || 120), windowDays = Number(process.argv[5] || 90);
const publishedAfter = new Date(Date.now() - windowDays * 86400000).toISOString();
const surl = `https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&videoDuration=short&order=viewCount&regionCode=KR&relevanceLanguage=ko&maxResults=50&publishedAfter=${encodeURIComponent(publishedAfter)}&q=${q}&key=${key}`;
const sr = await fetch(surl);
if (!sr.ok) { console.log(JSON.stringify({ error: "search HTTP " + sr.status })); process.exit(0); }
const sj = JSON.parse(await sr.text());
const ids = (sj.items || []).map((it) => it.id && it.id.videoId).filter(Boolean);
const vr = await fetch(`https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id=${ids.join(",")}&key=${key}`);
const vj = JSON.parse(await vr.text());
const now = Date.now();
const items = (vj.items || []).map((it) => {
  const dur = durSec((it.contentDetails || {}).duration);
  const views = Number((it.statistics || {}).viewCount || 0);
  const likes = Number((it.statistics || {}).likeCount || 0);
  const comments = Number((it.statistics || {}).commentCount || 0);
  const ageDays = Math.max(0.5, (now - new Date((it.snippet || {}).publishedAt).getTime()) / 86400000);
  return {
    id: it.id, watch: "https://www.youtube.com/watch?v=" + it.id, title: (it.snippet || {}).title, channel: (it.snippet || {}).channelTitle,
    dur, views, ageDays: Math.round(ageDays), velocityPerDay: Math.round(views / ageDays),
    likes, comments, engPct: views ? Math.round(((likes + comments) / views) * 10000) / 100 : 0
  };
});
const picks = items.filter((x) => x.dur >= minD && x.dur <= maxD && !/Topic$/.test(x.channel || "")).sort((a, b) => b.velocityPerDay - a.velocityPerDay).slice(0, 5);
console.log(JSON.stringify({ niche: process.argv[2], windowDays, ranked_by: "velocityPerDay", picks }, null, 2));
