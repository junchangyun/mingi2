const numbersContainer = document.querySelector('.numbers');
const generateBtn = document.querySelector('#generate');

const generateNumbers = () => {
    const numbers = new Set();
    while (numbers.size < 6) {
        numbers.add(Math.floor(Math.random() * 45) + 1);
    }
    return [...numbers];
};

const displayNumbers = (numbers) => {
    numbersContainer.innerHTML = '';
    numbers.forEach(number => {
        const numberEl = document.createElement('div');
        numberEl.classList.add('number');
        numberEl.textContent = number;
        numbersContainer.appendChild(numberEl);
    });
};

generateBtn.addEventListener('click', () => {
    const numbers = generateNumbers();
    displayNumbers(numbers);
});
