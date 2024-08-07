(function() {
    const loadWidget = () => {
        const iframe = document.createElement('iframe');
        iframe.src = 'https://epona.eqbay.co/chat_widget';
        iframe.style.position = 'fixed';
        iframe.style.bottom = '20px';
        iframe.style.right = '20px';
        iframe.style.width = '300px';
        iframe.style.height = '400px';
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