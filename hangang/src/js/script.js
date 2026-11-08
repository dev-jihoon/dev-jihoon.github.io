fetch(`https://api.hangang.life/`)
    .then((response) => response.json())
    .then((data) => {
        var hangangData = data.DATAs.DATA.HANGANG["탄천"];
        document.querySelector(
            "#temperature"
        ).innerHTML = `한강수온 | ${hangangData.TEMP}°C`;
        document.querySelector("#description").innerHTML = `${parseDate(
            new Date(hangangData.LAST_UPDATE)
        )} 탄천에서 측정했습니다.`;
    });

function parseDate(date) {
    var month = date.getMonth() + 1;
    month = month < 10 ? "0" + month : month;

    var day = date.getDate();
    day = day < 10 ? "0" + day : day;

    var hour = date.getHours();
    var ampm = hour >= 12 ? "오후" : "오전";

    hour = hour % 12;
    hour = hour ? hour : 12;
    hour = hour < 10 ? "0" + hour : hour;

    return `${month}월 ${day}일 ${ampm} ${hour}시`;
}
