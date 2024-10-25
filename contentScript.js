function sendTextForAnalysis() {
    let pageText = document.body.innerText || ""; // Extract text from the page
    chrome.runtime.sendMessage({ action: 'analyzePage', text: pageText }); // Send to background script
    console.log('Text sent for analysis.');
}

chrome.runtime.onMessage.addListener((message) => {
    if (message.result) {
        console.log('Received analysis result:', message.result);
        alert('Analysis Result: ' + message.result); // Display result in alert for simplicity
    }
});

window.onload = () => {
    console.log('Content script injected.');
    sendTextForAnalysis(); // Send text once the page loads
};