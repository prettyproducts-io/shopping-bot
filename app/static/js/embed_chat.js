(function() {
    // Create open button
    const openButton = document.createElement('button');
    openButton.innerText = 'Chat with us';
    openButton.className = 'open-button';
    openButton.onclick = () => {
        const chatWidget = document.createElement('div');
        chatWidget.id = 'chat-widget-container';
        chatWidget.innerHTML = `
            <div class="chat-header">
                <h2>Epona</h2>
            </div>
            <div id="chatbox" class="chatbox"></div>
            <form id="chat-form">
                <input type="text" id="chat-input" placeholder="Enter your message" required>
                <button type="submit">Send</button>
            </form>
        `;
        chatWidget.style.display = 'none';
        
        document.body.appendChild(chatWidget);
    };

    document.body.appendChild(openButton);

    // Function to get cookie value
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // Function to get session storage value
    function getSessionStorage(key) {
        return sessionStorage.getItem(key);
    }

    // Function to send session info to chat bot
    function sendSessionInfo() {
        const sessionInfo = {
            ajs_anonymous_id: getCookie('ajs_anonymous_id'),
            first_session: getCookie('first_session'),
            _pmw_session_data_cart: getSessionStorage('_pmw_session_data_cart'),
            klaviyoPagesVisitCount: getSessionStorage('klaviyoPagesVisitCount')
        };

        // Send session info to the server
        fetch('/update_session_info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(sessionInfo),
            credentials: 'include'  // Include cookies in the request
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error('Server response:', text);
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => console.log('Session info updated:', data))
        .catch(error => {
            console.error('Error updating session info:', error);
        });

        return sessionInfo;
    }

    // Create iframe for the chat widget
    const iframe = document.createElement('iframe');
    iframe.id = 'chat-widget-iframe';
    
    // Get the session info
    const sessionInfo = sendSessionInfo();
    
    // Append the ajs_anonymous_id to the iframe src as a query parameter
    iframe.src = `https://epona.eqbay.co/chat_widget?anonymous_id=${encodeURIComponent(sessionInfo.ajs_anonymous_id)}`;
    
    iframe.style.position = 'fixed';
    iframe.style.bottom = '30px';
    iframe.style.right = '30px';
    iframe.style.width = '350px';
    iframe.style.height = '450px';
    iframe.style.border = 'none';
    iframe.style.zIndex = '10001';
    iframe.style.display = 'none';

    iframe.onload = () => {
        console.log('Chat widget loaded');
        // You can send additional info to the iframe if needed
        iframe.contentWindow.postMessage({type: 'SESSION_INFO', data: sessionInfo}, '*');
    };

    document.body.appendChild(iframe);
})();