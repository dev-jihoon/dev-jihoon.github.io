const SEOUL_OPEN_API_KEY = "5a55706e6c706a68373062656d6b64";

fetch(
    `http://openapi.seoul.go.kr:8088/${SEOUL_OPEN_API_KEY}/json/WPOSInformationTime/1/1/`
)
    .then((response) => response.json())
    .then((data) => {
        var W_TEMP = data.WPOSInformationTime.row[0].W_TEMP;
        var MSR_DATE = data.WPOSInformationTime.row[0].MSR_DATE;
        var SITE_ID = data.WPOSInformationTime.row[0].SITE_ID;

        document.querySelector(
            "#temperature"
        ).innerHTML = `한강수온 | ${W_TEMP}°C`;
        document.querySelector("#description").innerHTML = `${MSR_DATE.slice(
            4,
            6
        )}월 ${MSR_DATE.slice(6, 8)}일 ${SITE_ID}에서 측정했습니다.`;
    });
