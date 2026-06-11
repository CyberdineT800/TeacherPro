let board = [];
let rows = 8;
let columns = 8;

let minesCount = 10;
let minesLocation = [];

let tilesClicked = 0;
let flagEnabled = false;

let gameOver = false;

// Text markers used instead of emoji
const FLAG_MARKER = "F";
const MINE_MARKER = "X";

window.onload = function () {
  startGame();

  document.getElementById("refresh-button").addEventListener("click", resetGame);

  document.getElementById("dialog-close").addEventListener("click", function() {
    document.getElementById("game-dialog").style.display = "none";
  });
};

function resetGame() {
  document.getElementById("board").innerHTML = "";

  board = [];
  minesLocation = [];
  tilesClicked = 0;
  flagEnabled = false;
  gameOver = false;

  document.getElementById("flag-button").style.backgroundColor = "lightgray";

  startGame();
}

function setMines() {
  let minesLeft = minesCount;
  while (minesLeft > 0) {
    let r = Math.floor(Math.random() * rows);
    let c = Math.floor(Math.random() * columns);
    let id = r.toString() + "-" + c.toString();

    if (!minesLocation.includes(id)) {
      minesLocation.push(id);
      minesLeft -= 1;
    }
  }
}

function startGame() {
  document.getElementById("mines-count").innerText = minesCount;
  document.getElementById("flag-button").addEventListener("click", setFlag);
  setMines();

  for (let r = 0; r < rows; r++) {
    let row = [];
    for (let c = 0; c < columns; c++) {
      let tile = document.createElement("div");
      tile.id = r.toString() + "-" + c.toString();
      tile.addEventListener("click", clickTile);
      document.getElementById("board").append(tile);
      row.push(tile);
    }
    board.push(row);
  }
}

function setFlag() {
  if (flagEnabled) {
    flagEnabled = false;
    document.getElementById("flag-button").style.backgroundColor = "lightgray";
  } else {
    flagEnabled = true;
    document.getElementById("flag-button").style.backgroundColor = "darkgray";
  }
}

function showDialog(message) {
  document.getElementById("dialog-message").innerText = message;
  document.getElementById("game-dialog").style.display = "flex";
}

function clickTile() {
  if (gameOver || this.classList.contains("tile-clicked")) {
    return;
  }

  let tile = this;
  if (flagEnabled) {
    if (tile.innerText == "") {
      tile.innerText = FLAG_MARKER;
      tile.classList.add("flagged");
    } else if (tile.innerText == FLAG_MARKER) {
      tile.innerText = "";
      tile.classList.remove("flagged");
    }
    return;
  }

  if (minesLocation.includes(tile.id)) {
    gameOver = true;
    revealMines();
    showDialog("Afsuski, siz tuzoqqa tushdingiz!");
    return;
  }

  let coords = tile.id.split("-");
  let r = parseInt(coords[0]);
  let c = parseInt(coords[1]);
  checkMine(r, c);
}

function revealMines() {
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < columns; c++) {
      let tile = board[r][c];
      if (minesLocation.includes(tile.id)) {
        tile.innerText = MINE_MARKER;
        tile.classList.add("mine-revealed");
        tile.style.backgroundColor = "red";
      }
    }
  }
}

function checkMine(r, c) {
  if (r < 0 || r >= rows || c < 0 || c >= columns) {
    return;
  }
  if (board[r][c].classList.contains("tile-clicked")) {
    return;
  }

  board[r][c].classList.add("tile-clicked");
  tilesClicked += 1;

  let minesFound = 0;

  minesFound += checkTile(r - 1, c - 1);
  minesFound += checkTile(r - 1, c);
  minesFound += checkTile(r - 1, c + 1);

  minesFound += checkTile(r, c - 1);
  minesFound += checkTile(r, c + 1);

  minesFound += checkTile(r + 1, c - 1);
  minesFound += checkTile(r + 1, c);
  minesFound += checkTile(r + 1, c + 1);

  if (minesFound > 0) {
    board[r][c].innerText = minesFound;
    board[r][c].classList.add("x" + minesFound.toString());
  } else {
    board[r][c].innerText = "";

    checkMine(r - 1, c - 1);
    checkMine(r - 1, c);
    checkMine(r - 1, c + 1);

    checkMine(r, c - 1);
    checkMine(r, c + 1);

    checkMine(r + 1, c - 1);
    checkMine(r + 1, c);
    checkMine(r + 1, c + 1);
  }

  if (tilesClicked == rows * columns - minesCount) {
    document.getElementById("mines-count").innerText = "Barcha tuzoqlar topildi";
    gameOver = true;
    showDialog("Ofarin! Siz yutdingiz!");
  }
}

function checkTile(r, c) {
  if (r < 0 || r >= rows || c < 0 || c >= columns) {
    return 0;
  }
  if (minesLocation.includes(r.toString() + "-" + c.toString())) {
    return 1;
  }
  return 0;
}
