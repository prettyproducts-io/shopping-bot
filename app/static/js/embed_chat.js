(function() {
    const loadWidget = () => {
        const iframe = document.createElement('iframe');
        iframe.src = 'https://epona.eqbay.co/chat_widget';
        iframe.style.position = 'fixed';
        iframe.style.bottom = '30px';
        iframe.style.right = '30px';
        iframe.style.width = '350px';
        iframe.style.height = '450px';
        iframe.style.border = 'none';
        iframe.style.zIndex = '10000';
        document.body.appendChild(iframe);
    };

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        loadWidget();
    } else {
        document.addEventListener('DOMContentLoaded', loadWidget);
    }
})();