const DAY_IN_MS = 24 * 60 * 60 * 1000;
const HOUR_IN_MS = 60 * 60 * 1000;
const MIN_IN_MS = 60 * 1000;
const STORAGE_KEY = "dday-target";

const targetDateEl = document.getElementById("target-date");
const ddayLabelEl = document.getElementById("dday-label");
const timeLeftEl = document.getElementById("time-left");
const targetInput = document.getElementById("target-input");
const applyButton = document.getElementById("apply-target");

const dayNames = ["일", "월", "화", "수", "목", "금", "토"];

const defaultTarget = new Date(2025, 11, 11, 0, 0, 0);
const state = {
  targetDate: loadSavedTarget() ?? defaultTarget,
};

init();

function init() {
  applyButton.addEventListener("click", applyTargetFromInput);
  targetInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      applyTargetFromInput();
    }
  });

  targetInput.value = formatDateForInput(state.targetDate);
  updateTargetDisplay(state.targetDate);
  updateCountdown();
  setInterval(updateCountdown, 1000);
}

function loadSavedTarget() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? new Date(saved) : null;
  } catch (error) {
    return null;
  }
}

function saveTarget(date) {
  try {
    localStorage.setItem(STORAGE_KEY, date.toISOString());
  } catch (error) {
    // Swallow errors from browsers that block storage.
  }
}

function applyTargetFromInput() {
  const parsed = parseLocalDateTime(targetInput.value);
  if (!parsed || Number.isNaN(parsed.getTime())) {
    targetInput.classList.add("shake");
    setTimeout(() => targetInput.classList.remove("shake"), 400);
    return;
  }

  state.targetDate = parsed;
  saveTarget(parsed);
  updateTargetDisplay(parsed);
  updateCountdown();
}

function parseLocalDateTime(value) {
  if (!value) return null;
  const [datePart, timePart] = value.split("T");
  if (!datePart || !timePart) return null;

  const [year, month, day] = datePart.split("-").map(Number);
  const [hour = 0, minute = 0] = timePart.split(":").map(Number);

  if (
    [year, month, day].some((component) => Number.isNaN(component)) ||
    Number.isNaN(hour) ||
    Number.isNaN(minute)
  ) {
    return null;
  }

  return new Date(year, month - 1, day, hour, minute, 0, 0);
}

function updateTargetDisplay(date) {
  targetDateEl.textContent = formatHumanReadable(date);
}

function formatHumanReadable(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const dayName = dayNames[date.getDay()];
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${year}년 ${month}월 ${day}일 ${dayName}요일 ${hour}:${minute}`;
}

function formatDateForInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function updateCountdown() {
  const now = new Date();
  const target = state.targetDate;
  const diffMs = target.getTime() - now.getTime();

  if (diffMs <= 0) {
    const daysPast = Math.ceil((now.getTime() - target.getTime()) / DAY_IN_MS);
    ddayLabelEl.textContent = daysPast <= 0 ? "D-Day" : `D+${daysPast}`;
    timeLeftEl.textContent = "00시간 00분 00초";
    return;
  }

  const diffDays = Math.floor(diffMs / DAY_IN_MS);
  const totalHours = Math.floor(diffMs / HOUR_IN_MS);
  const remainderAfterHours = diffMs % HOUR_IN_MS;
  const diffMinutes = Math.floor(remainderAfterHours / MIN_IN_MS);
  const diffSeconds = Math.floor((remainderAfterHours % MIN_IN_MS) / 1000);

  ddayLabelEl.textContent = diffDays > 0 ? `D-${diffDays}` : "D-Day";
  timeLeftEl.textContent = [
    `${String(totalHours).padStart(2, "0")}시간`,
    `${String(diffMinutes).padStart(2, "0")}분`,
    `${String(diffSeconds).padStart(2, "0")}초`,
  ].join(" ");
}
