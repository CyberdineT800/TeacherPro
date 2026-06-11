$(document).ready(modeMultiply);

$("#score").hide();
$("#game-canvas-controls").hide();

$(window).on("load", function() {
    initialiseBalloons();
    setTimeout(function(){
        $("#game-loader").hide();
        $("#score").removeClass("d-none");
        $("#score").fadeIn(1000);
        $("#game-canvas-controls").removeClass("d-none");
        $("#game-canvas-controls").fadeIn(1000);
    }, 1000);
});

$("#add").on("click", modeAddSubtract);

$("#subtract").on("click", modeAddSubtract);

$("#multiply").on("click", modeMultiply);

$("#divide").on("click", modeDivide);

$("#play").on("click", playGame);

$(".btn-mul-div-toggle").click(function(){
    let btnId = "#" + ($(this)[0].id);
    let btnIdArray = returnBtnIdArray("btn-mul-div");
    let i = btnIdArray.indexOf(btnId);
    if (i > -1) {
        btnIdArray.splice(i, 1);
    }

    makeNotActive(btnIdArray);
    if ($(this).hasClass("active")) {
        $(this).button('toggle');
    }
});

$(".btn-mul-div-sticky").click(function(){
    let btnIdArray = ["#btn-mul-div-1", "#btn-mul-div-2"];
    makeNotActive(btnIdArray);

    let btnId = ($(this)[0].id);
    if (($(this).hasClass("active")) && ((checkOtherStickyButtons(btnId)) == false)) {
        $(this).button('toggle');
    }
});

$(".btn-add-sub-toggle").click(function(){
    let btnId = "#" + ($(this)[0].id);
    let btnIdArray = returnBtnIdArray("btn-add-sub");
    let i = btnIdArray.indexOf(btnId);

    if (i > -1) {
        btnIdArray.splice(i, 1);
    }

    makeNotActive(btnIdArray);
    if ($(this).hasClass("active")) {
        $(this).button('toggle');
    }
});


$("#balloon-answer-text-left-1").on("click", checkSelectedAnswer);
$("#balloon-answer-text-left-2").on("click", checkSelectedAnswer);
$("#balloon-answer-text-left-3").on("click", checkSelectedAnswer);
$("#balloon-answer-text-right-1").on("click", checkSelectedAnswer);
$("#balloon-answer-text-right-2").on("click", checkSelectedAnswer);
$("#balloon-answer-text-right-3").on("click", checkSelectedAnswer);

$("#btn-game-section-home").on("click", returnToMenu);

$("#audio-off").on("click", muteAudio);

$("#audio-on").on("click", unMuteAudio);

$("#mute").on("click", muteAudioToggle);
