function initializeChat(sessionId) {
    const chatbox = document.getElementById('chatbox');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');

    // Display welcome message
    fetch('/welcome')
        .then(response => response.json())
        .then(data => {
            displayMessage(data.welcome_message, 'bot');
        });

    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            displayMessage(message, 'user');
            chatInput.value = '';
            sendMessage(message);
        }
    });

    function sendMessage(message) {
        fetch('/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            const token = data.access_token;
            return fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ question: message })
            });
        })
        .then(response => response.json())
        .then(data => {
            displayMessage(data.response, 'bot');
            if (data.products && data.products.length > 0) {
                displayProducts(data.products);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            displayMessage('Sorry, an error occurred. Please try again.', 'bot');
        });
    }

    function displayMessage(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender);
        messageElement.textContent = message;
        chatbox.appendChild(messageElement);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function displayProducts(products) {
        const productsContainer = document.createElement('div');
        productsContainer.classList.add('products-container');

        products.forEach(product => {
            const productElement = document.createElement('div');
            productElement.classList.add('product');

            const image = document.createElement('img');
            image.src = product.image;
            image.alt = product.title;
            image.style.maxWidth = '500px';

            const title = document.createElement('h3');
            title.textContent = product.title;

            const link = document.createElement('a');
            link.href = product.link;
            link.textContent = 'View Product';
            link.target = '_blank';

            const price = document.createElement('p');
            price.textContent = `Price: ${product.price}`;

            const stockStatus = document.createElement('p');
            stockStatus.textContent = `Stock Status: ${product.stock_status}`;

            if (product.sale_price) {
                const salePrice = document.createElement('p');
                salePrice.textContent = `Sale Price: ${product.sale_price}`;
                salePrice.classList.add('sale-price');
                productElement.appendChild(salePrice);
            }

            productElement.appendChild(image);
            productElement.appendChild(title);
            productElement.appendChild(link);
            productElement.appendChild(price);
            productElement.appendChild(stockStatus);

            productsContainer.appendChild(productElement);
        });

        chatbox.appendChild(productsContainer);
        chatbox.scrollTop = chatbox.scrollHeight;
    }
}