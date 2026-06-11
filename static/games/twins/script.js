const cards = document.querySelectorAll(".card");
const timerElement = document.querySelector(".timer");
const refreshBtn = document.querySelector(".refresh-btn");
const winDialog = document.getElementById("winDialog");
const completionTimeElement = document.getElementById("completionTime");
const playAgainBtn = document.getElementById("playAgainBtn");

let matched = 0;
let cardOne, cardTwo;
let disableDeck = false;
let timerInterval;
let seconds = 0;

function startTimer() {
    clearInterval(timerInterval);
    seconds = 0;
    timerElement.textContent = "Vaqt: 0s";

    timerInterval = setInterval(() => {
        seconds++;
        timerElement.textContent = `Vaqt: ${seconds}s`;
    }, 1000);
}

function showWinDialog() {
    completionTimeElement.textContent = seconds;
    winDialog.classList.add("show");
}

function hideWinDialog() {
    winDialog.classList.remove("show");
}

function flipCard({target: clickedCard}) {
    if(cardOne !== clickedCard && !disableDeck) {
        clickedCard.classList.add("flip");
        if(!cardOne) {
            return cardOne = clickedCard;
        }
        cardTwo = clickedCard;
        disableDeck = true;
        let cardOneImg = cardOne.querySelector(".back-view img").src,
        cardTwoImg = cardTwo.querySelector(".back-view img").src;
        matchCards(cardOneImg, cardTwoImg);
    }
}

function matchCards(img1, img2) {
    if(img1 === img2) {
        matched++;
        if(matched == 8) {
            clearInterval(timerInterval);
            setTimeout(() => {
                showWinDialog();
            }, 1000);
        }
        cardOne.removeEventListener("click", flipCard);
        cardTwo.removeEventListener("click", flipCard);
        cardOne = cardTwo = "";
        return disableDeck = false;
    }
    setTimeout(() => {
        cardOne.classList.add("shake");
        cardTwo.classList.add("shake");
    }, 400);

    setTimeout(() => {
        cardOne.classList.remove("shake", "flip");
        cardTwo.classList.remove("shake", "flip");
        cardOne = cardTwo = "";
        disableDeck = false;
    }, 1200);
}

function shuffleCard() {
    matched = 0;
    disableDeck = false;
    cardOne = cardTwo = "";
    let arr = [1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 6, 7, 8];
    arr.sort(() => Math.random() > 0.5 ? 1 : -1);
    cards.forEach((card, i) => {
        card.classList.remove("flip");
        let imgTag = card.querySelector(".back-view img");
        imgTag.src = `images/img-${arr[i]}.png`;
        card.addEventListener("click", flipCard);
    });

    hideWinDialog();

    startTimer();
}

shuffleCard();

cards.forEach(card => {
    card.addEventListener("click", flipCard);
});

refreshBtn.addEventListener("click", () => {
    shuffleCard();
});

playAgainBtn.addEventListener("click", () => {
    shuffleCard();
});
