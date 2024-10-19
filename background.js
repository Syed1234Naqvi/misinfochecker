chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Received message:", message);

    if (message.action === 'analyzePage' && message.text) {
        console.log("Sending text to the server:", message.text);

        fetch('https://misinfochecker.com/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: message.text
            })
        })
        .then(response => {
            console.log("Server response status:", response.status);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log("Server response data:", data);
            sendResponse({ status: 'success', result: data.analysis_results });
        })
        .catch(error => {
            console.error("Error during server request:", error);
            sendResponse({ result: "Error during analysis" });
        });

        return true;  // Keeps the message channel open for asynchronous response
    }
});
