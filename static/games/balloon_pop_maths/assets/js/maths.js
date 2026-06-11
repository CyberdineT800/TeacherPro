function returnQuestionArray (gameMode, optionArray, qno) {
    let questionArray = [];

    if (gameMode == "multiply") {
        questionArray = returnMultiplicationQuestionArray(optionArray, qno);
    } else if (gameMode == "divide") {
        questionArray = returnDivisionQuestionArray(optionArray, qno);
    } else if (gameMode == "add") {
        questionArray = returnAdditionQuestionArray(optionArray, qno);
    } else if (gameMode == "subtract") {
        questionArray = returnSubtractionQuestionArray(optionArray, qno);
    }
    return(questionArray);
}

function returnMultiplicationQuestionArray (optionArray, qno) {
    let mqArray = [];
    let i;
    let ttq;
    let tk;

    if (optionArray[0] == "2x, 5x, 10x") {
        let remq = (qno % 3);
        let no2xQ = Math.floor(qno / 3) + remq;
        let no5xQ = Math.floor(qno / 3);
        let no10xQ = Math.floor(qno / 3);

        for (i = 0; i < no2xQ; i++) {
            ttq = returnMultiplicationQuestion(2);
            tk = 0;
            while ((tk < 11) && (checkQuestionArray(ttq, mqArray))) {
                ttq = returnMultiplicationQuestion(2);
                tk++;
            }

            mqArray.push(ttq);
        }
        for (i = 0; i < no5xQ; i++) {
            ttq = returnMultiplicationQuestion(5);
            tk = 0;
            while ((tk < 11) && (checkQuestionArray(ttq, mqArray))) {
                ttq = returnMultiplicationQuestion(5);
                tk++;
            }
            mqArray.push(ttq);
        }
        for (i = 0; i < no10xQ; i++) {
            ttq = returnMultiplicationQuestion(10);

            tk = 0;
            while ((tk < 11) && (checkQuestionArray(ttq, mqArray))) {
                ttq = returnMultiplicationQuestion(10);
                tk++;
            }
            mqArray.push(ttq);
        }
    } else if (optionArray[0] == "1 dan 12 gacha") {
        let ttno;
        let ttq;

        for (i = 0; i < qno; i++) {
            ttno = Math.floor((Math.random() * 12) + 1);
            ttq = returnMultiplicationQuestion(ttno);

            tk = 0;
            while ((tk < 11) && (checkQuestionArray(ttq, mqArray))) {
                ttq = returnMultiplicationQuestion(ttno);
                tk++;
            }
            mqArray.push(ttq);
        }
    } else {
        let ttk = 0;
        let ttqstr;
        let ttqstrnew;
        for (i = 0; i < qno; i++) {
            ttqstr = (optionArray[ttk]);
            ttqstrnew = ttqstr.substring(0, ttqstr.length - 1);
            ttq = returnMultiplicationQuestion(ttqstrnew);

            tk = 0;
            while ((tk < 11) && (checkQuestionArray(ttq, mqArray))) {
                ttq = returnMultiplicationQuestion(ttqstrnew);
                tk++;
            }

            mqArray.push(ttq);
            if (ttk < (optionArray.length - 1)) {
                ttk = (ttk + 1);
            } else {
                ttk = 0;
            }
        }
    }
    return(mqArray);
}

function returnDivisionQuestionArray (optionArray, qno) {
    let dqArray = [];
    let dq;
    let i;
    let dk;

    if ((optionArray[0].substring(1, 2) == "2") && (optionArray[0].substring(5, 6) == "5") && (optionArray[0].substring(9, 11) == "10")) {
        let remq = (qno % 3);
        let no2Q = Math.floor(qno / 3) + remq;
        let no5Q = Math.floor(qno / 3);
        let no10Q = Math.floor(qno / 3);
        let dq;

        for (i = 0; i < no2Q; i++) {
            dq = returnDivisionQuestion(2);
            dk = 0;
            while ((dk < 11) && (checkQuestionArray(dq, dqArray))) {
                dq = returnDivisionQuestion(2);
                dk++;
            }

            dqArray.push(dq);
        }
        for (i = 0; i < no5Q; i++) {
            dq = returnDivisionQuestion(5);
            dk = 0;
            while ((dk < 11) && (checkQuestionArray(dq, dqArray))) {
                dq = returnDivisionQuestion(5);
                dk++;
            }
            dqArray.push(dq);
        }
        for (i = 0; i < no10Q; i++) {
            dq = returnDivisionQuestion(10);
            dk = 0;
            while ((dk < 11) && (checkQuestionArray(dq, dqArray))) {
                dq = returnDivisionQuestion(10);
                dk++;
            }
            dqArray.push(dq);
        }
    } else if (optionArray[0] == "1 dan 12 gacha") {
        let dno;
        for (i = 0; i < qno; i++) {
            dno = Math.floor((Math.random() * 12) + 1);
            dq = returnDivisionQuestion(dno);
            dk = 0;
            while ((dk < 11) && (checkQuestionArray(dq, dqArray))) {
                dq = returnDivisionQuestion(dno);
                dk++;
            }
            dqArray.push(dq);
        }
    } else {
        let ddk = 0;
        let dqstr;
        let dqstrnew;
        for (i = 0; i < qno; i++) {
            dqstr = (optionArray[ddk]);
            dqstrnew = dqstr.substring(1, dqstr.length);
            dq = returnDivisionQuestion(dqstrnew);
            dk = 0;
            while ((dk < 11) && (checkQuestionArray(dq, dqArray))) {
                dq = returnDivisionQuestion(dqstrnew);
                dk++;
            }
            dqArray.push(dq);
            if (ddk < (optionArray.length - 1)) {
                ddk = (ddk + 1);
            } else {
                ddk = 0;
            }
        }
    }
    return(dqArray);
}

function returnAdditionQuestionArray (optionArray, qno) {
    let aqArray = [];
    let qt;
    let aq;
    let i;
    let ak;

    if (optionArray[0] == "10 gacha") {
        qt = 10;
    } else if (optionArray[0] == "20 gacha") {
        qt = 20;
    } else if (optionArray[0] == "50 gacha") {
        qt = 50;
    } else if (optionArray[0] == "100 gacha") {
        qt = 100;
    }

    for (i = 0; i < qno; i++) {
        aq =  returnAdditionQuestion(qt);
        ak = 0;
        while ((ak < qno) && (checkQuestionArray(aq, aqArray))) {
           aq =  returnAdditionQuestion(qt);
           ak++;
        }
        aqArray.push(aq);
    }
    return(aqArray);
}

function returnSubtractionQuestionArray (optionArray, qno) {
    let sqArray = [];
    let qt;
    let sq;
    let i;
    let sk;

    if (optionArray[0] == "10 gacha") {
        qt = 10;
    } else if (optionArray[0] == "20 gacha") {
        qt = 20;
    } else if (optionArray[0] == "50 gacha") {
        qt = 50;
    } else if (optionArray[0] == "100 gacha") {
        qt = 100;
    }

    for (i = 0; i < qno; i++) {
        sq = returnSubtractionQuestion(qt);

        sk = 0;
        while ((sk < qno) && (checkQuestionArray(sq, sqArray))) {
           sq = returnSubtractionQuestion(qt);
           sk++;
        }
        sqArray.push(sq);

    }
    return(sqArray);
}

function returnMultiplicationQuestion(tno) {
    let ttno = Math.floor((Math.random() * 12) + 1);
    let ttqStr = tno.toString() + " x " + ttno.toString();
    let ttAnswer = (tno * ttno);
    let mq = [ttqStr, ttAnswer];
    return mq;
}

function returnDivisionQuestion(dno) {
    let dtno = Math.floor((Math.random() * 12) + 1);
    let dsum = dtno * dno;
    let dqStr = dsum.toString() + " &divide " + dno.toString();
    let dAnswer = (dtno);
    let dq = [dqStr, dAnswer];
    return dq;
}

function returnAdditionQuestion(maxsum) {
    let no1 = Math.floor((Math.random() * (maxsum / 2)) + 1);
    let no2 = Math.floor((Math.random() * (maxsum / 2)) + 1);
    let aqStr = no1.toString() + " + " + no2.toString();
    let aqAnswer = (no1 + no2);
    let aq = [aqStr, aqAnswer];
    return aq;
}

function returnSubtractionQuestion(maxsum) {
    let no1 = Math.floor((Math.random() * maxsum) + 1);
    let no2 = Math.floor((Math.random() * maxsum) + 1);
    let minno = Math.min(no1, no2);
    let maxno = Math.max(no1, no2);
    let mqStr = maxno.toString() + " - " + minno.toString();
    let mqAnswer = (maxno - minno);
    let mq = [mqStr, mqAnswer];
    return mq;
}

function checkQuestionArray(nq, qArray) {
    let i = 0;
    let qCheck = false;
    while ((qCheck == false) && (i < qArray.length)) {
        if (qArray[i][0] == nq[0]) {
            qCheck = true;
        }
        i++;
    }
    return(qCheck);
}

function answerArray(gameMode, qCurrent) {
    let answerArray = [];

    if (gameMode == "multiply") {
        answerArray = wrongAnswersMultiplication(qCurrent);
    } else if (gameMode == "divide") {
        answerArray = wrongAnswersDivision(qCurrent);
    } else if (gameMode == "add") {
        answerArray = wrongAnswersAddition(qCurrent);
    } else if (gameMode == "subtract") {
        answerArray = wrongAnswersSubtraction(qCurrent);
    }

    answerArray.push(qCurrent[1]);
    answerArray = shuffleArray(answerArray);
    return(answerArray);
}

function wrongAnswersMultiplication(qCurrent) {
    let qStr = qCurrent[0];
    let qStrArray = qStr.split(" ");
    let no1 = parseInt(qStrArray[0]);
    let no2 = parseInt(qStrArray[2]);
    let cA = qCurrent[1];
    let wrongAnswerArray = [];

    if (no1 > 1) {
        wrongAnswerArray.push((no1 - 1) * no2);
    } else {
        wrongAnswerArray.push((no1 + 2) * no2);
    }
    if (no1 > 2) {
        wrongAnswerArray.push((no1 - 2) * no2);
    } else {
        wrongAnswerArray.push((no1 + 3) * no2);
    }
    wrongAnswerArray.push((no1 + 1) * no2);
    let minInt = ((no1 - 1) * no2);
    let maxInt = ((no1 + 1) * no2);
    if (maxInt < 10) {
        minInt = 0;
        maxInt = 10;
    }

    wrongAnswerArray = wrongAnswerArrayComplete(wrongAnswerArray, cA, minInt, maxInt);
    return(wrongAnswerArray);
}

function wrongAnswersDivision(qCurrent) {
    let qStr = qCurrent[0];
    let qStrArray = qStr.split(" ");
    let no1 = parseInt(qStrArray[0]);
    let cA = qCurrent[1];
    let minInt = 1;
    let maxInt = 12;

    if (no1 < 12) {
        maxInt = no1;
    }

    if (maxInt < 6) {
        maxInt = 6;
    }

    let wrongAnswerArray = [(cA - 1), (cA + 1), (cA + 2)];
    wrongAnswerArray = wrongAnswerArrayComplete(wrongAnswerArray, cA, minInt, maxInt);
    return(wrongAnswerArray);
}

function wrongAnswersAddition(qCurrent) {
    let qStr = qCurrent[0];
    let qStrArray = qStr.split(" ");
    let no1 = parseInt(qStrArray[0]);
    let no2 = parseInt(qStrArray[2]);
    let cA = qCurrent[1];
    let wrongAnswerArray = [(cA - 1), (cA + 1), (cA + 2)];
    let minInt = (Math.max(no1, no2)) + 1;
    let maxInt = (no1 + no2 + 6);

    wrongAnswerArray = wrongAnswerArrayComplete(wrongAnswerArray, cA, minInt, maxInt);
    return(wrongAnswerArray);
}

function wrongAnswersSubtraction(qCurrent) {
    let qStr = qCurrent[0];
    let qStrArray = qStr.split(" ");
    let no1 = parseInt(qStrArray[0]);
    let cA = qCurrent[1];
    let wrongAnswerArray = [(cA - 1), (cA + 1), (cA + 2)];
    let maxInt = no1 - 1;
    let minInt = 0;

    if (maxInt < 6) {
        maxInt = 6;
    }

    wrongAnswerArray = wrongAnswerArrayComplete(wrongAnswerArray, cA, minInt, maxInt);
    return(wrongAnswerArray);
}

function wrongAnswerArrayComplete(wrongAnswerArray, cA, minInt, maxInt) {
    if ((maxInt - minInt) < 6) {
        maxInt = minInt + 6;
    }

    let randomInt;
    randomInt = getRandomIntInclusive(minInt, maxInt);

    while ((wrongAnswerArray.includes(randomInt)) || (randomInt == cA)) {
        randomInt = getRandomIntInclusive(minInt, maxInt);
    }

    wrongAnswerArray.push(randomInt);
    randomInt = getRandomIntInclusive(minInt, maxInt);

    while ((wrongAnswerArray.includes(randomInt)) || (randomInt == cA)) {
        randomInt = getRandomIntInclusive(minInt, maxInt);
    }

    wrongAnswerArray.push(randomInt);
    return(wrongAnswerArray);
}

function getRandomIntInclusive(min, max) {
  min = Math.ceil(min);
  max = Math.floor(max);

  return Math.floor(Math.random() * (max - min + 1) + min);
}

function shuffleArray(arrayToShuffle) {
    let j;
    for (let i = arrayToShuffle.length - 1; i > 0; i--) {
        j = Math.floor(Math.random() * (i + 1));
        [arrayToShuffle[i], arrayToShuffle[j]] = [arrayToShuffle[j], arrayToShuffle[i]];
    }
    return(arrayToShuffle);
}
