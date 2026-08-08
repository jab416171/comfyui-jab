import { app } from "../../scripts/app.js";

console.log("[jab extension] Loading extension...");

const refreshOpenAIModelNodes = async () => {
    const nodes = app.graph?._nodes || [];
    const refreshTasks = nodes
        .filter(node => node.comfyClass === "Get OpenAI Models" && typeof node.__openaiUpdateModelList === "function")
        .map(node => node.__openaiUpdateModelList());

    if (refreshTasks.length === 0) {
        return;
    }

    console.log(`[jab extension] Refreshing ${refreshTasks.length} Get OpenAI Models node(s) before run`);
    await Promise.allSettled(refreshTasks);
};

// extension to dynamically populate the model dropdown based on base_url
app.registerExtension({
    name: "comfyui_jab.models",

    async setup() {
        if (app.__openaiQueuePatchApplied) {
            return;
        }

        if (typeof app.queuePrompt !== "function") {
            console.warn("[jab extension] app.queuePrompt not found; run-time refresh hook not installed");
            return;
        }

        const originalQueuePrompt = app.queuePrompt.bind(app);
        app.queuePrompt = async (...args) => {
            await refreshOpenAIModelNodes();
            return originalQueuePrompt(...args);
        };

        app.__openaiQueuePatchApplied = true;
        console.log("[jab extension] Installed pre-run model refresh hook");
    },

    async nodeCreated(node) {
        console.log("[OpenAI extension] nodeCreated called for:", node.comfyClass);

        if (node.comfyClass === "Get OpenAI Models") {
            console.log("[jab extension] Processing Get OpenAI Models node");

            const baseUrlWidget = node.widgets.find(w => w.name === "base_url");
            let modelWidget = node.widgets.find(w => w.name === "model");

            if (!baseUrlWidget || !modelWidget) {
                console.log("[OpenAI extension] Could not find required widgets");
                return;
            }

            // Keep backend type as STRING (for prompt validation) but render as a combo widget.
            if (modelWidget.type !== "combo") {
                const existingValue = modelWidget.value || "Select a model...";
                const modelWidgetIndex = node.widgets.findIndex(w => w.name === "model");
                if (modelWidgetIndex !== -1) {
                    node.widgets.splice(modelWidgetIndex, 1);
                }

                modelWidget = node.addWidget(
                    "combo",
                    "model",
                    existingValue,
                    (value) => {
                        modelWidget.value = value;
                    },
                    { values: [existingValue] }
                );
            }

            const origBaseUrlCallback = baseUrlWidget.callback;

            const updateModelList = async () => {
                const baseUrl = baseUrlWidget.value;
                console.log("[jab extension] Updating model list for base_url:", baseUrl);
                if (!baseUrl) {
                    console.log("[OpenAI extension] No base_url provided");
                    return;
                }

                try {
                    // Use ComfyUI's internal API proxy to avoid CSP issues
                    const params = new URLSearchParams({ base_url: baseUrl });
                    const response = await fetch(`/jab/models?${params.toString()}`, {
                        method: "GET",
                        headers: { "Content-Type": "application/json" },
                    });

                    console.log("[jab extension] Fetch response status:", response.status);

                    if (!response.ok) throw new Error(`HTTP ${response.status}`);

                    const data = await response.json();
                    console.log("[jab extension] API response:", data);
                    const modelIds = data.data?.map(m => m.id) || [];
                    console.log("[jab extension] Model IDs:", modelIds);

                    if (modelIds.length > 0) {
                        const currentValue = modelWidget.value;
                        const values = [...modelIds];
                        if (currentValue && currentValue !== "Select a model..." && !values.includes(currentValue)) {
                            values.unshift(currentValue);
                        }

                        modelWidget.options.values = values;
                        if (!modelWidget.value || modelWidget.value === "Select a model...") {
                            modelWidget.value = values[0];
                        }
                        console.log(`[jab extension] Loaded ${modelIds.length} models from ${baseUrl}`);
                        node.setDirtyCanvas(true, true);
                    } else {
                        const currentValue = modelWidget.value;
                        modelWidget.options.values = currentValue
                            ? [currentValue, "Select a model..."]
                            : ["Select a model..."];
                        if (!currentValue) {
                            modelWidget.value = "Select a model...";
                        }
                        console.log(`[jab extension] No models found at ${baseUrl}`);
                        node.setDirtyCanvas(true, true);
                    }
                } catch (error) {
                    console.error(`[jab extension] Failed to fetch models from ${baseUrl}:`, error);
                    const currentValue = modelWidget.value;
                    modelWidget.options.values = currentValue
                        ? [currentValue, "Select a model..."]
                        : ["Select a model..."];
                    if (!currentValue) {
                        modelWidget.value = "Select a model...";
                    }
                    node.setDirtyCanvas(true, true);
                }
            };

            baseUrlWidget.callback = (value) => {
                console.log("[jab extension] base_url changed to:", value);
                origBaseUrlCallback?.call(node, value);
                updateModelList();
            };

            node.__openaiUpdateModelList = updateModelList;

            updateModelList();
        }
    },
});
