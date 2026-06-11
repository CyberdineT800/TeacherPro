function muteAudioToggle(){
    if (bpmSoundEffectsMuted == false) {
        muteAudio();
    } else {
        unMuteAudio();
    }
    return(bpmSoundEffectsMuted);
}

function muteAudio(){
    soundPop.muted = true;
    soundDeflate.muted = true;
    soundHighScore.muted = true;
    soundUnlucky.muted = true;
    soundWellDone.muted = true;
    $("#mute").removeClass("fa-volume-up").addClass("fas fa-volume-mute");
    $("#audio-on").removeClass("active").attr("aria-pressed", "false");
    $("#audio-off").addClass("active").attr("aria-pressed", "true");
    bpmSoundEffectsMuted = true;
    return(bpmSoundEffectsMuted);
}

function unMuteAudio() {
    soundPop.muted = false;
    soundDeflate.muted = false;
    soundHighScore.muted = false;
    soundUnlucky.muted = false;
    soundWellDone.muted = false;
    $("#mute").removeClass("fa-volume-mute").addClass("fas fa-volume-up");
    $("#audio-off").removeClass("active").attr("aria-pressed", "false");
    $("#audio-on").addClass("active").attr("aria-pressed", "true");
    bpmSoundEffectsMuted = false;
    return(bpmSoundEffectsMuted);
}
