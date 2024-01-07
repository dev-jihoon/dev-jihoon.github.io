import Selector from "./selector.js";

const subjects = {
    normal: ["국어", "도덕", "사회", "역사", "수학", "과학", "기술가정", "영어", "한문", "중국어", "일본어", "정보"],
    art: ["체육", "음악", "미술"],
};

const essentialSubjects = ["국어", "수학", "과학", "영어", "체육"];

const semesters = ["2학년 1학기", "2학년 2학기", "3학년 1학기", "3학년 2학기"];


const normalSubjectAchievement = {
    A: 90,
    B: 80,
    C: 70,
    D: 60,
    E: 0,
};

const normalSubjectAchievementScores = {
    A: 5,
    B: 4,
    C: 3,
    D: 2,
    E: 1,
};

const artSubjectAchievement = {
    A: 80,
    B: 60,
    C: 0,
};

const artSubjectAchievementScores = {
    A: 3,
    B: 2,
    C: 1,
};

const attendanceScores = [
    [6, 5.4, 4.8, 4.2, 3.6, 3.0, 2.4],
    [7, 6.3, 5.6, 4.9, 4.2, 3.5, 2.8],
    [7, 6.3, 5.6, 4.9, 4.2, 3.5, 2.8],
];

const volunteerScores = [12, 12, 12, 12, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 20];

const awardScores = [0, 0.5, 1, 1.5, 2, 2, 2, 2];


function addSemester(semester) {
    const cardElement = document.createElement("div");
    cardElement.classList.add("card");
    cardElement.classList.add("semester");
    const cardHeaderElement = document.createElement("div");
    cardHeaderElement.classList.add("card-header");
    const titleElement = document.createElement("p");
    titleElement.classList.add("title");
    titleElement.innerText = semesters[semester];
    const buttonTextElement = document.createElement("span");
    buttonTextElement.classList.add("button-text");
    buttonTextElement.innerText = "추가";
    cardHeaderElement.appendChild(titleElement);
    cardHeaderElement.appendChild(buttonTextElement);
    cardElement.appendChild(cardHeaderElement);
    const tableElement = document.createElement("table");
    tableElement.classList.add("table");
    const trElement = document.createElement("tr");
    trElement.classList.add("row");
    const thElement1 = document.createElement("th");
    thElement1.innerText = "과목";
    const thElement2 = document.createElement("th");
    thElement2.innerText = "원점수";
    const thElement3 = document.createElement("th");
    thElement3.innerText = "성취도";
    trElement.appendChild(thElement1);
    trElement.appendChild(thElement2);
    trElement.appendChild(thElement3);
    tableElement.appendChild(trElement);
    cardElement.appendChild(tableElement);
    document.querySelector("#semesters").appendChild(cardElement);
    buttonTextElement.addEventListener("click", () => {
        addSubject(tableElement, semester);
    });
    new Array(10).fill(0).forEach(() => {
        addSubject(tableElement, semester);
    });
}

function addSubject(tableElement, semester) {
    const trElement = document.createElement("tr");
    trElement.classList.add("subject");
    const tdElement1 = document.createElement("td");
    const selectElement = document.createElement("button");
    selectElement.classList.add("select");
    tdElement1.appendChild(selectElement);
    const tdElement2 = document.createElement("td");
    const inputElement = document.createElement("input");
    inputElement.classList.add("input");
    inputElement.type = "number";
    inputElement.placeholder = "입력";
    inputElement.inputMode = "decimal";
    tdElement2.appendChild(inputElement);
    const tdElement3 = document.createElement("td");
    tdElement3.innerText = "N/A";
    trElement.appendChild(tdElement1);
    trElement.appendChild(tdElement2);
    trElement.appendChild(tdElement3);
    tableElement.appendChild(trElement);

    var selector = new Selector(selectElement, "과목", "subject_" + semester, subjects.normal.concat(subjects.art), (value) => {
        if (inputElement.value != "") {
            calcAchievement(value, inputElement.value, tdElement3);
        }
    });

    for(var essentialSubject of essentialSubjects) {
        if(!selector.isAlreadySelected(essentialSubject)) {
            selector.selectOption(essentialSubject);
            break;
        }
    }

    inputElement.addEventListener("input", (event) => {
        if (event.target.value > 100) {
            event.target.value = event.target.value.slice(0, 2);
            return;
        } else if (event.target.value < 0) {
            event.target.value = 0;
            return;
        } else if (selectElement.innerHTML != "선택" && event.target.value != "") {
            calcAchievement(selectElement.innerHTML, event.target.value, tdElement3);
        } else {
            tdElement3.innerText = "N/A";
        }
    });
}

function calcAchievement(subject, score, achievementElement) {
    if (subjects.normal.includes(subject)) {
        if (score >= normalSubjectAchievement.A) {
            achievementElement.innerText = "A";
        } else if (score >= normalSubjectAchievement.B) {
            achievementElement.innerText = "B";
        } else if (score >= normalSubjectAchievement.C) {
            achievementElement.innerText = "C";
        } else if (score >= normalSubjectAchievement.D) {
            achievementElement.innerText = "D";
        } else {
            achievementElement.innerText = "E";
        }
    } else if (subjects.art.includes(subject)) {
        if (score >= artSubjectAchievement.A) {
            achievementElement.innerText = "A";
        } else if (score >= artSubjectAchievement.B) {
            achievementElement.innerText = "B";
        } else {
            achievementElement.innerText = "C";
        }
    }
}

function invalidError(element) {
    element.focus();
    element.classList.add("invalid");
    alert("입력값이 올바르지 않습니다.");
}

addSemester(0);

document.querySelector("#addSemester").addEventListener("click", (event) => {
    const semester = document.querySelectorAll(".semester").length;
    if (semester == 3) {
        event.target.remove();
    }
    addSemester(semester);
});

document.querySelector("#calculate").addEventListener("click", () => {
    const semesters = document.querySelectorAll(".semester");

    var totalScore = 0;
    var semesterTotalScore = 0;
    var artSubjectAchievementTotalScore = 0;
    var artSubjectCount = 0;

    for (var semester of semesters) {
        var subjectElements = semester.querySelectorAll(".subject");
        var normalSubjectAchievementScore = 0;
        var normalSubjectScore = 0;
        var normalSubjectCount = 0;
        for (var subjectElement of subjectElements) {
            var subjectName = subjectElement.querySelector("td:first-child").innerText;
            var subjectAchievement = subjectElement.querySelector("td:nth-child(3)").innerText;

            if(subjectName == "선택") {
                return invalidError(subjectElement.querySelector("td:first-child .select"))
            } else {
                subjectElement.querySelector("td:first-child .select").classList.remove("invalid");
            }

            if (subjects.normal.includes(subjectName)) {
                var subjectScore = Math.round(subjectElement.querySelector("td:nth-child(2) .input").value);
                if (subjectScore == "") {
                    return invalidError(subjectElement.querySelector("td:nth-child(2) .input"));
                } else {
                    subjectElement.querySelector("td:nth-child(2) .input").classList.remove("invalid");
                }
                
                normalSubjectAchievementScore += normalSubjectAchievementScores[subjectAchievement];
                normalSubjectScore += subjectScore;
                normalSubjectCount++;
            } else {
                var subjectAchievement = subjectElement.querySelector("td:nth-child(3)").innerText;
                artSubjectAchievementTotalScore += artSubjectAchievementScores[subjectAchievement];
                artSubjectCount++;
            }
        }

        var normalSubjectAverageAchievementScore = normalSubjectAchievementScore / normalSubjectCount;
        var normalSubjectAverageScore = normalSubjectScore / normalSubjectCount;
        var semesterScore = normalSubjectAverageAchievementScore * 2 + normalSubjectAverageScore * 0.1;
        semesterTotalScore += semesterScore;
    }

    var averageSemesterScore = semesterTotalScore / semesters.length;

    totalScore += averageSemesterScore * 4 + 40;
    totalScore += (artSubjectAchievementTotalScore / (3 * artSubjectCount)) * 20 + 10;
    
    var absences = [...document.querySelectorAll("input[name='absenceInput']")];
    for (var absence of absences) {
        if (absence.value == "") return invalidError(absence);
    }
    absences = absences.map((v) => parseInt(v.value));

    var tardinesss = [...document.querySelectorAll("input[name='tardinessInput']")];
    for (var tardiness of tardinesss) {
        if (tardiness.value == "") return invalidError(tardiness);
    }
    tardinesss = tardinesss.map((v) => parseInt(v.value));

    var leaves = [...document.querySelectorAll("input[name='leaveInput']")];
    for (var leave of leaves) {
        if (leave.value == "") return invalidError(leave);
    }
    leaves = leaves.map((v) => parseInt(v.value));

    var totalAbsences = absences.map((v, i) => parseInt(v * 1 + tardinesss[i] / 3 + leaves[i] / 3));

    var attendanceScore = totalAbsences.map((v, i) => attendanceScores[i][v] || attendanceScores[i][6]).reduce((a, b) => a + b);
    totalScore += attendanceScore;

    var volunteer = document.querySelector("#volunteerInput");
    if (volunteer.value == "") return invalidError(volunteer);

    var volunteerScore = volunteerScores[volunteer.value - 1] || 20;
    totalScore += volunteerScore;

    var awardScore = awardScores[[...document.querySelectorAll("input[name='awardInput']:checked")].length];
    totalScore += awardScore + 8;

    var showTotalScore = Math.round(totalScore * 100) / 100;

    var resultScore = document.querySelector("#resultScore");
    resultScore.innerText = (parseFloat(showTotalScore) - parseInt(showTotalScore)).toFixed(2);
    var interval = setInterval(() => {
        if (resultScore.innerText == showTotalScore) {
            clearInterval(interval);
            return;
        } else if (resultScore.innerText == "NaN") {
            resultScore.innerText = showTotalScore;
            clearInterval(interval);
            return;
        }
        resultScore.innerText = Math.round((parseFloat(resultScore.innerText) + 1) * 100) / 100;
    }, 1);
        
    document.querySelector("#resultBox").classList.add("active");
});


document.querySelector("#resultBox").addEventListener("click", (event) => {
    event.target.classList.remove("active");
});

document.querySelector("#resultClose").addEventListener("click", (event) => {
    event.target.classList.remove("active");
});