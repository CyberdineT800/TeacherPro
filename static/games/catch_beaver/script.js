const holes = document.querySelectorAll(".hole");
const scoreBoard = document.querySelector(".score");
const moles = document.querySelectorAll(".mole");
const button = document.querySelector("#start");
const timerDisplay = document.querySelector(".time-left");

let lastHole;
let timeUp = false;
let score = 0;
let countdown;
let timeLeft = 60;

function randomTime(min, max) {
  return Math.round(Math.random() * (max - min) + min);
}

function randomHole(holes) {
  const idx = Math.floor(Math.random() * holes.length);
  const hole = holes[idx];

  if (hole === lastHole) {
    return randomHole(holes);
  }

  lastHole = hole;
  return hole;
}

function peep() {
  const time = randomTime(200, 1000);
  const hole = randomHole(holes);
  hole.classList.add("up");

  setTimeout(() => {
    hole.classList.remove("up");
    if (!timeUp) peep();
  }, time);
}

function startTimer() {
  timeLeft = 60;
  timerDisplay.textContent = timeLeft;

  countdown = setInterval(() => {
    timeLeft--;
    timerDisplay.textContent = timeLeft;

    if (timeLeft <= 0) {
      clearInterval(countdown);
      timeUp = true;
      button.innerHTML = "Qaytadan boshlash!";
      button.style.visibility = "visible";
    }
  }, 1000);
}

function startGame() {
  scoreBoard.textContent = 0;
  timeUp = false;
  score = 0;
  button.style.visibility = "hidden";

  clearInterval(countdown);

  startTimer();

  peep();
}

function bonk(e) {
  if (!e.isTrusted) return;
  score++;
  this.classList.remove("up");
  scoreBoard.textContent = score;
}

function bonkTouch(e) {
  e.preventDefault();
  score++;
  this.classList.remove("up");
  scoreBoard.textContent = score;
}

moles.forEach((mole) => {
  mole.addEventListener("click", bonk);
  mole.addEventListener("touchstart", bonkTouch, { passive: false });
});
