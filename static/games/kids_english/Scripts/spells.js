const words = ["Apple", "Banana", "Cat", "Dog", "Egg",
              "Fish", "Goat", "Hat", "Ice Cream", "Jacket",
               "Key", "Lion", "Monkey", "Nest", "Orange",
               "Pizza", "Queen", "Rabbit", "Sun", "Tiger",
               "Umbrella", "Van", "Wave", "Xray", "Yarn",
               "Zebra"];

const option1 = document.getElementById("option1");
const option2 = document.getElementById("option2");
const option3 = document.getElementById("option3");
const img = document.getElementById("hint");

var answer = "";


function randomInteger(max) {
  return Math.floor(Math.random() * max);
}

function generateAlphabet(capital = false) {
	return [...Array(26)].map((_, i) => String.fromCharCode(i + (capital ? 65 : 97)));
}

function getRandomLetter() {
    const alphabet = generateAlphabet();
    return alphabet[Math.floor(Math.random() * alphabet.length)];
}

function generate_question(){
  document.getElementById("letter1").innerHTML = "";
  document.getElementById("letter2").innerHTML = "";
  document.getElementById("letter3").innerHTML = "";
  document.getElementById("letter4").innerHTML = "";
  document.getElementById("letter5").innerHTML = "";
  document.getElementById("letter6").innerHTML = "";
  document.getElementById("letter7").innerHTML = "";
  document.getElementById("letter8").innerHTML = "";

  var random1 = randomInteger(25);
  var word = words[random1];
  var wordSrc = word.replace(/\s/g, '');
  var wordLength = wordSrc.length;
  var random2 = randomInteger(wordLength);

  var missingLetter = wordSrc[random2];
  var newSrc = "images/" + wordSrc.toLowerCase() + ".png";
  img.src= newSrc;
  var extra="";
  var allAnswers = [];
  var switchAnswers = [];

  var letter1 = getRandomLetter();
  var letter2 = getRandomLetter();

  answer = missingLetter.toUpperCase();
  allAnswers = [answer, letter1.toUpperCase(), letter2.toUpperCase()];

  for (i = allAnswers.length; i--;){
      switchAnswers.push(allAnswers.splice(Math.floor(Math.random() * (i + 1)), 1)[0]);
    };
 option1.innerHTML = switchAnswers[0];
 option2.innerHTML = switchAnswers[1];
 option3.innerHTML = switchAnswers[2];


     for (var x=0; x < wordLength; x++){
       if(x != random2){
         var y = x + 1;
         var i = "letter" + y.toString();
         document.getElementById(i).innerHTML = wordSrc[x];
       }else{
         var y = x + 1;
         var i = "letter" + y.toString();
         document.getElementById(i).innerHTML = "?";
       }
    }
}

option1.addEventListener("click", function(){
    if(option1.innerHTML == answer){
      generate_question();
    }
    else{
      audio.play();
    }
});

option2.addEventListener("click", function(){
    if(option2.innerHTML == answer){
      generate_question();
    }

});

option3.addEventListener("click", function(){
    if(option3.innerHTML == answer){
      generate_question();
    }

});

generate_question();
