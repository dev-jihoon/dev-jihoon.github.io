/* selector module */

class Selector {
    constructor(selectElement, title, options, callback) {
        if(!selectElement || !title || !options || !callback) throw new Error("Selector: missing argument(s)!");
        this.selectElement = selectElement;
        this.selectElement.innerHTML = "선택";
        this.selectElement.style.color = "#757575";
        this.selectElement.addEventListener("click", () => {
            this.activate();
            this.setTitle();
            this.setOptions();
        });
        this.title = title;
        this.options = options;
        this.callback = callback;
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
        for(var option of this.options) {
            var optionElement = document.createElement("div");
            optionElement.setAttribute("class", "option");
            optionElement.innerHTML = option;
            optionElement.addEventListener("click", (event) => {
                this.value = event.target.innerHTML;
                this.selectElement.style.color = "#000000";
                this.selectElement.innerHTML = this.value;
                this.deactivate();
                this.callback(this.value)
;            });
            document.querySelector("#optionBox").appendChild(optionElement);
        }
    }
}

document.querySelector("#selectorBox").addEventListener("click", (event) => {
    event.target.classList.remove("active");
});

export default Selector;