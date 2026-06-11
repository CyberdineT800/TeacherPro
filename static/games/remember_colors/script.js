const colors = ["yashil", "qizil", "sariq", "moviy"];
let gamePattern = [];
let userPattern = [];
let level = 0;
let clickCount = 0;
let gameStarted = false;

window.addEventListener("load", function() {
  document.getElementById("start-btn").addEventListener("click", function() {
    if (!gameStarted) {
      gameStarted = true;
      this.textContent = "Qaytadan boshlash";
      startGame();
    } else {
      document.getElementById("custom-dialog").style.display = "none";
      startGame();
    }
  });

  document.getElementById("dialog-ok").addEventListener("click", function() {
    document.getElementById("custom-dialog").style.display = "none";
    startGame();
  });

  document.getElementById("custom-dialog").style.display = "none";
});

function showCustomDialog(message) {
  document.getElementById("dialog-message").textContent = message;
  document.getElementById("custom-dialog").style.display = "flex";
}

function startGame() {
  if (!gameStarted) {
    level = 0;
  }

  gamePattern = [];
  userPattern = [];
  clickCount = 0;

  document.getElementById("status").textContent = `${level}-bosqich`;
  document.getElementById("click-count").textContent = clickCount;

  showMyTexts();
  nextSequence();
}

function nextSequence() {
  userPattern = [];
  clickCount = 0;
  document.getElementById("click-count").textContent = clickCount;
  level++;
  document.getElementById("status").textContent = `${level}-bosqich`;

  document.getElementById("sequence-display").textContent = "-";

  const randomColor = colors[Math.floor(Math.random() * colors.length)];
  gamePattern.push(randomColor);

  animateSequence();
}

function animateSequence() {
  let i = 0;
  const interval = setInterval(() => {
    flashButton(gamePattern[i]);
    i++;
    if (i === gamePattern.length) {
      clearInterval(interval);
      enableUserInput();
    }
  }, 600);
}

function flashButton(color) {
  const button = document.getElementById(color);
  button.classList.add("active");
  setTimeout(() => {
    button.classList.remove("active");
  }, 300);
}

function enableUserInput() {
  colors.forEach((color) => {
    document.getElementById(color).removeEventListener("click", handleUserClick);
    document.getElementById(color).addEventListener("click", handleUserClick);
  });
}

function disableUserInput() {
  colors.forEach((color) => {
    document.getElementById(color).removeEventListener("click", handleUserClick);
  });
}

function handleUserClick(event) {
  const clickedColor = event.target.id;
  userPattern.push(clickedColor);
  flashButton(clickedColor);
  clickCount++;
  document.getElementById("click-count").textContent = clickCount;

  const sequenceDisplay = document.getElementById("sequence-display");
  sequenceDisplay.innerHTML = "";

  userPattern.forEach((color) => {
    const span = document.createElement("span");
    span.style.color = color == 'qizil' ? "red" : color == 'yashil' ? "green" : color == 'sariq' ? "rgb(218, 218, 3)" : "rgb(0, 183, 255)";
    span.textContent = color.toUpperCase() + " ";
    sequenceDisplay.appendChild(span);
  });

  checkAnswer(userPattern.length - 1);
}

function checkAnswer(currentLevel) {
  if (userPattern[currentLevel] === gamePattern[currentLevel]) {
    if (userPattern.length === gamePattern.length) {
      disableUserInput();
      setTimeout(() => {
        showCongratsMessage();
        setTimeout(() => {
          hideCongratsMessage();
          setTimeout(() => {
            nextSequence();
          }, 1000);
        }, 2000);
      }, 1000);
    }
  } else {
    disableUserInput();
    document.getElementById("status").textContent = `Yutqazdingiz!`;

    setTimeout(() => {
      flashButton(gamePattern[userPattern.length - 1]);
    }, 1000);
    setTimeout(() => {
      hideMyTexts();
    }, 1000);

    showLoseMessage();
    setTimeout(() => {
      hideLoseMessage();
      showCustomDialog(`Siz ${level}-bosqichga yetdingiz!`);
    }, 2000);

    gameStarted = false;

    setTimeout(() => {
      document.getElementById("sequence-display").textContent = "-";
      document.getElementById("click-count").textContent = 0;
    }, 1500);
  }
}

function showCongratsMessage() {
  const message = `Ofarin! Siz ${level}-bosqichdasiz!`;
  const congratsMessageElement = document.getElementById("level-message");
  congratsMessageElement.textContent = message;
  congratsMessageElement.style.display = "block";
  setTimeout(() => {
    congratsMessageElement.classList.add("show");
  }, 50);
}

function hideCongratsMessage() {
  const congratsMessageElement = document.getElementById("level-message");
  congratsMessageElement.classList.remove("show");
  setTimeout(() => {
    congratsMessageElement.style.display = "none";
  }, 1000);
}

function showLoseMessage() {
  const message = `Yutqazdingiz! To'g'ri ranglar: ${
    gamePattern[userPattern.length - 1]
  } edi.`;
  const loseMessageElement = document.getElementById("level-message");
  loseMessageElement.textContent = message;

  loseMessageElement.style.color = "red";
  loseMessageElement.style.display = "block";
  setTimeout(() => {
    loseMessageElement.classList.add("show");
  }, 10);
}

function hideLoseMessage() {
  const loseMessageElement = document.getElementById("level-message");
  loseMessageElement.classList.remove("show");
  setTimeout(() => {
    loseMessageElement.style.display = "none";
  }, 100);
}

function showMyTexts() {
  const texts = document.getElementsByClassName("my-text");

  for (let i = 0; i < texts.length; i++) {
    texts[i].style.display = "block";
    texts[i].classList.add("show");
  }
}

function hideMyTexts() {
  const texts = document.getElementsByClassName("my-text");

  for (let i = 0; i < texts.length; i++) {
    texts[i].classList.remove("show");
    texts[i].style.display = "none";
  }
}
