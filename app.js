const startBtn = document.getElementById('startBtn');
const captureBtn = document.getElementById('captureBtn');
const stopBtn = document.getElementById('stopBtn');
const fileInput = document.getElementById('fileInput');
const video = document.getElementById('previewVideo');
const canvas = document.getElementById('captureCanvas');
const message = document.getElementById('message');
const labelContainer = document.getElementById('label-container');
const topResult = document.getElementById('top-result');
const historyList = document.getElementById('history-list');

const MODEL_URL = 'https://teachablemachine.withgoogle.com/models/ANAssuJl9/';

let stream = null;
let model = null;
let maxPredictions = 0;

function setMessage(text) {
  if (message) message.textContent = text;
}

function enableCaptureControls(enabled) {
  if (captureBtn) captureBtn.disabled = !enabled;
  if (stopBtn) stopBtn.disabled = !enabled;
}

function stopShare() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  if (video) video.srcObject = null;
  enableCaptureControls(false);
}

async function initModel() {
  if (model) return;

  setMessage('분류 모델을 불러오는 중입니다.');
  const modelURL = `${MODEL_URL}model.json`;
  const metadataURL = `${MODEL_URL}metadata.json`;
  model = await tmImage.load(modelURL, metadataURL);
  maxPredictions = model.getTotalClasses();

  if (labelContainer) {
    labelContainer.innerHTML = '';
    for (let i = 0; i < maxPredictions; i += 1) {
      labelContainer.appendChild(document.createElement('div'));
    }
  }

  setMessage('준비 완료. 사진 업로드 또는 화면 공유를 사용하세요.');
}

async function predictFromCanvas() {
  if (!model) {
    await initModel();
  }

  const prediction = await model.predict(canvas);
  prediction.sort((a, b) => b.probability - a.probability);

  const best = prediction[0];
  if (topResult) {
    topResult.textContent = `가장 유력: ${best.className} (${(best.probability * 100).toFixed(1)}%)`;
  }

  if (labelContainer) {
    for (let i = 0; i < maxPredictions; i += 1) {
      const item = prediction[i];
      labelContainer.childNodes[i].textContent = `${item.className}: ${(item.probability * 100).toFixed(1)}%`;
    }
  }

  return best;
}

function formatCaptureTime() {
  return new Date().toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function addHistoryItem(best) {
  if (!historyList) return;

  const item = document.createElement('article');
  item.className = 'history-item';

  const img = document.createElement('img');
  img.className = 'history-image';
  img.src = canvas.toDataURL('image/png');
  img.alt = '분류에 사용된 이미지';

  const info = document.createElement('div');

  const time = document.createElement('p');
  time.className = 'history-time';
  time.textContent = formatCaptureTime();

  const result = document.createElement('p');
  result.className = 'history-result';
  result.textContent = `${best.className} (${(best.probability * 100).toFixed(1)}%)`;

  info.appendChild(time);
  info.appendChild(result);
  item.appendChild(img);
  item.appendChild(info);

  historyList.prepend(item);
}

function drawImageToCanvas(imgEl) {
  const w = imgEl.naturalWidth || imgEl.width;
  const h = imgEl.naturalHeight || imgEl.height;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(imgEl, 0, 0, w, h);
}

async function predictCurrentCanvas() {
  try {
    const best = await predictFromCanvas();
    addHistoryItem(best);
    setMessage('분류가 완료되었습니다.');
  } catch (error) {
    setMessage('분류 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
  }
}

if (startBtn) {
  startBtn.addEventListener('click', async () => {
    try {
      await initModel();
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });
      video.srcObject = stream;
      enableCaptureControls(true);
      setMessage('화면 공유 중입니다. 캡처 후 분류를 눌러 주세요.');

      const [track] = stream.getVideoTracks();
      track.addEventListener('ended', () => {
        stopShare();
        setMessage('화면 공유가 종료되었습니다.');
      });
    } catch (error) {
      setMessage('권한이 거부되었거나 화면 공유를 시작할 수 없습니다.');
    }
  });
}

if (captureBtn) {
  captureBtn.addEventListener('click', async () => {
    if (!stream) return;

    const { videoWidth, videoHeight } = video;
    if (!videoWidth || !videoHeight) {
      setMessage('화면이 아직 준비되지 않았습니다.');
      return;
    }

    canvas.width = videoWidth;
    canvas.height = videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, videoWidth, videoHeight);
    await predictCurrentCanvas();
  });
}

if (stopBtn) {
  stopBtn.addEventListener('click', () => {
    stopShare();
    setMessage('화면 공유를 중지했습니다.');
  });
}

if (fileInput) {
  fileInput.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    try {
      await initModel();
      const img = new Image();
      img.onload = async () => {
        drawImageToCanvas(img);
        await predictCurrentCanvas();
      };
      img.onerror = () => {
        setMessage('이미지를 불러오지 못했습니다. 다른 파일을 선택해 주세요.');
      };
      img.src = URL.createObjectURL(file);
    } catch (error) {
      setMessage('모델 초기화에 실패했습니다. 페이지를 새로고침해 주세요.');
    }
  });
}

initModel().catch(() => {
  setMessage('모델을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
});
