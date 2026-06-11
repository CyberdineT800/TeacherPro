// Word-Match: match Uzbek words with their English translations.
// No emoji content — all pairs are text labels.

const allWordPairs = [
    { word: "Olma",       translation: "Apple" },
    { word: "Kitob",      translation: "Book" },
    { word: "Quyosh",     translation: "Sun" },
    { word: "Oy",         translation: "Moon" },
    { word: "Baliq",      translation: "Fish" },
    { word: "Mushuk",     translation: "Cat" },
    { word: "Gul",        translation: "Flower" },
    { word: "Telefon",    translation: "Phone" },
    { word: "Mashina",    translation: "Car" },
    { word: "Samolyot",   translation: "Airplane" },
    { word: "Soat",       translation: "Clock" },
    { word: "Shar",       translation: "Ball" },
    { word: "Sovg'a",     translation: "Gift" },
    { word: "Koptok",     translation: "Football" },
    { word: "Bo'ri",      translation: "Wolf" },
    { word: "Yo'lbars",   translation: "Tiger" },
    { word: "Zebra",      translation: "Zebra" },
    { word: "Sigir",      translation: "Cow" },
    { word: "Maymun",     translation: "Monkey" },
    { word: "Ot",         translation: "Horse" },
    { word: "Ayiq",       translation: "Bear" },
    { word: "Quyon",      translation: "Rabbit" },
    { word: "Sher",       translation: "Lion" },
    { word: "Qurbaqa",    translation: "Frog" },
    { word: "Tarvuz",     translation: "Watermelon" },
    { word: "Uzum",       translation: "Grapes" },
    { word: "Pomidor",    translation: "Tomato" },
    { word: "Sabzi",      translation: "Carrot" },
    { word: "Banan",      translation: "Banana" },
    { word: "Qalam",      translation: "Pencil" },
    { word: "Stol",       translation: "Table" },
    { word: "Stul",       translation: "Chair" },
    { word: "Uy",         translation: "House" },
    { word: "Daryo",      translation: "River" },
    { word: "Tog'",       translation: "Mountain" },
    { word: "Suv",        translation: "Water" },
    { word: "Non",        translation: "Bread" },
    { word: "Sut",        translation: "Milk" },
    { word: "Kino",       translation: "Movie" },
    { word: "Maktab",     translation: "School" },
    { word: "O'qituvchi", translation: "Teacher" },
    { word: "O'quvchi",   translation: "Student" },
    { word: "Daftar",     translation: "Notebook" },
    { word: "Ruchka",     translation: "Pen" },
    { word: "Ko'z",       translation: "Eye" },
    { word: "Qo'l",       translation: "Hand" },
    { word: "Oyoq",       translation: "Leg" },
    { word: "Bosh",       translation: "Head" },
];

const wordsColumn   = document.getElementById('words-column');
const emojisColumn  = document.getElementById('emojis-column');
const canvas        = document.getElementById('connection-canvas');
const retryButton   = document.getElementById('retry-button');
const errorDialog   = document.getElementById('error-dialog');
const dialogClose   = document.getElementById('dialog-close');
const winDialog     = document.getElementById('win-dialog');
const winDialogClose = document.getElementById('win-dialog-close');

canvas.width  = window.innerWidth;
canvas.height = window.innerHeight;
const ctx = canvas.getContext('2d');

let selectedCell   = null;
let matchedPairs   = [];
let currentLines   = [];
let currentGamePairs = [];
const totalPairs   = 6;

function initGame() {
    wordsColumn.innerHTML  = '';
    emojisColumn.innerHTML = '';

    selectedCell   = null;
    matchedPairs   = [];
    currentLines   = [];

    const shuffledAll = [...allWordPairs].sort(() => Math.random() - 0.5);
    currentGamePairs  = shuffledAll.slice(0, totalPairs);

    const shuffledWords       = [...currentGamePairs].sort(() => Math.random() - 0.5);
    const shuffledTranslations = [...currentGamePairs].sort(() => Math.random() - 0.5);

    shuffledWords.forEach(pair => {
        const cell = document.createElement('div');
        cell.className      = 'cell word-cell';
        cell.textContent    = pair.word;
        cell.dataset.word   = pair.word;
        wordsColumn.appendChild(cell);
        cell.addEventListener('click', () => handleCellClick(cell, 'word'));
    });

    shuffledTranslations.forEach(pair => {
        const cell = document.createElement('div');
        cell.className           = 'cell emoji-cell';
        cell.textContent         = pair.translation;
        cell.dataset.emoji       = pair.translation; // reuse dataset key for compat
        cell.dataset.word        = pair.word;
        emojisColumn.appendChild(cell);
        cell.addEventListener('click', () => handleCellClick(cell, 'emoji'));
    });

    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function handleCellClick(cell, type) {
    if (matchedPairs.some(pair =>
        (type === 'word'  && pair.wordCell  === cell) ||
        (type === 'emoji' && pair.emojiCell === cell))) {
        return;
    }

    if (!selectedCell) {
        selectedCell = { cell, type };
        cell.classList.add('selected');
        return;
    }

    if (selectedCell.cell === cell) {
        cell.classList.remove('selected');
        selectedCell = null;
        return;
    }

    if (selectedCell.type === type) {
        selectedCell.cell.classList.remove('selected');
        cell.classList.add('selected');
        selectedCell = { cell, type };
        return;
    }

    const wordCell  = type === 'word'  ? cell : selectedCell.cell;
    const emojiCell = type === 'emoji' ? cell : selectedCell.cell;

    if (wordCell.dataset.word === emojiCell.dataset.word) {
        matchedPairs.push({ wordCell, emojiCell });

        wordCell.classList.remove('selected');
        emojiCell.classList.remove('selected');
        wordCell.classList.add('matched');
        emojiCell.classList.add('matched');

        drawConnection(wordCell, emojiCell, true);

        if (matchedPairs.length === totalPairs) {
            setTimeout(() => {
                winDialog.style.display = 'block';
            }, 500);
        }
    } else {
        wordCell.classList.remove('selected');
        emojiCell.classList.remove('selected');
        errorDialog.style.display = 'block';
    }

    selectedCell = null;
}

function drawConnection(wordCell, emojiCell, isPermanent) {
    const wordRect  = wordCell.getBoundingClientRect();
    const emojiRect = emojiCell.getBoundingClientRect();

    const startX = wordRect.right;
    const startY = wordRect.top  + wordRect.height  / 2;
    const endX   = emojiRect.left;
    const endY   = emojiRect.top + emojiRect.height / 2;

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX,   endY);
    ctx.strokeStyle = isPermanent ? '#27ae60' : '#3498db';
    ctx.lineWidth   = 2;
    ctx.stroke();

    if (isPermanent) {
        currentLines.push({ startX, startY, endX, endY, color: '#27ae60' });
    }
}

function redrawLines() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    currentLines.forEach(line => {
        ctx.beginPath();
        ctx.moveTo(line.startX, line.startY);
        ctx.lineTo(line.endX,   line.endY);
        ctx.strokeStyle = line.color;
        ctx.lineWidth   = 2;
        ctx.stroke();
    });
}

dialogClose.addEventListener('click',    () => { errorDialog.style.display = 'none'; });
winDialogClose.addEventListener('click', () => { winDialog.style.display   = 'none'; });
retryButton.addEventListener('click',    () => { initGame(); });

window.addEventListener('resize', () => {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    currentLines  = [];
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    matchedPairs.forEach(pair => drawConnection(pair.wordCell, pair.emojiCell, true));
});

initGame();
