// Extract text from the page and send it to the background script for analysis
function sendTextForAnalysis() {
    let pageText = extractTextFromPage();  // Function to extract text from the page

    // Send message to background script to analyze the page
    chrome.runtime.sendMessage({
        action: 'analyzePage',
        text: pageText
    }, function(response) {
        if (response && response.result) {
            console.log("Analysis result received:", response.result);
            displayResultOnPage(response.result);  // Display the result on the page
        } else {
            console.error("Failed to receive analysis result. Response:", response);
        }
    });
}

// Call the analysis function when content script is executed
sendTextForAnalysis();

// Add a placeholder function for extracting text (You should replace this with your actual implementation)
function extractTextFromPage() {
    let text = document.body.innerText || "";
    return text;
}

// Function to display the result on the page
function displayResultOnPage(result) {
    // Create the popup container
    const div = document.createElement('div');
    div.style.position = 'fixed';
    div.style.bottom = '10px';
    div.style.right = '10px';
    div.style.width = '350px';
    div.style.maxHeight = '400px';
    div.style.overflowY = 'auto';
    div.style.backgroundColor = '#f8f9fa';
    div.style.padding = '15px';
    div.style.border = '2px solid #007bff';
    div.style.boxShadow = '0 0 10px rgba(0,0,0,0.2)';
    div.style.zIndex = '1000';
    div.style.fontFamily = 'Arial, sans-serif';
    div.id = 'gptResultPopup';

    // Create the close button
    const closeButton = document.createElement('button');
    closeButton.innerText = 'X';
    closeButton.style.position = 'absolute';
    closeButton.style.top = '5px';
    closeButton.style.right = '10px';
    closeButton.style.backgroundColor = '#ff0000';
    closeButton.style.color = '#fff';
    closeButton.style.border = 'none';
    closeButton.style.cursor = 'pointer';
    closeButton.style.fontSize = '16px';

    // Add close button functionality
    closeButton.addEventListener('click', () => {
        div.remove();
    });

    // Insert the close button into the div
    div.appendChild(closeButton);

    // Create a container for the analysis result content
    const contentDiv = document.createElement('div');
    contentDiv.style.marginTop = '30px'; // To avoid overlap with close button

    // Check if the result is an object and has a 'message' property
    let messageText = typeof result === 'object' && result.message ? result.message : result;

    // Set the content of the div
    contentDiv.innerHTML = `
        <p style="color: black;">${messageText}</p>
    `;

    // Append the contentDiv to the popup div (after the close button)
    div.appendChild(contentDiv);

    // Append the popup to the body
    document.body.appendChild(div);
}
