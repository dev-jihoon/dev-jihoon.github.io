const GAK = "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";

const editor = document.getElementById("editor");
const ghostLayer = document.getElementById("ghost-layer");
const statusText = document.getElementById("statusText");
const aiToggle = document.getElementById("aiToggle");
const copyBtn = document.getElementById("copyBtn");

let currentSuggestion = "";
let isFetching = false;
let debounceTimer;

function syncScroll() {
    if (ghostLayer.scrollTop !== editor.scrollTop) {
        ghostLayer.scrollTop = editor.scrollTop;
    }
    requestAnimationFrame(syncScroll);
}
requestAnimationFrame(syncScroll);

editor.addEventListener("input", () => {
    ghostLayer.innerText = editor.value;
    currentSuggestion = "";

    clearTimeout(debounceTimer);

    if (!aiToggle.checked || editor.value.trim().length < 5) {
        statusText.innerText = aiToggle.checked ? "작성 중..." : "AI 꺼짐";
        return;
    }

    statusText.innerText = "문맥 읽는 중...";
    debounceTimer = setTimeout(() => {
        fetchAiNext(editor.value);
    }, 1500);
});

editor.addEventListener("keydown", (e) => {
    if (currentSuggestion && (e.key === "Enter" || e.key === "Tab")) {
        e.preventDefault();
        e.stopPropagation();
        acceptSuggestion();
    }
});

function acceptSuggestion() {
    const start = editor.selectionStart;
    const before = editor.value.substring(0, start);
    const after = editor.value.substring(start);

    editor.value = before + currentSuggestion + after;

    const newPos = start + currentSuggestion.length;
    editor.selectionStart = editor.selectionEnd = newPos;

    currentSuggestion = "";
    ghostLayer.innerText = editor.value;
    statusText.innerText = "문장 완성";
}

async function fetchAiNext(context) {
    if (isFetching) return;
    isFetching = true;
    statusText.innerText = "AI 제안 생성 중...";

    try {
        const response = await fetch(
            "https://api.groq.com/openai/v1/chat/completions",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${GAK}`,
                },
                body: JSON.stringify({
                    model: "llama-3.3-70b-versatile",
                    messages: [
                        {
                            role: "system",
                            content:
                                "너는 한국어 학술 문장 완성 AI야. 절대 앞 내용을 반복하지 마라. 이미 나온 단어로 시작하지 마라. 새로운 논리의 문장 하나만 완성해라. 부연설명 없이 본문만 출력해라.",
                        },
                        {
                            role: "user",
                            content: `이어서 작성해줘: "${context}"`,
                        },
                    ],
                    max_tokens: 60,
                    temperature: 0.5,
                    frequency_penalty: 2.0,
                    presence_penalty: 1.5,
                }),
            },
        );

        const data = await response.json();
        let aiResponse = data.choices?.[0]?.message?.content || "";

        if (aiResponse) {
            aiResponse = aiResponse
                .trim()
                .replace(/^["']|["']$/g, "")
                .replace(/\n/g, " ");

            const words = context.trim().split(/\s+/);
            const lastWord = words[words.length - 1];
            if (aiResponse.startsWith(lastWord)) {
                aiResponse = aiResponse.replace(lastWord, "").trim();
            }

            currentSuggestion = aiResponse;
            ghostLayer.innerText = editor.value + currentSuggestion;
            statusText.innerText = "제안 준비됨 (Enter/Tab)";
        }
    } catch (e) {
        statusText.innerText = "연결 오류";
    } finally {
        isFetching = false;
    }
}

copyBtn.onclick = () => {
    navigator.clipboard.writeText(editor.value).then(() => {
        const originalText = copyBtn.innerText;
        copyBtn.innerText = "복사됨!";
        setTimeout(() => (copyBtn.innerText = originalText), 2000);
    });
};
