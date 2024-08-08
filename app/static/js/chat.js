document.addEventListener('DOMContentLoaded', function() {
    const chatbox = document.getElementById('chatbox');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');

    function isJSONString(str) {
        try {
            JSON.parse(str);
            return true;
        } catch (e) {
            return false;
        }
    }

    // Enable touch scrolling for mobile devices
    chatbox.style.WebkitOverflowScrolling = 'touch';

    // Make chatbox focusable
    chatbox.tabIndex = 0;

    // Focus chatbox when clicked
    chatbox.addEventListener('click', function() {
        this.focus();
    });

    // Prevent default space bar behavior (page scroll) when chatbox is focused
    chatbox.addEventListener('keydown', function(e) {
        if (e.keyCode === 32 && e.target === chatbox) {
            e.preventDefault();
        }
    });

    // Prevent body scrolling when touching the chatbox on mobile
    chatbox.addEventListener('touchmove', function(e) {
        e.stopPropagation();
    }, false);

    function formatMarkdown(text) {
        return text
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')   // Bold text
            .replace(/(\d+\.\s+)([^\n]+)/g, '<p class="numbered-item">$1$2</p>') // Numbered list items
            .replace(/\n{2,}/g, '</p><p>')                        // Double newlines as paragraph breaks
            .replace(/\n/g, '<br>')                               // Single newlines as line breaks
            .trim();
    }
    
    function encodeHTML(str) {
        return str.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&#039;');
    }

    function scrollToBottom() {
        setTimeout(() => {
            chatbox.scrollTo({
                top: chatbox.scrollHeight,
                behavior: 'smooth'
            });
        }, 100); // 100ms delay
    }

    function appendProductCards(sender, products) {
        products.forEach(product => {
            const cardContainer = document.createElement('div');
            cardContainer.className = `message-container ${sender}-container product-card-container`;
    
            /*
            if (sender === 'assistant') {
                const iconImg = document.createElement('img');
                iconImg.src = '/static/assets/epona-logo.png';
                iconImg.className = 'assistant-icon';
                iconImg.alt = 'Epona Logo';
                cardContainer.appendChild(iconImg);
            }
    */
            const cardElement = document.createElement('div');
            cardElement.className = 'product-card';
            cardElement.innerHTML = `
                <img src="${product.image}" alt="${product.title}" class="product-image">
                <div class="product-info">
                    <h3 class="product-title">${product.title}</h3>
                    <p class="product-price">${product.price}</p>
                    <a href="${product.link}" class="product-link" target="_blank">View Product</a>
                </div>
            `;
    
            cardContainer.appendChild(cardElement);
            chatbox.appendChild(cardContainer);
    
            const descriptionContainer = document.createElement('div');
            descriptionContainer.className = `message-container ${sender}-container`;
    
            if (sender === 'assistant') {
                const descIconImg = document.createElement('img');
                descIconImg.src = '/static/assets/epona-logo.png';
                descIconImg.className = 'assistant-icon';
                descIconImg.alt = 'Epona Logo';
                descriptionContainer.appendChild(descIconImg);
            }
    
            const descriptionElement = document.createElement('div');
            descriptionElement.className = `message ${sender}-message product-description`;
            descriptionElement.innerHTML = `<p>${product.description}</p>`;
            descriptionContainer.appendChild(descriptionElement);
            chatbox.appendChild(descriptionContainer);
        });
    }

    function appendMessage(sender, message) {
        try {
            let jsonMessage;
            if (typeof message === 'string') {
                try {
                    jsonMessage = JSON.parse(message);
                } catch (e) {
                    // If parsing fails, treat it as a plain text message
                    jsonMessage = { response: message };
                }
            } else {
                jsonMessage = message;
            }
    
            const messageContainer = document.createElement('div');
            messageContainer.className = `message-container ${sender}-container`;
    
            if (sender === 'assistant') {
                const iconImg = document.createElement('img');
                iconImg.src = '/static/assets/epona-logo.png';
                iconImg.className = 'assistant-icon';
                iconImg.alt = 'Epona Logo';
                messageContainer.appendChild(iconImg);
            }
    
            const messageElement = document.createElement('div');
            messageElement.className = `message ${sender}-message`;
    
            if (jsonMessage.response) {
                messageElement.innerHTML = `<p>${formatMarkdown(jsonMessage.response)}</p>`;
            } else if (sender === 'user') {
                messageElement.innerHTML = `<p>${formatMarkdown(message)}</p>`;
            }
    
            messageContainer.appendChild(messageElement);
            chatbox.appendChild(messageContainer);
    
            if (jsonMessage.includes_products && jsonMessage.products && jsonMessage.products.length > 0) {
                appendProductCards(sender, jsonMessage.products);
            }
        } catch (error) {
            console.error('Failed to process message:', error);
        }
    
        scrollToBottom();
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question) return;
    
        appendMessage('user', question);
        chatInput.value = '';
    
        const formData = new FormData(chatForm);
        formData.set('question', question);
    
        try {
            const response = await fetch('/ask', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                }
            });
    
            if (response.ok) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
    
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(5).trim();
                            if (data === '[DONE]') {
                                console.log('Stream completed');
                                continue;
                            }
    
                            try {
                                const jsonData = JSON.parse(data);
                                appendMessage('assistant', jsonData);
                            } catch (error) {
                                console.error('Failed to parse JSON: ', error);
                                appendMessage('error', `Error: ${error.message}`);
                            }
                        }
                    }
                }
            } else {
                const errorData = await response.json();
                appendMessage('error', `Error: ${errorData.error}`);
            }
        } catch (error) {
            appendMessage('error', `Error: ${error.message}`);
        }
    });

    async function getWelcomeMessage() {
        try {
            const response = await fetch('/welcome', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                }
            });
            if (response.ok) {
                const data = await response.json();
                appendMessage('assistant', data);
            } else {
                console.error('Failed to fetch welcome message');
            }
        } catch (error) {
            console.error('Error fetching welcome message:', error);
        }
    }

    window.addEventListener('load', getWelcomeMessage);
        
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });
});