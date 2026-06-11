function getCanvasSize(canvasID) {
    if (canvasID.substr(0, 1) != "#") {
        canvasID = "#" + canvasID;
    }

    let cW = $(canvasID).width();
    let cH = $(canvasID).height();
    let cArray = [cW, cH];
    return cArray;
}

function drawBalloonImage(canvasID, img, fno) {
    if (canvasID.substr(0, 1) != "#") {
        canvasID = "#" + canvasID;
    }
    let beginX = 3072- (fno * 512);
    let canvasElement =  $(canvasID)[0];
    let canvasContext = canvasElement.getContext('2d');
    canvasContext.clearRect(0, 0, 300, 150);
    canvasContext.drawImage(img, beginX, 0, 512, 512, 0, 0, 300, 150);
    return(canvasContext);
}

function returnCanvasID(answerTextID) {
    if (answerTextID.substr(0, 1) != "#") {
        answerTextID = "#" + answerTextID;
    }

    let sArray = $(answerTextID).siblings();
    let canvasID = sArray[0].id;
    return(canvasID);
}

function animateBalloon(canvasID) {
    if (canvasID.substr(0, 1) != "#") {
        canvasID = "#" + canvasID;
    }
    let img;

    if (canvasID == "#canvas-balloon-left-1") {
        img = imgBalloonBlue;
    } else if (canvasID == "#canvas-balloon-left-2") {
        img = imgBalloonOrange;
    } else if (canvasID == "#canvas-balloon-left-3") {
        img = imgBalloonPurple;
    } else if (canvasID == "#canvas-balloon-right-1") {
        img = imgBalloonRed;
    } else if (canvasID == "#canvas-balloon-right-2") {
        img = imgBalloonGreen;
    } else if (canvasID == "#canvas-balloon-right-3") {
        img = imgBalloonYellow;
    }
    let balloonTimeout;
    balloonTimeout = setTimeout(drawBalloonImage, 25, canvasID, img, 1);
    balloonTimeout = setTimeout(drawBalloonImage, 50, canvasID, img, 2);
    balloonTimeout = setTimeout(drawBalloonImage, 75, canvasID, img, 3);
    balloonTimeout = setTimeout(drawBalloonImage, 200, canvasID, img, 4);
    balloonTimeout = setTimeout(drawBalloonImage, 300, canvasID, img, 5);
    balloonTimeout = setTimeout(drawBalloonImage, 400, canvasID, img, 6);
    balloonTimeout = setTimeout(drawBalloonImage, 500, canvasID, img, 1);
    return(balloonTimeout);
}

function initialiseBalloons() {
    $("[id^=canvas-balloon]").show();
    $("[id^=balloon-answer-text]").show();

    drawBalloonImage("canvas-balloon-left-1", imgBalloonBlue, 1);
    drawBalloonImage("canvas-balloon-left-2", imgBalloonOrange, 1);
    drawBalloonImage("canvas-balloon-left-3", imgBalloonPurple, 1);
    drawBalloonImage("canvas-balloon-right-1", imgBalloonRed, 1);
    drawBalloonImage("canvas-balloon-right-2", imgBalloonGreen, 1);
    drawBalloonImage("canvas-balloon-right-3", imgBalloonYellow, 1);
}
