let analysisPanel;
let analysisResultText;
let analysisToggle;

function createAnalysisPanel() {
    const existingPanel = document.getElementById('misinfo-analysis-result');
    if (existingPanel) {
        existingPanel.remove();
    }

    analysisPanel = document.createElement('div');
    analysisPanel.id = 'misinfo-analysis-result';
    const shadowRoot = analysisPanel.attachShadow({ mode: 'closed' });

    const style = document.createElement('style');
    style.textContent = `
        .panel {
            position: fixed;
            top: 0;
            right: 0;
            z-index: 2147483647;
            display: flex;
            width: 380px;
            height: 100vh;
            flex-direction: column;
            background: #fff;
            color: #222;
            box-shadow: -3px 0 12px rgba(0, 0, 0, 0.25);
            font-family: Arial, sans-serif;
            transition: width 0.2s ease;
        }
        .panel.collapsed {
            width: 36px;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 52px;
            padding: 0 12px 0 18px;
            border-bottom: 1px solid #ddd;
            font-size: 18px;
            font-weight: bold;
        }
        .panel.collapsed .header {
            height: 100%;
            flex-direction: column;
            justify-content: flex-start;
            gap: 18px;
            padding: 14px 0;
        }
        .panel.collapsed .title {
            writing-mode: vertical-rl;
            font-size: 13px;
        }
        .toggle {
            border: 0;
            border-radius: 4px;
            background: #eee;
            color: #333;
            cursor: pointer;
            font-size: 18px;
            line-height: 1;
            padding: 6px 9px;
        }
        .toggle:hover {
            background: #ddd;
        }
        .content {
            display: flex;
            min-height: 0;
            flex: 1;
            flex-direction: column;
        }
        .panel.collapsed .content {
            display: none;
        }
        .result {
            flex: 1;
            margin: 0;
            padding: 18px;
            overflow: auto;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font: 14px/1.5 Arial, sans-serif;
        }
    `;

    const panel = document.createElement('div');
    panel.className = 'panel';

    const header = document.createElement('div');
    header.className = 'header';

    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = 'Analysis Result';

    analysisToggle = document.createElement('button');
    analysisToggle.className = 'toggle';
    analysisToggle.type = 'button';
    analysisToggle.setAttribute('aria-label', 'Collapse analysis panel');
    analysisToggle.setAttribute('aria-expanded', 'true');
    analysisToggle.textContent = '>';
    analysisToggle.addEventListener('click', () => {
        const collapsed = panel.classList.toggle('collapsed');
        analysisToggle.textContent = collapsed ? '<' : '>';
        analysisToggle.setAttribute('aria-expanded', String(!collapsed));
        analysisToggle.setAttribute(
            'aria-label',
            collapsed ? 'Expand analysis panel' : 'Collapse analysis panel'
        );
    });

    header.append(title, analysisToggle);

    const content = document.createElement('div');
    content.className = 'content';
    analysisResultText = document.createElement('pre');
    analysisResultText.className = 'result';
    analysisResultText.textContent = 'Waiting for analysis...';
    content.appendChild(analysisResultText);

    panel.append(header, content);
    shadowRoot.append(style, panel);
    document.documentElement.appendChild(analysisPanel);
}

function showAnalysisResult(result) {
    if (!analysisPanel) {
        createAnalysisPanel();
    }
    analysisResultText.textContent = result;
}

function sendTextForAnalysis() {
    let pageText = document.body.innerText || ""; // Extract text from the page
    chrome.runtime.sendMessage({ action: 'analyzePage', text: pageText }); // Send to background script
    console.log('Text sent for analysis.');
}

chrome.runtime.onMessage.addListener((message) => {
    if (message.result) {
        console.log('Received analysis result:', message.result);
        showAnalysisResult(message.result);
    }
});

createAnalysisPanel();

window.onload = () => {
    console.log('Content script injected.');
    sendTextForAnalysis(); // Send text once the page loads
};