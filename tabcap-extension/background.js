// refcap tab recorder - background service worker.
// Toggle: click the extension icon to start, click again to stop.
// Flow: getMediaStreamId(current tab) -> offscreen document does MediaRecorder -> downloads .webm.
let recording = false;

chrome.action.onClicked.addListener(async (tab) => {
  if (recording) {
    chrome.runtime.sendMessage({ type: "refcap-stop" });
    setRecording(false);
    return;
  }
  if (!tab || tab.id == null) return;
  try {
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
    await ensureOffscreen();
    // small delay so the offscreen listener is registered before we send.
    chrome.runtime.sendMessage({ type: "refcap-start", streamId });
    setRecording(true);
  } catch (e) {
    chrome.action.setBadgeText({ text: "ERR" });
    chrome.action.setBadgeBackgroundColor({ color: "#d00" });
    console.error("[refcap]", e);
  }
});

// offscreen tells us when the file has been handed to the browser's downloader.
chrome.runtime.onMessage.addListener((msg) => {
  if (msg && msg.type === "refcap-saved") setRecording(false);
});

function setRecording(on) {
  recording = on;
  chrome.action.setBadgeText({ text: on ? "REC" : "" });
  if (on) chrome.action.setBadgeBackgroundColor({ color: "#d00" });
}

async function ensureOffscreen() {
  const has = await chrome.offscreen.hasDocument();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Record the active tab's audio+video locally for personal reference analysis."
  });
}
