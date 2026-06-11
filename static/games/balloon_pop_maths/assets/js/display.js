function returnToMenu() {
    $("#game-section").hide(400);
    $("#heading-section").show(400);
    $("#options-section").show(400);
    $("#information-section").show(400);
}

function modeAddSubtract() {
    $("#options-multiply-divide").hide(400);
    $("#options-add-subtract").show(400);
    makeActive("#btn-mul-div-1");
}

function modeMultiply() {
    $("#options-add-subtract").hide(400);
    $("#options-multiply-divide").show(400);
    makeActive("#btn-mul-div-1");

    $("#btn-mul-div-1").html("2x, 5x, 10x");
    $("#btn-mul-div-2").html("1 dan 12 gacha");
    $("#btn-mul-div-3").html("1x");
    $("#btn-mul-div-4").html("7x");
    $("#btn-mul-div-5").html("2x");
    $("#btn-mul-div-6").html("8x");
    $("#btn-mul-div-7").html("3x");
    $("#btn-mul-div-8").html("9x");
    $("#btn-mul-div-9").html("4x");
    $("#btn-mul-div-10").html("10x");
    $("#btn-mul-div-11").html("5x");
    $("#btn-mul-div-12").html("11x");
    $("#btn-mul-div-13").html("6x");
    $("#btn-mul-div-14").html("12x");
}

function modeDivide() {
    $("#options-add-subtract").hide(400);
    $("#options-multiply-divide").show(400);
    makeActive("#btn-mul-div-1");

    $("#btn-mul-div-1").html("&divide2, &divide5, &divide10");
    $("#btn-mul-div-2").html("1 dan 12 gacha");
    $("#btn-mul-div-3").html("&divide1");
    $("#btn-mul-div-4").html("&divide7");
    $("#btn-mul-div-5").html("&divide2");
    $("#btn-mul-div-6").html("&divide8");
    $("#btn-mul-div-7").html("&divide3");
    $("#btn-mul-div-8").html("&divide9");
    $("#btn-mul-div-9").html("&divide4");
    $("#btn-mul-div-10").html("&divide10");
    $("#btn-mul-div-11").html("&divide5");
    $("#btn-mul-div-12").html("&divide11");
    $("#btn-mul-div-13").html("&divide6");
    $("#btn-mul-div-14").html("&divide12");
}

function returnBtnIdArray(btnPrefix) {
    let btnArray = $(":button");
    let btnIdArray = [];
    let i = 0;
    for (i = 0; i < btnArray.length; i++) {
        if (((btnArray[i].id).search(btnPrefix)) > -1) {
            btnIdArray.push("#" + btnArray[i].id);
        }
    }
    return(btnIdArray);
}

function makeActive(btnId) {
    let btnIdArray = ["#btn-mul-div-1", "#btn-mul-div-2", "#btn-mul-div-3", "#btn-mul-div-4", "#btn-mul-div-5", "#btn-mul-div-6", "#btn-mul-div-7", "#btn-mul-div-8", "#btn-mul-div-9", "#btn-mul-div-10", "#btn-mul-div-11", "#btn-mul-div-12", "#btn-mul-div-13", "#btn-mul-div-14"];
    makeNotActive(btnIdArray);
    $(btnId).addClass("active").attr("aria-pressed", "true");
    return(btnId);
}

function makeNotActive(btnIdArray) {
    for (let btnId of btnIdArray) {
        $(btnId).removeClass("active").removeClass("focus").attr("aria-pressed", "false");
    }
    return(btnIdArray);
}

function checkOtherStickyButtons(btnId) {
    let mdbtnIdArray = $(".btn-mul-div-sticky");
    let activeFlag = false;
    let i = 0;
    while ((activeFlag == false) && (i < mdbtnIdArray.length)) {
        if (((mdbtnIdArray[i].id) !== btnId) && (mdbtnIdArray[i].classList.contains("active"))) {
            activeFlag = true;
        }
        i++;
    }
    return(activeFlag);
}

function returnGameMode() {
    let gameMode = "";
    if ($("#multiply").hasClass("active")) {
        gameMode = "multiply";
    } else if ($("#divide").hasClass("active")) {
        gameMode = "divide";
    } else if ($("#add").hasClass("active")) {
        gameMode = "add";
    } else if ($("#subtract").hasClass("active")) {
        gameMode = "subtract";
    }
    return(gameMode);
}

function returnDifficulty() {
    let difficulty = "";
    if ($("#easy").hasClass("active")) {
        difficulty = "easy";
    } else if ($("#medium").hasClass("active")) {
        difficulty = "medium";
    } else if ($("#hard").hasClass("active")) {
        difficulty = "hard";
    }
    return(difficulty);
}

function returnQuestions() {
    let qno = "";
    if ($("#10q").hasClass("active")) {
        qno = 10;
    } else if ($("#20q").hasClass("active")) {
        qno = 20;
    }
    return(qno);
}

function returnActiveButtons(gameMode) {
    let btnIdArray = btnArray();
    let btnActiveArray = [];
    for (let btnId of btnIdArray) {
        btnId = "#" + btnId;
        if ($(btnId).hasClass("active")) {
            if ((gameMode == "add" || gameMode == "subtract") && ((btnId.substring(1, 12)) == "btn-add-sub")) {
                btnActiveArray.push(btnId);
            }
            if ((gameMode == "multiply" || gameMode == "divide") && ((btnId.substring(1, 12)) == "btn-mul-div")) {
                btnActiveArray.push(btnId);
            }
        }
    }
    return(btnActiveArray);
}

function btnArray() {
    let btnArray = [];
    $(':button.btn-xl').each(function() {
        let btnId = (this.id);
        if (btnId != "") {
            btnArray.push(btnId);
        }
    });
    return btnArray;
}

function returnOptionArray (activeButtons) {
    let optionArray = [];
    for (let [key, btnId] of Object.entries(activeButtons)) {
        optionArray.push($(btnId).text());
        key = key;
    }
    return(optionArray);
}

function initialiseHealthBar(difficulty) {
    let healthArray;
    if (difficulty == "easy") {
        healthArray = [5, 5];
        $("#heart1").show();
        $("#heart2").show();
        $("#heart3").show();
        $("#heart4").show();
        $("#heart5").show();
    } else if (difficulty == "medium") {
        healthArray = [3, 3];
        $("#heart1").show();
        $("#heart2").show();
        $("#heart3").show();
        $("#heart4").hide();
        $("#heart5").hide();
    } else if (difficulty == "hard") {
        healthArray = [1, 1];
        $("#heart1").show();
        $("#heart2").hide();
        $("#heart3").hide();
        $("#heart4").hide();
        $("#heart5").hide();
    }
    setHealthBar(healthArray);
    return healthArray;
}

function setHealthBar(healthArray) {
    let currentHealth = healthArray[0];
    let totalHealth = healthArray[1];
    let i;
    let hstr;

    for (i = 1; i < (totalHealth + 1); i++) {
        hstr = "#heart" + i;
        $(hstr).removeClass("far fa-heart").addClass("fas fa-heart");
    }

    for (i = (currentHealth + 1); i < (totalHealth + 1); i++) {
        hstr = "#heart" + i;
        $(hstr).removeClass("fas fa-heart").addClass("far fa-heart");
    }
    return(healthArray);
}

function checkHighScore(highScore, scoreArray) {
    let res = false;
    if (scoreArray[0] > 0) {
        if (
            ((scoreArray[0] / scoreArray[1]) > (highScore[0] / highScore[1])) ||
            ((scoreArray[0] / scoreArray[1]) == ((highScore[0] / highScore[1])) && (scoreArray[1] > highScore[1]))
            ) {
        res = true;
        }
    }
    return res;
}

function getHighScore() {
    let scoreString = $("#highscore").text();
    let scoreArrayTemp = scoreString.split(" ");
    let scoreArray = [parseInt(scoreArrayTemp[2]), parseInt(scoreArrayTemp[4])];
    return scoreArray;
}

function setHighScore(scoreArray) {
    let scoreString = "Yuqori ball: " + scoreArray[0] + " / " + scoreArray[1];
    $("#highscore").text(scoreString);
    return(scoreArray);
}

function setScore(scoreArray) {
    let scoreString = "Ball: " + scoreArray[0] + " / " + scoreArray[1];
    $("#score").text(scoreString);
    return(scoreArray);
}

function setQuestion(qCurrent) {
    let qString = qCurrent[0];
    $("#question").html(qString);
    return(qCurrent);
}

function setBalloons(answerArray) {
    $("#balloon-answer-text-left-1").html(answerArray[0]);
    $("#balloon-answer-text-left-2").html(answerArray[1]);
    $("#balloon-answer-text-left-3").html(answerArray[2]);
    $("#balloon-answer-text-right-1").html(answerArray[3]);
    $("#balloon-answer-text-right-2").html(answerArray[4]);
    $("#balloon-answer-text-right-3").html(answerArray[5]);
    return(answerArray);
}
