// refcap offscreen recorder - owns the MediaRecorder (service workers can't).
let recorder = null;
let chunks = [];
let stream = null;
let audioCtx = null;

chrome.runtime.onMessage.addListener(async (msg) => {
  if (!msg) return;

  if (msg.type === "refcap-start") {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: msg.streamId } },
        video: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: msg.streamId } }
      });
    } catch (e) {
      console.error("[refcap] getUserMedia failed", e);
      return;
    }
    // tabCapture mutes the tab for the user by default; pipe it back so you still hear it.
    audioCtx = new AudioContext();
    audioCtx.createMediaStreamSource(stream).connect(audioCtx.destination);

    chunks = [];
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
      ? "video/webm;codecs=vp9,opus"
      : "video/webm;codecs=vp8,opus";
    recorder = new MediaRecorder(stream, { mimeType: mime });
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    recorder.onstop = save;
    recorder.start();
  }

  if (msg.type === "refcap-stop") {
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }
});

function save() {
  const blob = new Blob(chunks, { type: "video/webm" });
  const url = URL.createObjectURL(blob);
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const a = document.createElement("a");
  a.href = url;
  a.download = `refcap-rec-${ts}.webm`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  if (audioCtx) { audioCtx.close(); audioCtx = null; }
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  chrome.runtime.sendMessage({ type: "refcap-saved" });
}
