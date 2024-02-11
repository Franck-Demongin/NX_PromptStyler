import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { api } from "../../scripts/api.js"

const COLOR_THEMES = {
    red: { nodeColor: "#332222", nodeBgColor: "#553333" },
    green: { nodeColor: "#223322", nodeBgColor: "#335533" },
    blue: { nodeColor: "#222233", nodeBgColor: "#333355" },
    pale_blue: { nodeColor: "#2a363b", nodeBgColor: "#3f5159" },
    cyan: { nodeColor: "#223333", nodeBgColor: "#335555" },
    purple: { nodeColor: "#332233", nodeBgColor: "#553355" },
    yellow: { nodeColor: "#443322", nodeBgColor: "#665533" },
    none: { nodeColor: null, nodeBgColor: null } // no color
};

const COLOR = "blue";
const NOT_NEEDED = ["presets", "Save Preset", 'Delete Preset', "Reset", "prompt_positive", "prompt_negative"];

app.registerExtension({
	name: "NX_PromptStyler",	
	
	async beforeRegisterNodeDef(nodeType, nodeData, app) {		
		if (nodeData.name === "NX_PromptStyler") {			
			const orig_nodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
				orig_nodeCreated?.apply(this, arguments);				
				
				// check if widget name is not in NOT_NEEDED
				const checkIfWidgetIsNeeded = (widget_name, not_needed = [], nedded = []) => {
					if (not_needed?.includes(widget_name)) return false
					if (nedded?.includes(widget_name)) return true
					if (NOT_NEEDED.includes(widget_name)) return false
					return true
				}

				// get weight
				const get_weight = (widget_name) => {
					const widget = this.widgets?.find((w) => w.name === `${widget_name} weight`);
					if (widget == null) return 1.0
					return widget.value
				}

				// set weight
				const set_weight = (widget_name, weight) => {
					const widget = this.widgets?.find((w) => w.name === `${widget_name} weight`);
					if (widget) widget.value = weight
				}

				// insert widget at index into this.widgets
				const insert_widget = (widget, index) => {
				    if (index < 0) {
						const widgets_count = this.widgets.length
						index = (widgets_count + 1) + index
					}
					if (index > this.widgets.length) index = this.widgets.length
				    this.widgets.splice(index, 0, widget);
				}

				// remove widget from this.widgets
				const remove_widget = (widget) => {
					const index = this.widgets.findIndex((w) => w.name === widget.name);
					if (index === -1) return
					this.widgets.splice(index, 1);
				}

				const move_widget = (widget, index) => {
					const old_index = this.widgets.findIndex((w) => w.name === widget.name);
					if (old_index === -1) return
					remove_widget(widget);
					insert_widget(widget, index);
				}

				// create widgets button Save Preset
				const buttonPreset = this.addWidget("button", "Save Preset", null, () => {
					const preset_widget = this.widgets?.find((w) => w.name === "presets");
					let preset_name = null
					if (preset_widget.value === "None" || preset_widget.value === "none") {
						preset_name = prompt('Preset name');
					}
					else {
						preset_name = prompt('Preset name', preset_widget.value);
					}
					
					if (preset_name === null) {
						return
					} 
					else {
						preset_name = preset_name.trim()
						preset_name = preset_name.toLowerCase()
						if (preset_name === "") {
							alert("Empty preset name is not allowed");
							return
						}
						if (preset_name === "none") {
							alert("\"none\" preset name is not allowed");
							return
						}
					} 
					console.log("Preset name: " + preset_name)
					const preset = {}
					preset["name"] = preset_name;
					preset["name_old"] = preset_widget.value;

					let values = {}
					for (let w1 of this.widgets) {
						if (checkIfWidgetIsNeeded(w1.name) == false || w1.type != "combo" || w1.value == 'None') continue
						values[w1.name] = [
							w1.value,
							get_weight(w1.name)
						]
					}
					preset["values"] = values

					const resp = api.fetchApi('/savepreset', {
						method: 'POST',
						body: JSON.stringify(preset),
					}).then(response => response.json())
					.then(data => {
						if (!data.saved) {
							if (data.error) alert("Error: " + data.error)
							else alert("Error: one error occurred")
						}
						else{
							if (preset_widget.options.values.indexOf(data.name_old) !== "none" && preset_widget.options.values.indexOf(data.name_old) !== -1){
								preset_widget.options.values.splice(preset_widget.options.values.indexOf(data.name_old),1)
							}
							if (preset_widget.options.values.indexOf(data.name) == -1){
								preset_widget.options.values.splice(0,1)
								preset_widget.options.values.push(data.name)
								preset_widget.options.values.sort()
								preset_widget.options.values.unshift("none")
							}
							preset_widget.value = data.name
						}
					})
					.catch(error => {
						console.error('Error:', error);
					})
				}, { serialize: false })
				this.widgets.splice(0, 0,this.widgets.pop());

				// create widgets button Delete Preset
				const buttonDeletePreset = this.addWidget("button", "Delete Preset", null, () => {
					const preset_widget = this.widgets?.find((w) => w.name === "presets");
					if (preset_widget.value == "None" || preset_widget.value == "none") {
						alert("No preset selected")
						return
					}
					const del = confirm(`Are you sure you want to delete "${preset_widget.value}" preset?`)
					if (!del) return
					
					const resp = api.fetchApi('/deletepreset', {
						method: 'POST',
						body: JSON.stringify({"preset": preset_widget.value}),
					}).then(response => response.json())
					.then(data => {
						if (!data.deleted) {
							alert("Error: one error occurred")
						}
						else{
							preset_widget.options.values.splice(preset_widget.options.values.indexOf(preset_widget.value), 1)
							preset_widget.value = "none"
						}
					})
					.catch(error => {
						console.error('Error:', error);
					})
				}, { serialize: false })
				this.widgets.splice(1, 0,this.widgets.pop());
				
				// create widgets button to reset weights and values
				const buttonReset = this.addWidget("button", "Reset", null, () => {
					for (let w of this.widgets) {
						if (checkIfWidgetIsNeeded(w.name) == false || w.type != "combo") continue
						w.value = w.options.values[0]
						set_weight(w.name, 1.0)
					}
				}, { serialize: false })
				this.widgets.splice(4, 0,this.widgets.pop());
				
				// callback function for presets list 
				const presets = this.widgets?.find((w) => w.name === "presets");	
				presets.callback = async (v) => {
					if (v === "None" || v === "none") {
						buttonPreset.label = "Save Preset"
						return
					}
					
					buttonPreset.label = "Update Preset"
					presets.value = 'Loading...'
					const resp = await api.fetchApi('/loadpreset', {
						method: 'POST',
						body: JSON.stringify({"preset": v}),
					}).then(response => response.json())
					.then(data => {
						if (data == null) return
						
						const data_keys = Object.keys(data)						
						for (let w of this.widgets) {
							if (checkIfWidgetIsNeeded(w.name) == false || w.type != "combo") continue																					
							if (
								data_keys.includes(w.name) == false || 
								data[w.name] == null ||
								w.options.values.includes(data[w.name][0]) == false
							) {
								w.value = w.options.values[0]
								set_weight(w.name, 1.0)
								continue
							}
							w.value = data[w.name][0]
							set_weight(w.name, data[w.name][1])
						}
						presets.value = v
					})
					.catch(error => {
						console.error('Error:', error);
						presets.value = 'none'
					})
				}
				remove_widget(presets)
				insert_widget(presets, 0)
				presets.options.values.sort()
				presets.options.values.unshift("none")

				// create widgets button to display positive prompt
				const buttonDisplayPositive = this.addWidget("button", "Generate Positive", null, () => {
					this.viewer_positive.value = 'Loading...'
					const values = {}
					for (let w of this.widgets) {
						if (checkIfWidgetIsNeeded(w.name, ["viewer_positive", "viewer_negative"], ["prompt_positive", "prompt_negative"]) == false || w.type == "button") continue
						values[w.name] = w.value
					}
					const resp = api.fetchApi('/loadprompt', {
						method: 'POST',
						body: JSON.stringify({"prompt": "positive", "data":values}),
					}).then(response => response.json())
					.then(data => {
						if (data == null) return
						this.viewer_positive.value = data.prompt
					})
					.catch(error => {
						console.error('Error:', error);
						this.viewer_positive.value = "";
					})	
				}, { serialize: false })

				// create widgets button to erase display_prompt_positive
				const buttonErasePositive = this.addWidget("button", "Erase Generated Positive", null, () => {
					this.viewer_positive.value = ""
				}, { serialize: false })
				console.log("buttonErasePositive", buttonErasePositive)

				// create widgets button to display negative prompt
				const buttonDisplayNegative = this.addWidget("button", "Generate Negative", null, () => {
					this.viewer_negative.value = 'Loading...'
					const values = {}
					for (let w of this.widgets) {
						if (checkIfWidgetIsNeeded(w.name, ["viewer_positive", "viewer_negative"], ["prompt_positive", "prompt_negative"]) == false || w.type == "button") continue
						values[w.name] = w.value
					}
					const resp = api.fetchApi('/loadprompt', {
						method: 'POST',
						body: JSON.stringify({"prompt": "negative", "data":values}),
					}).then(response => response.json())
					.then(data => {
						if (data == null) return
						this.viewer_negative.value = data.prompt
					})
					.catch(error => {
						console.error('Error:', error);
						this.viewer_negative.value = "";
					})	
				}, { serialize: false })

				// create widgets button to erase display_prompt_negaive
				const buttonEraseNegative = this.addWidget("button", "Erase Generated Negative", null, () => {
					this.viewer_negative.value = ""
				}, { serialize: false })
				console.log("buttonEraseNegative", buttonEraseNegative)

				this.viewer_positive = this.widgets.find((w) => w.name === "viewer_positive");
				this.viewer_negative = this.widgets.find((w) => w.name === "viewer_negative");

				move_widget(buttonDisplayPositive, -5)
				move_widget(buttonErasePositive, -4)
				
				// set shape, size horizontal and color
				nodeType.prototype.shape = "box";
				this.size[0] = 400;
				this.size[1] += 100;
				
				if (COLOR_THEMES[COLOR]) {
					this.color = COLOR_THEMES[COLOR].nodeColor;
					this.bgcolor = COLOR_THEMES[COLOR].nodeBgColor;
				}
			}	
		}
	}
});