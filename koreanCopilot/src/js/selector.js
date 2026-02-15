/* selector module */

window.__selectors = {};

class Selector {
    constructor(selectElement, title, name, options, doChangeElement, allowDuplication, callback) {
        if (!selectElement || !title || !options || !callback) throw new Error("Selector: missing argument(s)!");
        this.selectElement = selectElement;
        this.selectElement.addEventListener("click", () => {
            this.activate();
            this.setTitle();
            this.setOptions();
        });
        this.title = title;
        this.name = name;
        this.options = options;
        this.doChangeElement = doChangeElement;
        this.allowDuplication = allowDuplication;
        this.callback = callback;

        if (!window.__selectors[this.name]) window.__selectors[this.name] = [];
        if (doChangeElement) {
            this.selectElement.innerHTML = "선택";
            this.selectElement.style.color = "#757575";
        }
    }

    activate() {
        document.querySelector("#selectorBox").classList.add("active");
    }

    deactivate() {
        document.querySelector("#selectorBox").classList.remove("active");
    }

    setTitle() {
        document.querySelector("#selectorTitle").innerHTML = this.title;
    }

    setOptions() {
        document.querySelector("#optionBox").innerHTML = "";
        for (var option of this.options) {
            if (!this.allowDuplication && window.__selectors[this.name].includes(option)) continue;
            var optionElement = document.createElement("div");
            optionElement.setAttribute("class", "option");
            optionElement.innerHTML = option;
            optionElement.addEventListener("click", (event) => {
                this.selectOption(event.target.innerHTML);
            });
            document.querySelector("#optionBox").appendChild(optionElement);
        }
    }

    selectOption(value) {
        this.value = value;
        this.deactivate();
        this.callback(this.value);

        window.__selectors[this.name].push(this.value);
        if (this.doChangeElement) {
            this.selectElement.style.color = "#000000";
            this.selectElement.innerHTML = this.value;
        }
    }

    isAlreadySelected(value) {
        return window.__selectors[this.name].includes(value);
    }
}

document.querySelector("#selectorBox").addEventListener("click", (event) => {
    event.target.classList.remove("active");
});

export default Selector;
