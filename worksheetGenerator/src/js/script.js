import Selector from "./selector.js";

const LEVELS = { Basic: 0.3, Intermediate: 0.5, Advanced: 0.7, Expert: 1.0, Answer: 0.0 };
const PRESETS = ["Tales of Birbal", "Aesop's Fables - The Greedy Dog"];
function readFile(url) {
    return fetch(url).then((response) => response.arrayBuffer());
}
function shuffle(array) {
    array.sort(() => Math.random() - 0.5);
}

function convertDocxToPdf(base64) {
    return fetch("https://v2.convertapi.com/convert/docx/to/pdf", {
        method: "POST",
        body: JSON.stringify({
            Parameters: [
                {
                    Name: "File",
                    FileValue: {
                        Name: "worksheet.docx",
                        Data: base64,
                    },
                },
            ],
        }),
        headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer token_laqwl6B4",
        },
    })
        .then((response) => response.json())
        .then((data) => {
            return data.Files[0].FileData;
        });
}

function generateWorksheet(title, content, translation, levels) {
    var sentences = content.split("\n").map((sentence) => sentence.trim());
    var translatedSentences = translation.split("\n").map((sentence) => sentence.trim());

    var pdfs = [];
    for (const level of levels) {
        const levelValue = LEVELS[level];
        docx.patchDocument({
            outputType: "base64",
            data: readFile("/worksheetGenerator/assets/template.docx"),
            patches: {
                title: {
                    type: docx.PatchType.PARAGRAPH,
                    children: [new docx.TextRun(title)],
                    style: "WorkSheetTitle",
                },
                level: {
                    type: docx.PatchType.PARAGRAPH,
                    children: [new docx.TextRun(level)],
                    style: "WorkSheetLevel",
                },
                table: {
                    type: docx.PatchType.DOCUMENT,
                    children: [
                        new docx.Table({
                            width: {
                                size: 100,
                                type: docx.WidthType.PERCENTAGE,
                            },
                            rows: sentences.map((sentence, index) => {
                                var words = sentence.split(" ");
                                if (level === "Expert") {
                                    words.map((word) => "__________");
                                } else {
                                    var hideWordIndex = [];
                                    for (let i = 0; i < words.length; i++) {
                                        if (!["A", "An", "The"].includes(words[i])) {
                                            hideWordIndex.push(i);
                                        }
                                    }
                                    shuffle(hideWordIndex);
                                    hideWordIndex.slice(0, Math.floor(hideWordIndex.length * levelValue)).forEach((index) => {
                                        words[index] = "__________";
                                    });
                                }
                                sentence = words.join(" ");
                                if (translation) {
                                    return new docx.TableRow({
                                        children: [
                                            new docx.TableCell({
                                                width: {
                                                    size: 7.5,
                                                    type: docx.WidthType.PERCENTAGE,
                                                },
                                                borders: {
                                                    top: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    left: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    right: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                },
                                                margins: {
                                                    top: docx.convertInchesToTwip(0.1),
                                                    bottom: docx.convertInchesToTwip(0.1),
                                                    left: docx.convertInchesToTwip(0.1),
                                                    right: docx.convertInchesToTwip(0.1),
                                                },
                                                verticalAlign: docx.VerticalAlign.CENTER,
                                                children: [
                                                    new docx.Paragraph({
                                                        children: [new docx.TextRun((index + 1).toString().padStart(2, "0"))],
                                                        style: "WorkSheetIndex",
                                                    }),
                                                ],
                                            }),
                                            new docx.TableCell({
                                                width: {
                                                    size: 60,
                                                    type: docx.WidthType.PERCENTAGE,
                                                },
                                                borders: {
                                                    top: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    left: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    right: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                },
                                                margins: {
                                                    top: docx.convertInchesToTwip(0.1),
                                                    bottom: docx.convertInchesToTwip(0.1),
                                                    left: docx.convertInchesToTwip(0.1),
                                                    right: docx.convertInchesToTwip(0.1),
                                                },
                                                verticalAlign: docx.VerticalAlign.CENTER,
                                                children: [
                                                    new docx.Paragraph({
                                                        children: [new docx.TextRun(sentence)],
                                                        style: "WorkSheetContent",
                                                    }),
                                                ],
                                            }),
                                            new docx.TableCell({
                                                width: {
                                                    size: 32.5,
                                                    type: docx.WidthType.PERCENTAGE,
                                                },
                                                borders: {
                                                    top: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    left: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    right: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                },
                                                margins: {
                                                    top: docx.convertInchesToTwip(0.1),
                                                    bottom: docx.convertInchesToTwip(0.1),
                                                    left: docx.convertInchesToTwip(0.1),
                                                    right: docx.convertInchesToTwip(0.1),
                                                },
                                                verticalAlign: docx.VerticalAlign.CENTER,
                                                children: [
                                                    new docx.Paragraph({
                                                        children: [new docx.TextRun(translatedSentences[index])],
                                                        style: "WorkSheetTranslated",
                                                    }),
                                                ],
                                            }),
                                        ],
                                    });
                                } else {
                                    return new docx.TableRow({
                                        children: [
                                            new docx.TableCell({
                                                width: {
                                                    size: 7.5,
                                                    type: docx.WidthType.PERCENTAGE,
                                                },
                                                borders: {
                                                    top: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    left: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    right: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                },
                                                margins: {
                                                    top: docx.convertInchesToTwip(0.1),
                                                    bottom: docx.convertInchesToTwip(0.1),
                                                    left: docx.convertInchesToTwip(0.1),
                                                    right: docx.convertInchesToTwip(0.1),
                                                },
                                                verticalAlign: docx.VerticalAlign.CENTER,
                                                children: [
                                                    new docx.Paragraph({
                                                        children: [new docx.TextRun((index + 1).toString().padStart(2, "0"))],
                                                        style: "WorkSheetIndex",
                                                    }),
                                                ],
                                            }),
                                            new docx.TableCell({
                                                width: {
                                                    size: 92.5,
                                                    type: docx.WidthType.PERCENTAGE,
                                                },
                                                borders: {
                                                    top: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    left: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                    right: { style: docx.BorderStyle.SINGLE, size: 1, color: "ffffff" },
                                                },
                                                margins: {
                                                    top: docx.convertInchesToTwip(0.1),
                                                    bottom: docx.convertInchesToTwip(0.1),
                                                    left: docx.convertInchesToTwip(0.1),
                                                    right: docx.convertInchesToTwip(0.1),
                                                },
                                                verticalAlign: docx.VerticalAlign.CENTER,
                                                children: [
                                                    new docx.Paragraph({
                                                        children: [new docx.TextRun(sentence)],
                                                        style: "WorkSheetContent",
                                                    }),
                                                ],
                                            }),
                                        ],
                                    });
                                }
                            }),
                        }),
                    ],
                },
            },
        })
            .then((base64) => {
                window.base64 = base64;
                return convertDocxToPdf(base64);
            })
            .then((pdf) => {
                saveAs("data:application/pdf;base64," + pdf, `${title} - ${level}.pdf`);
            });
    }
}

function exportWorksheet() {
    var title = titleInputElement.value;
    var content = contentInputElement.value;
    var translation = translationInputElement.value;
    if (title === "") {
        titleInputElement.focus();
        titleInputElement.classList.add("invalid");
        alert("제목을 입력해주세요.");
    } else if (content === "") {
        contentInputElement.focus();
        contentInputElement.classList.add("invalid");
        alert("본문을 입력해주세요.");
    } else if (!levelSelector.value) {
        levelSelectorElement.focus();
        levelSelectorElement.classList.add("invalid");
        alert("난이도를 선택해주세요.");
    } else {
        generateWorksheet(title, content, translation, [levelSelector.value]);
    }
}

function textAreaResize(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
}

const titleInputElement = document.querySelector("#titleInput");
const contentInputElement = document.querySelector("#contentInput");
const translationInputElement = document.querySelector("#translationInput");
const exportButtonElement = document.querySelector("#exportButton");
const presetSelectorElement = document.querySelector("#loadPresetButton");
const levelSelectorElement = document.querySelector("#levelSelector");

contentInputElement.addEventListener("input", (event) => {
    textAreaResize(event.target);
});

translationInputElement.addEventListener("input", (event) => {
    textAreaResize(event.target);
});

exportButtonElement.addEventListener("click", exportWorksheet);

var presetSelector = new Selector(presetSelectorElement, "Select Preset", "preset", PRESETS, false, true, async (value) => {
    var content = await fetch(`/worksheetGenerator/presets/${value}.txt`).then((response) => response.text());
    var translation = await fetch(`/worksheetGenerator/presets/${value}.kr.txt`).then((response) => response.text());
    titleInputElement.value = value;
    contentInputElement.value = content;
    translationInputElement.value = translation;
    textAreaResize(contentInputElement);
    textAreaResize(translationInputElement);
});

var levelSelector = new Selector(levelSelectorElement, "난이도 선택", "level", Object.keys(LEVELS), true, true, (value) => {});
