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

    // Prevent body scrolling when touching the chatbox on mobile
    chatbox.addEventListener('touchmove', function(e) {
        e.stopPropagation();
    }, false);

    function formatMarkdown(text) {
        return text
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')   // Bold text
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

    function appendMessage(sender, message) {
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

        try {
            let content = '';

            if (isJSONString(message)) {
                const jsonMessage = JSON.parse(message);

                if (typeof jsonMessage.response === 'string') {
                    try {
                        const innerJson = JSON.parse(jsonMessage.response.replace(/```json\n|\n```/g, ''));
                        if (innerJson && typeof innerJson.response === 'string') {
                            content = formatMarkdown(innerJson.response);
                            jsonMessage.products = innerJson.products || [];
                        } else {
                            content = formatMarkdown(jsonMessage.response);
                        }
                    } catch (innerError) {
                        content = formatMarkdown(jsonMessage.response);
                    }
                } else {
                    content = formatMarkdown(JSON.stringify(jsonMessage.response));
                }

                const introElement = document.createElement('div');
                introElement.className = `message ${sender}-message`;
                introElement.innerHTML = `<p>${content}</p>`;
                chatbox.appendChild(introElement);

                if (jsonMessage.products && jsonMessage.products.length > 0) {
                    jsonMessage.products.forEach(product => {
                        const { productHTML, descriptionHTML } = formatProduct(product);

                        const productElement = document.createElement('div');
                        productElement.className = `message ${sender}-message product-card`;
                        productElement.innerHTML = productHTML;
                        chatbox.appendChild(productElement);

                        const descriptionElement = document.createElement('div');
                        descriptionElement.className = `message ${sender}-message product-description`;
                        descriptionElement.innerHTML = descriptionHTML;
                        chatbox.appendChild(descriptionElement);

                        // Scroll after each product is added
                        scrollToBottom();
                    });
                }
            } else {
                content = encodeHTML(message);  // Sanitize and encode content
                content = formatMarkdown(content);
                messageElement.innerHTML = `<p>${content}</p>`;
                chatbox.appendChild(messageElement);
            }
        } catch (error) {
            console.error('Failed to parse message:', error);
            messageElement.textContent = encodeHTML(message);  // Fallback to showing raw, encoded message in case of parsing error
            chatbox.appendChild(messageElement);
        }

        messageContainer.appendChild(messageElement);
        chatbox.appendChild(messageContainer);
        chatbox.scrollTop = chatbox.scrollHeight;

        // Scroll to the bottom after adding the message
        scrollToBottom();
    }

    function formatProduct(product) {
        const productHTML = `
            <div class="product-card">
                <img src="${product.image}" alt="${product.title}">
                <h3>${product.title}</h3>
                <div class="price">Price: ${product.price}</div>
                <a class="view-product-btn" href="${product.link}" target="_blank">View Product</a>
            </div>
        `;

        const descriptionHTML = `
            <div class="product-description">
                <p><strong>Stock Status</strong>: ${product.stock_status}</p>
                <p>${product.description}</p>
            </div>
        `;

        return { productHTML, descriptionHTML };
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
                let assistantMessage = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(5).trim();
                            if (data === '[DONE]') {
                                console.log('Stream completed');
                                break;
                            }

                            try {
                                const jsonData = JSON.parse(data);
                                if (jsonData.response) {
                                    assistantMessage = jsonData.response;
                                }
                            } catch (error) {
                                console.error('Failed to parse JSON: ', error);
                                appendMessage('error', `Error: ${error.message}`);
                            }
                        }
                    }
                }

                appendMessage('assistant', assistantMessage);
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
                appendMessage('assistant', data.welcome_message);
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