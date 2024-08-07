document.addEventListener('DOMContentLoaded', function() {
    const chatbox = document.getElementById('chatbox');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const backButton = document.querySelector('.back-button');

    function addUserMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.textContent = message;
        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function addAssistantMessage(message) {
        const messageDiv = document.createElement('div');

        const iconImg = document.createElement('img');
        iconImg.src = '/static/assets/epona-logo.png';
        iconImg.className = 'assistant-icon';
        messageDiv.appendChild(iconImg);
        messageDiv.className = 'message assistant-message';
        

        
        const messageContent = document.createElement('span');
        messageContent.textContent = message;
        messageDiv.appendChild(messageContent);
        
        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function showThinking() {
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'thinking';
        thinkingDiv.textContent = 'Thinking';
        chatbox.appendChild(thinkingDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function removeThinking() {
        const thinkingDiv = chatbox.querySelector('.thinking');
        if (thinkingDiv) {
            chatbox.removeChild(thinkingDiv);
        }
    }

    chatForm.onsubmit = async function(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            addUserMessage(message);
            chatInput.value = '';
            showThinking();
            
            try {
                const response = await sendMessageToServer(message);
                removeThinking();
                addAssistantMessage(response);
            } catch (error) {
                removeThinking();
                addAssistantMessage('Sorry, there was an error processing your request.');
            }
        }
    };

    async function sendMessageToServer(message) {
        // Implement your server communication here
        // This is just a placeholder
        return new Promise(resolve => {
            setTimeout(() => resolve('This is a placeholder response from the assistant.'), 1000);
        });
    }

    backButton.onclick = function() {
        window.parent.postMessage('closeChatWidget', '*');
    };
});