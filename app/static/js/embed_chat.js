(function() {
    // Create open button
    const openButton = document.createElement('button');
    openButton.innerText = 'Chat with us';
    openButton.className = 'open-button';
    openButton.onclick = () => {
        const iframe = document.getElementById('chat-widget-iframe');
        if (iframe) {
            iframe.style.display = 'block';
        }
        openButton.style.display = 'none';
    };

    document.body.appendChild(openButton);

    // Create iframe for the chat widget
    const iframe = document.createElement('iframe');
    iframe.id = 'chat-widget-iframe';
    iframe.src = 'https://epona.eqbay.co/chat_widget';
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
    };

    document.body.appendChild(iframe);
})();