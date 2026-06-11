document.addEventListener("DOMContentLoaded", () => {
  const gridDisplay = document.querySelector(".grid");
  const scoreDisplay = document.getElementById("score");
  const resultDisplay = document.getElementById("result");
  const upButton = document.getElementById("up-button");
  const leftButton = document.getElementById("left-button");
  const rightButton = document.getElementById("right-button");
  const downButton = document.getElementById("down-button");
  const refreshButton = document.getElementById("refresh-button");

  let squares = [];
  const width = 4;
  let score = 0;

  function createBoard() {
    for (let i = 0; i < width * width; i++) {
      square = document.createElement("div");
      square.innerHTML = 0;
      gridDisplay.appendChild(square);
      squares.push(square);
    }
    generate();
    generate();
  }
  createBoard();

  function generate() {
    randomNumber = Math.floor(Math.random() * squares.length);
    if (squares[randomNumber].innerHTML == 0) {
      squares[randomNumber].innerHTML = 2;
      checkForGameOver();
    } else generate();
  }

  function moveRight() {
    for (let i = 0; i < 16; i++) {
      if (i % 4 === 0) {
        let totalOne = squares[i].innerHTML;
        let totalTwo = squares[i + 1].innerHTML;
        let totalThree = squares[i + 2].innerHTML;
        let totalFour = squares[i + 3].innerHTML;
        let row = [
          parseInt(totalOne),
          parseInt(totalTwo),
          parseInt(totalThree),
          parseInt(totalFour),
        ];

        let filteredRow = row.filter((num) => num);
        let missing = 4 - filteredRow.length;
        let zeros = Array(missing).fill(0);
        let newRow = zeros.concat(filteredRow);

        squares[i].innerHTML = newRow[0];
        squares[i + 1].innerHTML = newRow[1];
        squares[i + 2].innerHTML = newRow[2];
        squares[i + 3].innerHTML = newRow[3];
      }
    }
  }

  function moveLeft() {
    for (let i = 0; i < 16; i++) {
      if (i % 4 === 0) {
        let totalOne = squares[i].innerHTML;
        let totalTwo = squares[i + 1].innerHTML;
        let totalThree = squares[i + 2].innerHTML;
        let totalFour = squares[i + 3].innerHTML;
        let row = [
          parseInt(totalOne),
          parseInt(totalTwo),
          parseInt(totalThree),
          parseInt(totalFour),
        ];

        let filteredRow = row.filter((num) => num);
        let missing = 4 - filteredRow.length;
        let zeros = Array(missing).fill(0);
        let newRow = filteredRow.concat(zeros);

        squares[i].innerHTML = newRow[0];
        squares[i + 1].innerHTML = newRow[1];
        squares[i + 2].innerHTML = newRow[2];
        squares[i + 3].innerHTML = newRow[3];
      }
    }
  }

  function moveUp() {
    for (let i = 0; i < 4; i++) {
      let totalOne = squares[i].innerHTML;
      let totalTwo = squares[i + width].innerHTML;
      let totalThree = squares[i + width * 2].innerHTML;
      let totalFour = squares[i + width * 3].innerHTML;
      let column = [
        parseInt(totalOne),
        parseInt(totalTwo),
        parseInt(totalThree),
        parseInt(totalFour),
      ];

      let filteredColumn = column.filter((num) => num);
      let missing = 4 - filteredColumn.length;
      let zeros = Array(missing).fill(0);
      let newColumn = filteredColumn.concat(zeros);

      squares[i].innerHTML = newColumn[0];
      squares[i + width].innerHTML = newColumn[1];
      squares[i + width * 2].innerHTML = newColumn[2];
      squares[i + width * 3].innerHTML = newColumn[3];
    }
  }

  function moveDown() {
    for (let i = 0; i < 4; i++) {
      let totalOne = squares[i].innerHTML;
      let totalTwo = squares[i + width].innerHTML;
      let totalThree = squares[i + width * 2].innerHTML;
      let totalFour = squares[i + width * 3].innerHTML;
      let column = [
        parseInt(totalOne),
        parseInt(totalTwo),
        parseInt(totalThree),
        parseInt(totalFour),
      ];

      let filteredColumn = column.filter((num) => num);
      let missing = 4 - filteredColumn.length;
      let zeros = Array(missing).fill(0);
      let newColumn = zeros.concat(filteredColumn);

      squares[i].innerHTML = newColumn[0];
      squares[i + width].innerHTML = newColumn[1];
      squares[i + width * 2].innerHTML = newColumn[2];
      squares[i + width * 3].innerHTML = newColumn[3];
    }
  }

  function combineRow() {
    for (let i = 0; i < 15; i++) {
      if ((i + 1) % 4 === 0) continue; // skip row boundaries (3→4, 7→8, 11→12)
      if (squares[i].innerHTML === squares[i + 1].innerHTML &&
          squares[i].innerHTML !== "0") {
        let combinedTotal =
          parseInt(squares[i].innerHTML) + parseInt(squares[i + 1].innerHTML);
        squares[i].innerHTML = combinedTotal;
        squares[i + 1].innerHTML = 0;
        score += combinedTotal;
        scoreDisplay.innerHTML = score;
      }
    }
    checkForWin();
  }

  function combineRowRight() {
    for (let i = 14; i >= 0; i--) {
      if (i % 4 === 0) continue; // skip row boundaries (3←4, 7←8, 11←12): skip when i is leftmost
      if (squares[i].innerHTML === squares[i - 1].innerHTML &&
          squares[i].innerHTML !== "0") {
        let combinedTotal =
          parseInt(squares[i].innerHTML) + parseInt(squares[i - 1].innerHTML);
        squares[i].innerHTML = combinedTotal;
        squares[i - 1].innerHTML = 0;
        score += combinedTotal;
        scoreDisplay.innerHTML = score;
      }
    }
    checkForWin();
  }

  function combineColumn() {
    for (let i = 0; i < 12; i++) {
      if (squares[i].innerHTML === squares[i + width].innerHTML &&
          squares[i].innerHTML !== "0") {
        let combinedTotal =
          parseInt(squares[i].innerHTML) +
          parseInt(squares[i + width].innerHTML);
        squares[i].innerHTML = combinedTotal;
        squares[i + width].innerHTML = 0;
        score += combinedTotal;
        scoreDisplay.innerHTML = score;
      }
    }
    checkForWin();
  }

  function combineColumnDown() {
    for (let i = 15; i >= 4; i--) {
      if (squares[i].innerHTML === squares[i - width].innerHTML &&
          squares[i].innerHTML !== "0") {
        let combinedTotal =
          parseInt(squares[i].innerHTML) +
          parseInt(squares[i - width].innerHTML);
        squares[i].innerHTML = combinedTotal;
        squares[i - width].innerHTML = 0;
        score += combinedTotal;
        scoreDisplay.innerHTML = score;
      }
    }
    checkForWin();
  }

  function control(e) {
    if (e.keyCode === 37) {
      keyLeft();
    } else if (e.keyCode === 38) {
      keyUp();
    } else if (e.keyCode === 39) {
      keyRight();
    } else if (e.keyCode === 40) {
      keyDown();
    }
  }
  document.addEventListener("keyup", control);

  upButton.addEventListener("click", keyUp);
  leftButton.addEventListener("click", keyLeft);
  rightButton.addEventListener("click", keyRight);
  downButton.addEventListener("click", keyDown);

  refreshButton.addEventListener("click", () => {
    squares.forEach(square => {
      square.innerHTML = 0;
    });
    score = 0;
    scoreDisplay.innerHTML = score;
    resultDisplay.innerHTML = "Raqamlarni birlashtirish orqali <b>2048</b> hosil qiling!";

    location.reload();
  });

  let touchStartX = 0;
  let touchStartY = 0;
  let touchEndX = 0;
  let touchEndY = 0;

  gridDisplay.addEventListener("touchstart", function(e) {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  }, false);

  gridDisplay.addEventListener("touchend", function(e) {
    touchEndX = e.changedTouches[0].screenX;
    touchEndY = e.changedTouches[0].screenY;
    handleSwipe();
  }, false);

  function handleSwipe() {
    const xDiff = touchStartX - touchEndX;
    const yDiff = touchStartY - touchEndY;

    if (Math.abs(xDiff) > Math.abs(yDiff)) {
      if (xDiff > 10) keyLeft();
      else if (xDiff < -10) keyRight();
    } else {
      if (yDiff > 10) keyUp();
      else if (yDiff < -10) keyDown();
    }
  }

  function keyRight() {
    moveRight();
    combineRowRight();
    moveRight();
    generate();
  }

  function keyLeft() {
    moveLeft();
    combineRow();
    moveLeft();
    generate();
  }

  function keyUp() {
    moveUp();
    combineColumn();
    moveUp();
    generate();
  }

  function keyDown() {
    moveDown();
    combineColumnDown();
    moveDown();
    generate();
  }

  function checkForWin() {
    for (let i = 0; i < squares.length; i++) {
      if (squares[i].innerHTML == 2048) {
        resultDisplay.innerHTML = "Ofarin!";
        setTimeout(() => clear(), 1000);
      }
    }
  }

  function checkForGameOver() {
    let zeros = 0;
    for (let i = 0; i < squares.length; i++) {
      if (squares[i].innerHTML == 0) {
        zeros++;
      }
    }
    if (zeros === 0) {
      resultDisplay.innerHTML = "Yutqazdingiz";
      setTimeout(() => clear(), 100);
    }
  }

  function disableButtons() {
    upButton.disabled = true;
    leftButton.disabled = true;
    rightButton.disabled = true;
    downButton.disabled = true;
  }

  function clear() {
    clearInterval(myTimer);
  }

  function addColours() {
    for (let i = 0; i < squares.length; i++) {
      const val = squares[i].innerHTML;
      if (val == 0) {
        squares[i].style.backgroundColor = "#afa192";
        squares[i].style.color = "#afa192"; // hide "0" text
      } else {
        squares[i].style.color = "";
        if (val == 2)    squares[i].style.backgroundColor = "#eee4da";
        else if (val == 4)    squares[i].style.backgroundColor = "#ede0c8";
        else if (val == 8)    squares[i].style.backgroundColor = "#f2b179";
        else if (val == 16)   squares[i].style.backgroundColor = "#ffcea4";
        else if (val == 32)   squares[i].style.backgroundColor = "#e8c064";
        else if (val == 64)   squares[i].style.backgroundColor = "#ffab6e";
        else if (val == 128)  squares[i].style.backgroundColor = "#fd9982";
        else if (val == 256)  squares[i].style.backgroundColor = "#ead79c";
        else if (val == 512)  squares[i].style.backgroundColor = "#76daff";
        else if (val == 1024) squares[i].style.backgroundColor = "#beeaa5";
        else if (val == 2048) squares[i].style.backgroundColor = "#d7d4f0";
        else squares[i].style.backgroundColor = "#eee4da"; // fallback for any other value
      }
    }
  }
  addColours();

  var myTimer = setInterval(addColours, 50);
});
