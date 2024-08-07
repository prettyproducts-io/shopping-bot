(async function createChatWidget() {
    // Create open button
    const openButton = document.createElement('button');
    openButton.innerText = 'Chat with Epona';
    openButton.id = 'epona-chat-open-button';
    openButton.className = 'epona-chat-open-button';
    openButton.onclick = toggleChatWidget;
 
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

    // Function to get CSRF token
    async function getCSRFToken() {
        const response = await fetch('https://epona.eqbay.co/welcome', {
            method: 'GET',
            credentials: 'include'
        });
        const data = await response.json();
        console.log('CSRF Token:', data.csrf_token);
        return data.csrf_token;
    }

    // Function to send session info to chat bot
    async function sendSessionInfo() {
        const sessionInfo = {
            ajs_anonymous_id: getCookie('ajs_anonymous_id'),
            first_session: getCookie('first_session'),
            _pmw_session_data_cart: getSessionStorage('_pmw_session_data_cart'),
            klaviyoPagesVisitCount: getSessionStorage('klaviyoPagesVisitCount')
        };
        console.log('Session Info:', sessionInfo);
    
        try {
            const csrfToken = await getCSRFToken();
            console.log('CSRF Token:', csrfToken);
    
            const response = await fetch('https://epona.eqbay.co/update_session_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(sessionInfo),
                credentials: 'include'
            });
    
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
    
            if (!response.ok) {
                const text = await response.text();
                console.log('Response text:', text);
                throw new Error(`HTTP error! status: ${response.status}, body: ${text}`);
            }
    
            const data = await response.json();
            console.log('Response data:', data);
            return data;
        } catch (error) {
            console.error('Error updating session info:', error);
            console.error('Error details:', error.message);
            return null;
        }
    }

    // Get the session info
    const sessionInfo = await sendSessionInfo();
    console.log('Session Info:', sessionInfo);

    // Create iframe for the chat widget
    const iframe = document.createElement('iframe');
    const anonymousId = sessionInfo?.ajs_anonymous_id || 'unknown';
    iframe.src = `https://epona.eqbay.co/chat_widget?anonymous_id=${encodeURIComponent(anonymousId)}`;
    iframe.id = 'chat-widget-iframe';
    iframe.style.position = 'fixed';
    iframe.style.bottom = '30px';
    iframe.style.right = '30px';
    iframe.style.width = '400px';
    iframe.style.height = '550px';
    iframe.style.border = 'none';
    iframe.style.zIndex = '10001';
    iframe.style.display = 'none';
    iframe.style.borderRadius = '20px';
    iframe.style.overflow = 'hidden';
    iframe.style.boxShadow = '0 5px 20px rgba(0,0,0,0.1)';

    function tryTrackEvent(retries = 3) {
        if (window.analytics && typeof window.analytics.track === 'function') {
            window.analytics.track('Chat Widget Initialized', {
                anonymousId: sessionInfo.ajs_anonymous_id,
                url: window.location.href,
                timestamp: new Date().toISOString()
            });
        } else if (retries > 0) {
            setTimeout(() => tryTrackEvent(retries - 1), 1000); // Wait 1 second before retrying
        } else {
            console.warn('Failed to track Chat Widget Initialized event: analytics not available');
        }
    }
    
    iframe.onload = () => {
        console.log('Chat widget loaded');
        iframe.contentWindow.postMessage({type: 'SESSION_INFO', data: sessionInfo}, '*');
        tryTrackEvent();
    };

    document.body.appendChild(iframe);

    // Function to toggle chat widget visibility
    function toggleChatWidget() {
        const iframe = document.getElementById('chat-widget-iframe');
        const openButton = document.getElementById('epona-chat-open-button');
        if (iframe && openButton) {
            if (iframe.style.display === 'none') {
                iframe.style.display = 'block';
                openButton.style.display = 'none';
            } else {
                iframe.style.display = 'none';
                openButton.style.display = 'block';
            }
        }
    }

    // Listen for messages from the iframe
    window.addEventListener('message', function(event) {
        if (event.origin !== 'https://epona.eqbay.co') return;
        
        if (event.data === 'closeChatWidget') {
            toggleChatWidget();
        }
    }, false);
})();