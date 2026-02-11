const startBtn = document.getElementById('startBtn');
const captureBtn = document.getElementById('captureBtn');
const stopBtn = document.getElementById('stopBtn');
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
  message.textContent = text;
}

function enableCaptureControls(enabled) {
  captureBtn.disabled = !enabled;
  stopBtn.disabled = !enabled;
}

function stopShare() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  video.srcObject = null;
  enableCaptureControls(false);
  setMessage('화면 공유가 중지되었습니다.');
}

async function initModel() {
  if (model) return;

  const modelURL = `${MODEL_URL}model.json`;
  const metadataURL = `${MODEL_URL}metadata.json`;
  model = await tmImage.load(modelURL, metadataURL);
  maxPredictions = model.getTotalClasses();

  labelContainer.innerHTML = '';
  for (let i = 0; i < maxPredictions; i += 1) {
    labelContainer.appendChild(document.createElement('div'));
  }
}

async function predictFromCanvas() {
  if (!model) {
    await initModel();
  }

  const prediction = await model.predict(canvas);
  prediction.sort((a, b) => b.probability - a.probability);

  const best = prediction[0];
  topResult.textContent = `가장 유력: ${best.className} (${(best.probability * 100).toFixed(1)}%)`;

  for (let i = 0; i < maxPredictions; i += 1) {
    const item = prediction[i];
    labelContainer.childNodes[i].textContent = `${item.className}: ${(item.probability * 100).toFixed(1)}%`;
  }

  return { best, prediction };
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
  const item = document.createElement('article');
  item.className = 'history-item';

  const img = document.createElement('img');
  img.className = 'history-image';
  img.src = canvas.toDataURL('image/png');
  img.alt = '캡처 이미지';

  const info = document.createElement('div');
  info.className = 'history-info';

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

startBtn.addEventListener('click', async () => {
  try {
    await initModel();

    stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    });

    video.srcObject = stream;
    enableCaptureControls(true);
    setMessage('화면 공유가 시작되었습니다. 캡쳐 및 분류 버튼을 눌러 결과를 확인하세요.');

    const [track] = stream.getVideoTracks();
    track.addEventListener('ended', () => {
      stopShare();
    });
  } catch (err) {
    setMessage('모델 로드 실패 또는 화면 공유 권한이 거부되었습니다.');
  }
});

captureBtn.addEventListener('click', async () => {
  if (!stream) return;

  const { videoWidth, videoHeight } = video;
  if (!videoWidth || !videoHeight) {
    setMessage('영상이 준비되지 않았습니다. 잠시 후 다시 시도하세요.');
    return;
  }

  canvas.width = videoWidth;
  canvas.height = videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, videoWidth, videoHeight);
  try {
    const { best } = await predictFromCanvas();
    addHistoryItem(best);
    setMessage('캡처 이미지 분류가 완료되었습니다.');
  } catch (err) {
    setMessage('이미지 분류에 실패했습니다.');
  }
});

stopBtn.addEventListener('click', () => {
  stopShare();
});
