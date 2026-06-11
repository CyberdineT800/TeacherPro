function playGame() {
    $("[id^=canvas-balloon]").show();
    $("[id^=balloon-answer-text]").show();

    bpmGameMode = returnGameMode();
    bpmQno = returnQuestions();
    bpmDifficulty = returnDifficulty();
    bpmActiveButtons = returnActiveButtons(bpmGameMode);
    bpmOptionArray = returnOptionArray(bpmActiveButtons);
    bpmQArray = returnQuestionArray(bpmGameMode, bpmOptionArray, bpmQno);
    bpmHealthArray = initialiseHealthBar(bpmDifficulty);
    bpmCQ = 0;
    bpmQCurrent = setQuestion(bpmQArray[bpmCQ]);
    bpmAnswerArray = answerArray(bpmGameMode, bpmQCurrent);
    bpmAnswerArray = setBalloons(bpmAnswerArray);
    bpmScoreArray = setScore([0, bpmQno]);

    $("#heading-section").hide(400);
    $("#options-section").hide(400);
    $("#information-section").hide(400);
    $("#game-section").hide();
    $("#game-section").removeClass("d-none");
    $("#game-section").show(1000);

    return bpmScoreArray;
}

function checkSelectedAnswer() {
    let answerTextID = "#"+ (this.id);
    let canvasID = "#"+ returnCanvasID(answerTextID);
    let sAnswer = this.innerHTML;
    let highScore = getHighScore();
    let currentScore;
    if (sAnswer == bpmQCurrent[1]) {
        soundPop.play();
        let balloonTimeout = animateBalloon(canvasID);
        currentScore = bpmScoreArray[0];
        bpmScoreArray = setScore([(currentScore + 1), bpmScoreArray[1]]);
        bpmCQ = bpmCQ + 1;
        if (bpmCQ < bpmQno) {
            $("[id^=canvas-balloon]").fadeIn("fast");
            $("[id^=balloon-answer-text]").fadeIn("fast");

            bpmQCurrent = setQuestion(bpmQArray[bpmCQ]);
            bpmAnswerArray = answerArray(bpmGameMode, bpmQCurrent);
            bpmAnswerArray = setBalloons(bpmAnswerArray);
        } else {
            if (checkHighScore(highScore, bpmScoreArray)) {
                setHighScore(bpmScoreArray);
                $("#modal-feedback-heading-text").text("Ajoyib - yangi eng yuqori ball!!!");
                soundHighScore.play();
            } else {
                if ((bpmScoreArray[0]) < 4) {
                    $("#modal-feedback-heading-text").text("Hech qisi yo'q. Yana urinib ko'ring!");
                    soundUnlucky.play();
                } else {
                    $("#modal-feedback-heading-text").text("Juda ajoyib!!!");
                    soundWellDone.play();
                }
            }
            $("#modal-feedback-body-text").text("Sizda " +  bpmScoreArray[0] + " dan " + bpmScoreArray[1] + "!");
            $('#modal-feedback').modal();

            returnToMenu();
        }
    } else {
        let cHealth = bpmHealthArray[0];
        if (cHealth > 0) {
            $(answerTextID).fadeOut("slow");
            $(canvasID).fadeOut("slow");

            let healthArray = [(cHealth - 1), bpmHealthArray[1]];
            bpmHealthArray = setHealthBar(healthArray);
            soundDeflate.play();
        } else {
            if (checkHighScore(highScore, bpmScoreArray)) {
                setHighScore(bpmScoreArray);

                $("#modal-feedback-heading-text").text("Ajoyib - yangi eng yuqori ball!!!");

                soundHighScore.play();
            } else {
                if ((bpmScoreArray[0]) < 4) {
                    $("#modal-feedback-heading-text").text("Hech qisi yo'q. Yana urinib ko'ring!");

                    soundUnlucky.play();
                } else {
                    $("#modal-feedback-heading-text").text("Juda ajoyib!");
                    soundWellDone.play();
                }
            }

            $("#modal-feedback-body-text").text("Sizda " +  bpmScoreArray[0] + " dan " + bpmScoreArray[1] + "!");
            $('#modal-feedback').modal();

            returnToMenu();
        }
    }
}
