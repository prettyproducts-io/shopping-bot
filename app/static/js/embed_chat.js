(function() {
    const openButton = document.createElement('button');
    openButton.innerText = 'Chat with us';
    openButton.className = 'open-button';
    openButton.onclick = () => {
        document.getElementById('chat-widget-container').style.display = 'block';
        openButton.style.display = 'none';
    };

    document.body.appendChild(openButton);

    const iframe = document.createElement('iframe');
    iframe.src = 'https://epona.eqbay.co/chat_widget';
    iframe.style.position = 'fixed';
    iframe.style.bottom = '0';
    iframe.style.right = '0';
    iframe.style.width = '350px';
    iframe.style.height = '450px';
    iframe.style.border = 'none';
    iframe.style.zIndex = '10001';
    iframe.style.display = 'none';

    iframe.onload = () => {
        document.getElementById('chat-widget-container').style.display = 'block';
    };

    document.body.appendChild(iframe);
})();