let webSocket;
let keepAliveIntervalId = null; // Keep track of keep-alive interval
const requestMap = new Map();  // Store requests by tab ID

function connectWebSocket() {
    webSocket = new WebSocket('ws://localhost:5000/ws'); // WebSocket connection

    webSocket.onopen = () => {
        console.log('WebSocket connection opened.');
		startKeepAlive(); // Start keep-alive pings when connected
    };

    webSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.result) {
            console.log('Received analysis result.');

            // Find the correct tab ID based on the request map
            const tabId = requestMap.get(data.requestInfo); // Retrieve tab ID using requestInfo // This line was modified or newly added 
            if (tabId) {
                console.log(`Sending result to tab ID: ${tabId}.`);
                chrome.tabs.sendMessage(tabId, { result: data.result }, (response) => {
					if (chrome.runtime.lastError) {
						console.warn('Failed to send message to content script:', chrome.runtime.lastError.message);
					}
				});
				// Remove the tab from the request map after sending the result
                requestMap.delete(data.requestInfo); // This line was modified or newly added
		} else {
			console.warn('No matching tab found to send the result.');
		}								   
        }
    };

    webSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
		stopKeepAlive(); // Stop keep-alive on error											
    };
	webSocket.onclose = () => {
        console.warn('WebSocket connection closed.');
        stopKeepAlive(); // Stop keep-alive on close
        setTimeout(connectWebSocket, 1000); // Reconnect after 1 second
    };						   					  
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'analyzePage') {
        const requestInfo = new Date().getTime().toString(); // Example using timestamp // This line was modified or newly added
        requestMap.set(requestInfo, sender.tab.id);  // Track the tab making the request // This line was modified or newly added
        console.log(`Stored request for tab ID: ${sender.tab.id}`);
	webSocket.send(JSON.stringify({ action: 'analyze_text', text: message.text, requestInfo: requestInfo })); // This line was modified or newly added
        console.log('Text sent through WebSocket.');
    }
	return true;
});

function startKeepAlive() {
    if (keepAliveIntervalId) {
        console.warn('Keep-alive already running. Skipping start.');
        return;
    }

    keepAliveIntervalId = setInterval(() => {
        if (webSocket && webSocket.readyState === WebSocket.OPEN) {
            webSocket.send(JSON.stringify({ type: 'ping' }));
            console.log('Sent keep-alive ping.');
        } else {
            console.warn('WebSocket not open. Stopping keep-alive.');
            stopKeepAlive();
        }
    }, 20000); // Ping every 20 seconds
}

function stopKeepAlive() {
    if (keepAliveIntervalId) {
        console.log('Stopping keep-alive pings.');
        clearInterval(keepAliveIntervalId);
        keepAliveIntervalId = null;
    }
}						   
connectWebSocket(); // Initialize WebSocket
