(async function createChatWidget() {
    // Create open button
    const openButton = document.createElement('button');
    openButton.innerText = 'Chat with Epona';
    openButton.id = 'epona-chat-open-button';
    openButton.className = 'epona-chat-open-button';
    openButton.innerHTML = '<span class="button-text">Chat with Epona</span><i class="arrow-icon"></i>';
    openButton.onclick = toggleChatWidget;
 
    document.body.appendChild(openButton);

    // Function to get cookie value
    function getCookie(name) {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name)) {
                return cookie.substring(name.length + 1);
            }
        }
        return null;
    }

    // Function to get the wordpress_logged_in_ cookie value
    async function getWordpressLoggedInUser() {
        try {
            const response = await fetch('/wp-admin/admin-ajax.php?action=fetch_wp_username', {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await response.json();
            console.log('Fetched wp_username data:', data);  // Log AJAX response
            return data.wp_username || null;
        } catch (error) {
            console.error('Error fetching wp_username:', error);
            return null;
        }
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

    // Function to get the cart items from Wordpress
    async function getCartItems() {
        try {
            const response = await fetch('/wp-admin/admin-ajax.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: 'action=fetch_cart_items',
            });
            const data = await response.json();
            const cartData = {
                totalItems: 0,
                totalPrice: 0,
                items: []
            };
    
            data.forEach(item => {
                const price = parseFloat(item.price);
                const quantity = parseInt(item.quantity);
    
                cartData.totalItems += quantity;
                cartData.totalPrice += price * quantity;
    
                cartData.items.push({
                    id: item.id,
                    name: item.product_name,
                    category: item.category,
                    brand: item.brand,
                    sku: item.sku,
                    quantity: quantity,
                    price: price
                });
            });
    
            return cartData;
        } catch (error) {
            console.error('Error fetching cart items:', error);
            return {
                totalItems: 0,
                totalPrice: 0,
                items: []
            };
        }
    }

    // Function to send session info to chat bot
    async function sendSessionInfo() {
        const sessionInfo = {
            current_page_name: document.title,
            current_page_path: window.location.pathname,
            wp_username: getWordpressLoggedInUser(),
            visits: parseInt(getSessionStorage('visits')) || 1,
            start: parseInt(getSessionStorage('first_visit_time')),
            last_visit: Date.now(),
            url: window.location.href,
            path: window.location.pathname,
            referrer: document.referrer,
            prev_visit: parseInt(getSessionStorage('previous_visit_time')),
            time_since_last_visit: Date.now() - (parseInt(getSessionStorage('previous_visit_time')) || 0),
            version: 1.0,
            cart_contents: await getCartItems()
        };

        sessionStorage.setItem('previous_visit_time', String(Date.now()));
    
        try {
            const csrfToken = await getCSRFToken();
            const response = await fetch('https://epona.eqbay.co/update_session_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(sessionInfo),
                credentials: 'include'
            });
    
            if (!response.ok) {
                const text = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${text}`);
            }
    
            return await response.json();
        } catch (error) {
            console.error('Error updating session info:', error);
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
    iframe.style.bottom = '80px';
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
        const buttonText = openButton.querySelector('.button-text');
        if (iframe && openButton) {
            if (iframe.style.display === 'none') {
                iframe.style.display = 'block';
                openButton.classList.add('open');
                buttonText.style.display = 'none'; // Hide the text
            } else {
                iframe.style.display = 'none';
                openButton.classList.remove('open');
                buttonText.style.display = 'inline'; // Show the text again
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