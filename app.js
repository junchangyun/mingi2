const startBtn = document.getElementById('startBtn');
const captureBtn = document.getElementById('captureBtn');
const stopBtn = document.getElementById('stopBtn');
const video = document.getElementById('previewVideo');
const canvas = document.getElementById('captureCanvas');
const message = document.getElementById('message');

let stream = null;

function setMessage(text) {
  message.textContent = text;
}

function enableCaptureControls(enabled) {
  captureBtn.disabled = !enabled;
  stopBtn.disabled = !enabled;
}

function stopShare() {
  if (stream) {
    // Stop all tracks to end the screen share.
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  video.srcObject = null;
  enableCaptureControls(false);
  setMessage('화면 공유가 중지되었습니다.');
}

startBtn.addEventListener('click', async () => {
  try {
    // Request full screen capture from the user.
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    });

    video.srcObject = stream;
    enableCaptureControls(true);
    setMessage('화면 공유가 시작되었습니다. 캡쳐를 눌러 저장하세요.');

    // If the user stops sharing from browser UI, update the UI.
    const [track] = stream.getVideoTracks();
    track.addEventListener('ended', () => {
      stopShare();
    });
  } catch (err) {
    // Handle permission denial or user cancellation.
    setMessage('화면 공유가 취소되었거나 권한이 거부되었습니다.');
  }
});

captureBtn.addEventListener('click', async () => {
  if (!stream) return;

  const { videoWidth, videoHeight } = video;
  if (!videoWidth || !videoHeight) {
    setMessage('영상이 준비되지 않았습니다. 잠시 후 다시 시도하세요.');
    return;
  }

  // Draw the current video frame to the canvas.
  canvas.width = videoWidth;
  canvas.height = videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, videoWidth, videoHeight);

  // Convert canvas to PNG and download.
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screenshot_${timestamp()}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, 'image/png');
});

stopBtn.addEventListener('click', () => {
  stopShare();
});

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  const ss = pad(d.getSeconds());
  return `${yyyy}${mm}${dd}_${hh}${mi}${ss}`;
}
