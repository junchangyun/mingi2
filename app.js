const WORDS = {
  HSK1: [
    { hanzi: '你好', pinyin: 'nihao', meaning: '안녕하세요', example: '你好！很高兴认识你。' },
    { hanzi: '谢谢', pinyin: 'xiexie', meaning: '감사합니다', example: '谢谢你的帮助。' },
    { hanzi: '老师', pinyin: 'laoshi', meaning: '선생님', example: '老师今天很忙。' },
    { hanzi: '朋友', pinyin: 'pengyou', meaning: '친구', example: '他是我的朋友。' },
    { hanzi: '今天', pinyin: 'jintian', meaning: '오늘', example: '今天天气很好。' },
    { hanzi: '学习', pinyin: 'xuexi', meaning: '공부하다', example: '我每天学习中文。' },
  ],
  HSK2: [
    { hanzi: '准备', pinyin: 'zhunbei', meaning: '준비하다', example: '我在准备考试。' },
    { hanzi: '练习', pinyin: 'lianxi', meaning: '연습하다', example: '每天练习听力。' },
    { hanzi: '方便', pinyin: 'fangbian', meaning: '편리하다', example: '坐地铁很方便。' },
    { hanzi: '明白', pinyin: 'mingbai', meaning: '이해하다', example: '我明白你的意思。' },
    { hanzi: '需要', pinyin: 'xuyao', meaning: '필요하다', example: '我需要一本词典。' },
    { hanzi: '一起', pinyin: 'yiqi', meaning: '함께', example: '我们一起去图书馆吧。' },
  ],
};

const levelSelect = document.getElementById('level-select');
const nextCardBtn = document.getElementById('next-card');
const cardMessage = document.getElementById('card-message');
const cardHanzi = document.getElementById('card-hanzi');
const cardPinyin = document.getElementById('card-pinyin');
const cardMeaning = document.getElementById('card-meaning');
const cardExample = document.getElementById('card-example');
const speakBtn = document.getElementById('speak-btn');

const quizQuestion = document.getElementById('quiz-question');
const quizChoices = document.getElementById('quiz-choices');
const quizFeedback = document.getElementById('quiz-feedback');
const newQuizBtn = document.getElementById('new-quiz');

const pinyinTarget = document.getElementById('pinyin-target');
const pinyinForm = document.getElementById('pinyin-form');
const pinyinInput = document.getElementById('pinyin-input');
const pinyinFeedback = document.getElementById('pinyin-feedback');

let currentWord = null;
let currentQuiz = null;
let currentPinyin = null;

function pickRandom(words) {
  return words[Math.floor(Math.random() * words.length)];
}

function getCurrentWords() {
  const level = levelSelect ? levelSelect.value : 'HSK1';
  return WORDS[level] || WORDS.HSK1;
}

function updateCard(word) {
  currentWord = word;
  if (cardHanzi) cardHanzi.textContent = word.hanzi;
  if (cardPinyin) cardPinyin.textContent = word.pinyin;
  if (cardMeaning) cardMeaning.textContent = word.meaning;
  if (cardExample) cardExample.textContent = word.example;
  if (cardMessage) cardMessage.textContent = `${levelSelect.value} 단어 카드`;
}

function nextCard() {
  const words = getCurrentWords();
  updateCard(pickRandom(words));
}

function shuffled(array) {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function makeQuiz() {
  const words = getCurrentWords();
  const answer = pickRandom(words);
  const distractors = shuffled(words.filter((word) => word.hanzi !== answer.hanzi))
    .slice(0, 3)
    .map((word) => word.meaning);
  const choices = shuffled([answer.meaning, ...distractors]);

  currentQuiz = { answer: answer.meaning, hanzi: answer.hanzi, choices };
  if (quizQuestion) quizQuestion.textContent = `다음 한자의 뜻은? ${answer.hanzi}`;
  if (quizFeedback) quizFeedback.textContent = '';
  renderQuizChoices();
}

function renderQuizChoices() {
  if (!quizChoices || !currentQuiz) return;

  quizChoices.innerHTML = currentQuiz.choices
    .map((choice) => `<button class="choice-btn" type="button" data-choice="${choice}">${choice}</button>`)
    .join('');
}

function makePinyinQuestion() {
  const words = getCurrentWords();
  const word = pickRandom(words);
  currentPinyin = word;
  if (pinyinTarget) pinyinTarget.textContent = word.hanzi;
  if (pinyinFeedback) pinyinFeedback.textContent = '';
  if (pinyinInput) pinyinInput.value = '';
}

if (nextCardBtn) {
  nextCardBtn.addEventListener('click', nextCard);
}

if (levelSelect) {
  levelSelect.addEventListener('change', () => {
    nextCard();
    makeQuiz();
    makePinyinQuestion();
  });
}

if (speakBtn) {
  speakBtn.addEventListener('click', () => {
    if (!currentWord || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(currentWord.hanzi);
    utterance.lang = 'zh-CN';
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

if (quizChoices) {
  quizChoices.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const choice = target.dataset.choice;
    if (!choice || !currentQuiz) return;

    const isCorrect = choice === currentQuiz.answer;
    target.classList.add(isCorrect ? 'correct' : 'wrong');
    if (quizFeedback) {
      quizFeedback.textContent = isCorrect
        ? '정답입니다.'
        : `오답입니다. 정답: ${currentQuiz.answer}`;
    }
  });
}

if (newQuizBtn) {
  newQuizBtn.addEventListener('click', makeQuiz);
}

if (pinyinForm) {
  pinyinForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!currentPinyin || !pinyinInput || !pinyinFeedback) return;

    const typed = pinyinInput.value.trim().toLowerCase();
    const answer = currentPinyin.pinyin.toLowerCase();
    if (!typed) {
      pinyinFeedback.textContent = '병음을 입력하세요.';
      return;
    }

    if (typed === answer) {
      pinyinFeedback.textContent = '정답입니다. 다음 문제로 넘어갑니다.';
      makePinyinQuestion();
      return;
    }

    pinyinFeedback.textContent = `오답입니다. 정답은 ${answer}`;
  });
}

nextCard();
makeQuiz();
makePinyinQuestion();
